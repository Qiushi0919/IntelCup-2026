from __future__ import annotations

import math
import random

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from models import DetectionEvent, DroneState


class DroneSimulator(QObject):
    state_changed = pyqtSignal(object)
    event_generated = pyqtSignal(object)
    log_generated = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.state = DroneState()
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self._mission_running = False
        self._paused = False
        self._returning = False
        self._landing = False
        self._time = 0.0
        self._event_sent = False
        self._takeoff_point = (35.0, 35.0)
        self._return_point = (35.0, 35.0)
        self._waypoints = [
            (115.0, 290.0),
            (270.0, 290.0),
            (410.0, 290.0),
            (410.0, 120.0),
            (250.0, 120.0),
            (100.0, 120.0),
        ]
        self._route_points = [self._takeoff_point, *self._waypoints, self._return_point]
        self.state.x, self.state.y = self._takeoff_point
        self.state.total_waypoints = len(self._waypoints)
        self._segment = 0
        self._segment_t = 0.0
        self._special_path: list[tuple[float, float, float]] = []
        self._path_index = 0
        self._path_mode = False
        self._path_t = 0.0
        self._origin_pos = (0.0, 0.0, 0.0)
        self._spiral_start_altitude = 1.8
        self._sim_speed_cm_s = 40.0

    @property
    def waypoints(self) -> list[tuple[float, float]]:
        return self._waypoints[:]

    def apply_command(self, action: str) -> tuple[bool, str]:
        if action == "TAKEOFF":
            if self.state.armed or self.state.altitude > 0.1:
                return False, "无人机已经解锁或处于空中"
            self.state.armed = True
            self.state.flight_mode = "GUIDED"
            self.state.flight_phase = "自动起飞"
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
            self._path_mode = False
            self.log_generated.emit("INFO", "收到起飞命令：模拟器开始爬升")
            return True, "起飞命令已接受"

        if action == "START_MISSION":
            if self.state.altitude < 1.0:
                return False, "请先完成起飞并达到安全高度"
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
            self._path_mode = False
            self.state.flight_mode = "AUTO"
            self.state.flight_phase = "覆盖巡逻"
            self.log_generated.emit("INFO", "巡逻任务已开始")
            return True, "巡逻任务已开始"

        if action == "HOLD":
            if self.state.altitude <= 0.1:
                return False, "无人机尚未起飞"
            self._paused = True
            self._mission_running = False
            self.state.flight_mode = "LOITER"
            self.state.flight_phase = "暂停悬停"
            self.log_generated.emit("WARNING", "任务暂停，无人机进入悬停")
            return True, "已暂停并悬停"

        if action == "CONTINUE":
            if not self._paused:
                return False, "当前任务未暂停"
            self._paused = False
            self._mission_running = True
            self.state.flight_mode = "AUTO"
            self.state.flight_phase = "覆盖巡逻"
            self.log_generated.emit("INFO", "任务继续执行")
            return True, "任务已继续"

        if action == "RTL":
            if self.state.altitude <= 0.1:
                return False, "无人机尚未起飞"
            self._mission_running = False
            self._paused = False
            self._returning = True
            self._landing = False
            self._path_mode = False
            self.state.flight_mode = "RTL"
            self.state.flight_phase = "正在返航"
            self.log_generated.emit("WARNING", "已进入返航流程")
            return True, "返航命令已接受"

        if action == "LAND":
            if self.state.altitude <= 0.05:
                return False, "无人机已经在地面"
            self._mission_running = False
            self._paused = False
            self._returning = False
            self._landing = True
            self._path_mode = False
            self.state.flight_mode = "LAND"
            self.state.flight_phase = "自动降落"
            self.log_generated.emit("WARNING", "已进入自动降落流程")
            return True, "降落命令已接受"

        if action == "SHUTDOWN":
            self._mission_running = False
            self._paused = False
            self._returning = False
            self._landing = False
            self._path_mode = False
            self.state.armed = False
            self.state.flight_mode = "DISARM"
            self.state.flight_phase = "紧急关机保护"
            self.state.vertical_speed = 0.0
            self.log_generated.emit("WARNING", "已执行关机保护命令")
            return True, "关机保护命令已接受"

        if action == "STATUS":
            s = self.state
            info = (
                f"位置({s.x:.1f},{s.y:.1f}) cm 高度{s.altitude:.1f} m "
                f"姿态({s.roll:.1f},{s.pitch:.1f},{s.yaw:.1f}) "
                f"速度{s.horizontal_speed:.1f} cm/s 电压{s.battery_voltage:.1f} V "
                f"模式:{s.flight_mode} 阶段:{s.flight_phase}"
            )
            self.log_generated.emit("INFO", info)
            return True, info

        if action.startswith("GOTO"):
            parts = action.split()
            if len(parts) >= 3:
                try:
                    gx, gy = float(parts[1]), float(parts[2])
                    gz = float(parts[3]) if len(parts) >= 4 else self.state.altitude
                except ValueError:
                    return False, "GOTO 格式：GOTO x y [z]，x/y 单位 cm，z 单位 m"
                if self.state.altitude < 0.3:
                    return False, "请先起飞"
                gx = max(0.0, min(480.0, gx))
                gy = max(0.0, min(400.0, gy))
                gz = max(0.5, min(50.0, gz))
                self._generate_straight_path(
                    self.state.x,
                    self.state.y,
                    self.state.altitude,
                    gx,
                    gy,
                    gz,
                )
                self._mission_running = True
                self._paused = False
                self._returning = False
                self._landing = False
                self.state.flight_mode = "GOTO"
                self.state.flight_phase = f"飞往({gx:.0f},{gy:.0f})"
                self.log_generated.emit("INFO", f"GOTO {gx:.0f} {gy:.0f} {gz:.1f}")
                return True, f"正在飞往 ({gx:.0f}, {gy:.0f}) cm，高度 {gz:.1f} m"
            return False, "GOTO 格式：GOTO x y [z]，x/y 单位 cm，z 单位 m"

        if action.startswith("SET_ALT"):
            try:
                alt = float(action.split()[1])
            except (IndexError, ValueError):
                return False, "SET_ALT 格式：SET_ALT 高度"
            alt = max(0.5, min(50.0, alt))
            self.state.altitude = alt
            self.state.rangefinder_distance = alt
            self.log_generated.emit("INFO", f"仿真高度已设为 {alt:.1f} m")
            return True, f"高度设为 {alt:.1f} m"

        if action.startswith("SET_SPEED"):
            try:
                speed_m_s = float(action.split()[1])
            except (IndexError, ValueError):
                return False, "SET_SPEED 格式：SET_SPEED 速度"
            speed_m_s = max(0.5, min(20.0, speed_m_s))
            self._sim_speed_cm_s = speed_m_s * 20.0
            self.state.horizontal_speed = self._sim_speed_cm_s
            self.log_generated.emit("INFO", f"仿真速度已设为 {speed_m_s:.1f}")
            return True, f"速度设为 {speed_m_s:.1f}，仿真模型按比例运动"

        if action == "CIRCLE":
            if self.state.altitude < 0.3:
                return False, "请先起飞"
            self._path_mode = True
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
            self.state.flight_mode = "CIRCLE"
            self.state.flight_phase = "圆形航线"
            self._origin_pos = (self.state.x, self.state.y, self.state.altitude)
            self._path_t = 0.0
            self.log_generated.emit("INFO", "圆形航线开始")
            return True, "圆形航线已开始"

        if action == "FIGURE_EIGHT":
            if self.state.altitude < 0.3:
                return False, "请先起飞"
            self._path_mode = True
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
            self.state.flight_mode = "FIGURE8"
            self.state.flight_phase = "8字航线"
            self._origin_pos = (self.state.x, self.state.y, self.state.altitude)
            self._path_t = 0.0
            self.log_generated.emit("INFO", "8字航线开始")
            return True, "8字航线已开始"

        if action == "SQUARE":
            if self.state.altitude < 0.3:
                return False, "请先起飞"
            side = 150.0
            cx, cy = self.state.x, self.state.y
            alt = self.state.altitude
            self._special_path = [
                (min(480.0, cx + side), min(400.0, cy + side), alt),
                (min(480.0, cx + side), max(0.0, cy - side), alt),
                (max(0.0, cx - side), max(0.0, cy - side), alt),
                (max(0.0, cx - side), min(400.0, cy + side), alt),
                (min(480.0, cx + side), min(400.0, cy + side), alt),
            ]
            self._path_index = 0
            self._path_mode = True
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
            self.state.flight_mode = "SQUARE"
            self.state.flight_phase = "正方形航线"
            self.log_generated.emit("INFO", "正方形航线开始")
            return True, "正方形航线已开始"

        if action == "ZIGZAG":
            if self.state.altitude < 0.3:
                return False, "请先起飞"
            cx, cy = self.state.x, self.state.y
            alt = self.state.altitude
            self._special_path = []
            for i in range(5):
                x = max(0.0, min(480.0, cx + i * 80.0))
                y = max(0.0, min(400.0, cy + (80.0 if i % 2 == 0 else -80.0)))
                self._special_path.append((x, y, alt))
            self._path_index = 0
            self._path_mode = True
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
            self.state.flight_mode = "ZIGZAG"
            self.state.flight_phase = "Z字形航线"
            self.log_generated.emit("INFO", "Z字形航线开始")
            return True, "Z字形航线已开始"

        if action.startswith("SPIRAL"):
            if self.state.altitude < 0.3:
                return False, "请先起飞"
            try:
                top_alt = float(action.split()[1]) if len(action.split()) >= 2 else 20.0
            except ValueError:
                top_alt = 20.0
            top_alt = max(self.state.altitude + 0.5, min(50.0, top_alt))
            self._path_mode = True
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
            self.state.flight_mode = "SPIRAL"
            self.state.flight_phase = f"螺旋上升至{top_alt:.0f}m"
            self._origin_pos = (self.state.x, self.state.y, top_alt)
            self._spiral_start_altitude = self.state.altitude
            self._path_t = 0.0
            self.log_generated.emit("INFO", f"螺旋上升至{top_alt:.0f}m")
            return True, f"螺旋上升至{top_alt:.0f}m"

        return False, f"模拟器不支持命令 {action}"

    def _tick(self) -> None:
        dt = self.timer.interval() / 1000.0
        self._time += dt
        state = self.state
        state.last_update = state.last_update.now()
        state.link_latency_ms = max(12, int(28 + math.sin(self._time * 0.7) * 8))
        state.packet_loss_percent = max(0.0, 0.2 + math.sin(self._time * 0.23) * 0.15)
        state.roll = math.sin(self._time * 1.3) * (1.1 if state.altitude > 0.1 else 0.1)
        state.pitch = math.cos(self._time * 1.1) * (0.9 if state.altitude > 0.1 else 0.1)
        state.yaw = (state.yaw + (1.6 if self._mission_running else 0.25)) % 360
        state.optical_flow_quality = int(84 + math.sin(self._time * 0.5) * 6)

        if state.armed:
            state.elapsed_seconds += 1 if int(self._time * 4) % 4 == 0 else 0
            state.battery_percent = max(4.0, state.battery_percent - 0.012)
            state.battery_voltage = 13.6 + state.battery_percent / 100 * 3.0

        if state.armed and state.altitude < 1.8 and not self._landing:
            state.vertical_speed = 0.55
            state.altitude = min(1.8, state.altitude + dt * state.vertical_speed)
            state.rangefinder_distance = state.altitude
            state.horizontal_speed = 0.0
            if state.altitude >= 1.79:
                state.flight_phase = "等待任务"
                state.flight_mode = "LOITER"
                self._mission_running = False

        elif self._mission_running and not self._paused:
            if self._path_mode:
                self._advance_special_path(dt)
            else:
                self._advance_route(dt)

        elif self._returning:
            self._move_towards(40.0, 40.0, dt, speed=30.0)
            if math.hypot(state.x - 40.0, state.y - 40.0) < 3.5:
                self._returning = False
                self._landing = True
                state.flight_mode = "LAND"
                state.flight_phase = "返航点降落"

        elif self._landing:
            state.horizontal_speed = 0.0
            state.vertical_speed = -0.45
            state.altitude = max(0.0, state.altitude + dt * state.vertical_speed)
            state.rangefinder_distance = state.altitude
            if state.altitude <= 0.01:
                self._landing = False
                state.armed = False
                state.flight_mode = "STANDBY"
                state.flight_phase = "任务完成"
                state.vertical_speed = 0.0
                self.log_generated.emit("INFO", "无人机已落地并上锁")

        else:
            state.horizontal_speed = 0.0
            state.vertical_speed = 0.0
            state.rangefinder_distance = state.altitude

        if state.battery_percent < 25:
            state.warning = "电量偏低，建议尽快返航"
        elif state.optical_flow_quality < 45:
            state.warning = "光流质量不足"
        else:
            state.warning = ""

        self.state_changed.emit(state)

    def _advance_route(self, dt: float) -> None:
        state = self.state
        start = self._route_points[self._segment]
        end = self._route_points[
            min(self._segment + 1, len(self._route_points) - 1)
        ]
        segment_length = max(0.1, math.hypot(end[0] - start[0], end[1] - start[1]))
        speed = 40.0
        previous_x, previous_y = state.x, state.y
        self._segment_t += speed * dt / segment_length

        if self._segment_t >= 1.0:
            self._segment_t = 0.0
            self._segment += 1
            if self._segment >= len(self._route_points) - 1:
                state.x, state.y = self._return_point
                state.current_waypoint = state.total_waypoints
                state.mission_progress = 100.0
                self._mission_running = False
                self._returning = False
                state.flight_mode = "RTL"
                state.flight_phase = "巡逻完成，已返航"
                self.log_generated.emit("INFO", "覆盖巡逻完成，已返回黑色返航区")
                return
            start = self._route_points[self._segment]
            end = self._route_points[self._segment + 1]

        state.x = start[0] + (end[0] - start[0]) * self._segment_t
        state.y = start[1] + (end[1] - start[1]) * self._segment_t
        state.horizontal_speed = speed
        state.distance_travelled += math.hypot(
            state.x - previous_x, state.y - previous_y
        )
        state.current_waypoint = min(self._segment, state.total_waypoints)
        state.mission_progress = (
            min(self._segment + self._segment_t, state.total_waypoints)
            / state.total_waypoints
            * 100
        )
        state.flight_phase = "覆盖巡逻"

        if state.mission_progress > 42 and not self._event_sent:
            self._event_sent = True
            event = DetectionEvent(
                target_type="红色火源",
                confidence=0.93,
                x=state.x,
                y=state.y,
                altitude=state.altitude,
            )
            self.event_generated.emit(event)
            self.log_generated.emit(
                "WARNING",
                f"视觉模块发现红色火源，位置 ({state.x:.1f}, {state.y:.1f})",
            )

    def _generate_straight_path(
        self,
        x1: float,
        y1: float,
        z1: float,
        x2: float,
        y2: float,
        z2: float,
    ) -> None:
        steps = 20
        self._special_path = []
        for index in range(steps + 1):
            ratio = index / steps
            self._special_path.append(
                (
                    x1 + (x2 - x1) * ratio,
                    y1 + (y2 - y1) * ratio,
                    z1 + (z2 - z1) * ratio,
                )
            )
        self._path_index = 0
        self._path_mode = True

    def _advance_special_path(self, dt: float) -> None:
        state = self.state
        speed = max(20.0, self._sim_speed_cm_s)

        if state.flight_mode == "GOTO" and self._special_path:
            target_x, target_y, target_alt = self._special_path[-1]
            self._move_towards(target_x, target_y, dt, speed)
            if state.altitude < target_alt:
                state.altitude = min(target_alt, state.altitude + dt * 0.8)
            elif state.altitude > target_alt:
                state.altitude = max(target_alt, state.altitude - dt * 0.8)
            state.rangefinder_distance = state.altitude
            if math.hypot(state.x - target_x, state.y - target_y) < 5.0:
                self._path_mode = False
                self._mission_running = False
                state.flight_phase = "到达目标点"
                self.log_generated.emit("INFO", "已到达目标点")
            return

        if state.flight_mode in {"SQUARE", "ZIGZAG"} and self._special_path:
            if self._path_index >= len(self._special_path):
                self._path_mode = False
                self._mission_running = False
                return
            target_x, target_y, target_alt = self._special_path[self._path_index]
            self._move_towards(target_x, target_y, dt, speed)
            state.altitude = target_alt
            state.rangefinder_distance = state.altitude
            if math.hypot(state.x - target_x, state.y - target_y) < 5.0:
                self._path_index += 1
                if self._path_index >= len(self._special_path):
                    self._path_mode = False
                    self._mission_running = False
                    state.flight_phase = (
                        "正方形完成" if state.flight_mode == "SQUARE" else "Z字形完成"
                    )
                    self.log_generated.emit("INFO", f"{state.flight_phase}")
            return

        if state.flight_mode in {"CIRCLE", "FIGURE8", "SPIRAL"}:
            previous_x, previous_y = state.x, state.y
            origin_x, origin_y, target_alt = self._origin_pos
            radius = 80.0
            self._path_t += dt * max(0.2, speed / 100.0)
            t = self._path_t

            if state.flight_mode == "CIRCLE":
                state.x = max(0.0, min(480.0, origin_x + radius * math.cos(t)))
                state.y = max(0.0, min(400.0, origin_y + radius * math.sin(t)))
                state.altitude = target_alt
                state.flight_phase = "圆形航线"
                state.yaw = (math.degrees(t) + 90.0) % 360.0

            elif state.flight_mode == "FIGURE8":
                state.x = max(0.0, min(480.0, origin_x + radius * math.sin(t)))
                state.y = max(
                    0.0,
                    min(400.0, origin_y + radius * math.sin(t * 2.0) * 0.6),
                )
                state.altitude = target_alt
                state.flight_phase = "8字航线"
                state.yaw = (math.degrees(t) + 90.0) % 360.0

            elif state.flight_mode == "SPIRAL":
                fraction = min(1.0, t / 30.0)
                spiral_radius = radius * (1.0 - fraction * 0.5)
                state.x = max(
                    0.0,
                    min(480.0, origin_x + spiral_radius * math.cos(t)),
                )
                state.y = max(
                    0.0,
                    min(400.0, origin_y + spiral_radius * math.sin(t)),
                )
                state.altitude = self._spiral_start_altitude + (
                    target_alt - self._spiral_start_altitude
                ) * fraction
                state.flight_phase = f"螺旋上升 {state.altitude:.0f}/{target_alt:.0f}m"
                state.yaw = (math.degrees(t) + 90.0) % 360.0
                if fraction >= 1.0:
                    self._path_mode = False
                    self._mission_running = False
                    state.flight_phase = "螺旋完成"

            state.rangefinder_distance = state.altitude
            state.horizontal_speed = speed
            state.vertical_speed = 0.1 if state.flight_mode == "SPIRAL" else 0.0
            state.distance_travelled += math.hypot(
                state.x - previous_x,
                state.y - previous_y,
            )

    def _move_towards(
        self, target_x: float, target_y: float, dt: float, speed: float
    ) -> None:
        state = self.state
        dx = target_x - state.x
        dy = target_y - state.y
        distance = math.hypot(dx, dy)
        if distance <= 0.001:
            state.x = target_x
            state.y = target_y
            return
        step = min(distance, speed * dt)
        previous_x, previous_y = state.x, state.y
        state.x += dx / distance * step
        state.y += dy / distance * step
        state.horizontal_speed = speed
        state.distance_travelled += math.hypot(
            state.x - previous_x, state.y - previous_y
        )

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
            self.log_generated.emit("INFO", "收到起飞命令：模拟器开始爬升")
            return True, "起飞命令已接受"

        if action == "START_MISSION":
            if self.state.altitude < 1.0:
                return False, "请先完成起飞并达到安全高度"
            self._mission_running = True
            self._paused = False
            self._returning = False
            self._landing = False
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
            self.state.flight_mode = "LAND"
            self.state.flight_phase = "自动降落"
            self.log_generated.emit("WARNING", "已进入自动降落流程")
            return True, "降落命令已接受"

        if action == "SHUTDOWN":
            self._mission_running = False
            self._paused = False
            self._returning = False
            self._landing = False
            self.state.armed = False
            self.state.flight_mode = "DISARM"
            self.state.flight_phase = "紧急关机保护"
            self.state.vertical_speed = 0.0
            self.log_generated.emit("WARNING", "已执行关机保护命令")
            return True, "关机保护命令已接受"

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

import gc
import os
import time
import image
import lvgl as lv

from machine import TOUCH
from media.display import Display
from media.sensor import CAM_CHN_ID_1

from temp import motor
from apps.gimbal_control.threshold_store import ThresholdStore


class PIDController:
    """Small positional PID whose output is an angle change in degrees."""

    def __init__(self, kp, ki, kd, output_limit=1.5,
                 integral_limit=500.0, deadband=5):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit
        self.integral_limit = integral_limit
        self.deadband = deadband
        self.integral = 0.0
        self.last_error = None

    def reset(self):
        self.integral = 0.0
        self.last_error = None

    def update(self, error, dt):
        if abs(error) <= self.deadband:
            self.reset()
            return 0.0
        dt = max(0.02, min(0.5, dt))
        self.integral += error * dt
        self.integral = max(
            -self.integral_limit,
            min(self.integral_limit, self.integral))
        derivative = 0.0
        if self.last_error is not None:
            derivative = (error - self.last_error) / dt
        self.last_error = error
        output = (self.kp * error + self.ki * self.integral
                  + self.kd * derivative)
        return max(-self.output_limit, min(self.output_limit, output))


class LaserTrackingPage:
    """Track red/green laser blobs and move the green spot with PID."""

    PAN_ID = 0
    TILT_ID = 1
    PAN_MIN = -6.0
    PAN_MAX = 22.0
    TILT_MIN = -4.0
    TILT_MAX = 21.0
    HOME_WAIT_MS = 1200
    CONTROL_INTERVAL_MS = 120
    BLOB_AREA_MIN = 4
    BLOB_PIXELS_MIN = 4
    # 激光点应当是紧凑的小光斑。大片反光即使颜色命中阈值，也不参与跟踪。
    BLOB_PIXELS_MAX = 500
    BLOB_WIDTH_MAX = 32
    BLOB_HEIGHT_MAX = 32
    GREEN_BLOB_PIXELS_MIN = 12
    GREEN_BLOB_WIDTH_MIN = 3
    GREEN_BLOB_HEIGHT_MIN = 3
    GREEN_BLOB_WIDTH_MAX = 40
    GREEN_BLOB_HEIGHT_MAX = 40
    ROI_SCALE = 0.6
    ROI_DASH_LENGTH = 20
    ROI_DASH_GAP = 12

    def __init__(self, app, parent, back_callback):
        self.app = app
        self.parent = parent
        self.back_callback = back_callback
        self.store = ThresholdStore()
        self.touch = TOUCH(0)
        self.thresholds = []
        self.red_index = 0
        self.green_index = 1
        self.pan_sign = 1
        self.tilt_sign = -1
        self.red_label = None
        self.green_label = None
        self.pan_direction_label = None
        self.tilt_direction_label = None
        self.status_label = None
        self.lvgl_blank = None
        self.running = False

    def display(self):
        motor.set_uart(self.app.app_manager.gimbal_uart)
        self.thresholds = self.store.load()
        self.red_index = 0
        self.green_index = 1 if len(self.thresholds) > 1 else 0
        self._create_ui()

    def _make_label(self, parent, text, x, y, color=0x1F2937):
        label = lv.label(parent)
        label.set_text(text)
        label.set_pos(x, y)
        label.set_style_text_color(lv.color_hex(color), 0)
        return label

    def _make_button(self, parent, text, callback, width=75, height=42,
                     color=0x2563EB):
        button = lv.btn(parent)
        button.set_size(width, height)
        button.set_style_radius(9, 0)
        button.set_style_bg_color(lv.color_hex(color), 0)
        button.set_style_shadow_width(0, 0)
        button.set_style_pad_all(0, 0)
        button.add_event(callback, lv.EVENT.CLICKED, None)
        label = lv.label(button)
        label.set_text(text)
        label.center()
        return button

    def _create_ui(self):
        self.parent.clean()
        self._make_button(
            self.parent, lv.SYMBOL.LEFT + " 任务",
            self.back_callback, 92, 42, 0x64748B).set_pos(12, 5)
        self.status_label = self._make_label(
            self.parent, "激光跟踪 · 选择红光和绿光阈值",
            120, 16, 0x15803D)

        self._make_threshold_panel(20, 62, "红色激光阈值", True, 0xDC2626)
        self._make_threshold_panel(330, 62, "绿色激光阈值", False, 0x16A34A)

        self._make_label(
            self.parent, "若绿光越跟越远，请停止后反转对应方向。",
            145, 230, 0x6B7280)
        self._make_button(
            self.parent, "水平反转", self._toggle_pan_sign,
            120, 50, 0x7C3AED).set_pos(105, 265)
        self.pan_direction_label = self._make_label(
            self.parent, self._direction_text(self.pan_sign),
            235, 282, 0x111827)
        self._make_button(
            self.parent, "俯仰反转", self._toggle_tilt_sign,
            120, 50, 0x7C3AED).set_pos(355, 265)
        self.tilt_direction_label = self._make_label(
            self.parent, self._direction_text(self.tilt_sign),
            485, 282, 0x111827)

        self._make_button(
            self.parent, "启动激光跟踪", self._start_tracking,
            190, 62, 0x16A34A).set_pos(225, 335)
        if len(self.thresholds) < 2:
            self._show_status("请先在阈值调节中至少保存两个阈值", False)

    def _make_threshold_panel(self, x, y, title, is_red, color):
        panel = lv.obj(self.parent)
        panel.set_pos(x, y)
        panel.set_size(290, 150)
        panel.set_style_radius(12, 0)
        panel.set_style_border_width(2, 0)
        panel.set_style_border_color(lv.color_hex(color), 0)
        panel.set_style_pad_all(0, 0)
        panel.clear_flag(lv.obj.FLAG.SCROLLABLE)
        self._make_label(panel, title, 14, 12, color)
        previous = self._previous_red if is_red else self._previous_green
        following = self._next_red if is_red else self._next_green
        self._make_button(panel, "<", previous, 48, 42, 0x64748B).set_pos(12, 48)
        self._make_button(panel, ">", following, 48, 42, color).set_pos(230, 48)
        label = self._make_label(panel, self._threshold_name(is_red), 82, 60)
        if is_red:
            self.red_label = label
        else:
            self.green_label = label
        self._make_label(
            panel, self._threshold_values_text(is_red), 14, 112, 0x6B7280)

    def _threshold_name(self, is_red):
        if not self.thresholds:
            return "未保存"
        index = self.red_index if is_red else self.green_index
        return self.thresholds[index]["name"]

    def _threshold_values_text(self, is_red):
        if not self.thresholds:
            return "LAB: --"
        index = self.red_index if is_red else self.green_index
        return "LAB: {}".format(self.thresholds[index]["values"])

    def _refresh_threshold_labels(self):
        if self.red_label is not None:
            self.red_label.set_text(self._threshold_name(True))
        if self.green_label is not None:
            self.green_label.set_text(self._threshold_name(False))

    def _cycle_threshold(self, is_red, delta):
        if not self.thresholds:
            return
        if is_red:
            self.red_index = (self.red_index + delta) % len(self.thresholds)
        else:
            self.green_index = (self.green_index + delta) % len(self.thresholds)
        self._create_ui()

    def _previous_red(self, event=None):
        self._cycle_threshold(True, -1)

    def _next_red(self, event=None):
        self._cycle_threshold(True, 1)

    def _previous_green(self, event=None):
        self._cycle_threshold(False, -1)

    def _next_green(self, event=None):
        self._cycle_threshold(False, 1)

    @staticmethod
    def _direction_text(sign):
        return "方向：正" if sign > 0 else "方向：反"

    def _toggle_pan_sign(self, event=None):
        self.pan_sign *= -1
        self.pan_direction_label.set_text(self._direction_text(self.pan_sign))

    def _toggle_tilt_sign(self, event=None):
        self.tilt_sign *= -1
        self.tilt_direction_label.set_text(self._direction_text(self.tilt_sign))

    def _show_status(self, text, ok):
        if self.status_label is not None:
            self.status_label.set_text(text)
            self.status_label.set_style_text_color(
                lv.color_hex(0x15803D if ok else 0xDC2626), 0)

    def _set_lvgl_visible(self, visible):
        try:
            if visible:
                self.app.screen.set_style_bg_opa(255, 0)
                self.app.title_bar.clear_flag(lv.obj.FLAG.HIDDEN)
                self.parent.clear_flag(lv.obj.FLAG.HIDDEN)
                self.app.screen.invalidate()
                lv.refr_now(None)
                if self.lvgl_blank is not None:
                    Display.show_image(
                        self.lvgl_blank, 0, 0,
                        Display.LAYER_OSD3, alpha=0)
                time.sleep_ms(30)
                self.lvgl_blank = None
            else:
                self.app.screen.set_style_bg_opa(0, 0)
                self.app.title_bar.add_flag(lv.obj.FLAG.HIDDEN)
                self.parent.add_flag(lv.obj.FLAG.HIDDEN)
                self.app.screen.invalidate()
                lv.refr_now(None)
                self.lvgl_blank = image.Image(640, 480, image.BGRA8888)
                self.lvgl_blank.clear()
                Display.show_image(self.lvgl_blank, alpha=0)
                time.sleep_ms(30)
        except Exception as exc:
            print("laser tracking LVGL layer:", exc)

    @staticmethod
    def _largest_blob(blobs):
        if not blobs:
            return None
        largest = blobs[0]
        for blob in blobs[1:]:
            if blob.pixels() > largest.pixels():
                largest = blob
        return largest

    def _tracking_roi(self, frame):
        frame_width = frame.width()
        frame_height = frame.height()
        roi_width = int(frame_width * self.ROI_SCALE)
        roi_height = int(frame_height * self.ROI_SCALE)
        return (
            (frame_width - roi_width) // 2,
            (frame_height - roi_height) // 2,
            roi_width,
            roi_height,
        )

    def _find_laser(self, frame, threshold, roi,
                    pixels_min=None, width_min=1, height_min=1,
                    width_max=None, height_max=None):
        if pixels_min is None:
            pixels_min = self.BLOB_PIXELS_MIN
        if width_max is None:
            width_max = self.BLOB_WIDTH_MAX
        if height_max is None:
            height_max = self.BLOB_HEIGHT_MAX
        blobs = frame.find_blobs(
            [threshold], roi=roi, x_stride=1, y_stride=1,
            area_threshold=self.BLOB_AREA_MIN,
            pixels_threshold=pixels_min,
            merge=False)
        candidates = []
        for blob in blobs:
            if blob.pixels() < pixels_min:
                continue
            if blob.pixels() > self.BLOB_PIXELS_MAX:
                continue
            if blob.w() < width_min:
                continue
            if blob.h() < height_min:
                continue
            if blob.w() > width_max:
                continue
            if blob.h() > height_max:
                continue
            candidates.append(blob)
        return self._largest_blob(candidates)

    def _draw_tracking_roi(self, frame, roi):
        x, y, width, height = roi
        right = x + width - 1
        bottom = y + height - 1
        step = self.ROI_DASH_LENGTH + self.ROI_DASH_GAP
        color = (0, 220, 255)
        for dash_x in range(x, right + 1, step):
            dash_end = min(dash_x + self.ROI_DASH_LENGTH, right)
            frame.draw_line(
                dash_x, y, dash_end, y, color=color, thickness=2)
            frame.draw_line(
                dash_x, bottom, dash_end, bottom,
                color=color, thickness=2)
        for dash_y in range(y, bottom + 1, step):
            dash_end = min(dash_y + self.ROI_DASH_LENGTH, bottom)
            frame.draw_line(
                x, dash_y, x, dash_end, color=color, thickness=2)
            frame.draw_line(
                right, dash_y, right, dash_end,
                color=color, thickness=2)

    @staticmethod
    def _draw_blob(frame, blob, color, label):
        if blob is None:
            return
        frame.draw_rectangle(blob.rect(), color=color, thickness=3)
        frame.draw_cross(blob.cx(), blob.cy(), color=color,
                         size=8, thickness=2)
        frame.draw_string_advanced(
            max(0, blob.x()), max(62, blob.y() - 22),
            20, label, color=color)

    def _draw_run_controls(self, frame, red_blob, green_blob):
        frame.draw_rectangle(
            0, 0, 145, 52, color=(70, 80, 95), thickness=1, fill=True)
        frame.draw_string_advanced(
            12, 14, 22, "停止返回", color=(255, 255, 255))
        frame.draw_rectangle(
            475, 0, 165, 52, color=(190, 35, 35), thickness=1, fill=True)
        frame.draw_string_advanced(
            490, 14, 22, "回零停止", color=(255, 255, 255))
        if red_blob is not None and green_blob is not None:
            frame.draw_line(
                green_blob.cx(), green_blob.cy(),
                red_blob.cx(), red_blob.cy(),
                color=(255, 255, 0), thickness=2)
            message = "R({},{}) G({},{})".format(
                red_blob.cx(), red_blob.cy(),
                green_blob.cx(), green_blob.cy())
        elif red_blob is None and green_blob is None:
            message = "未识别到红光和绿光"
        elif red_blob is None:
            message = "未识别到红光"
        else:
            message = "未识别到绿光"
        frame.draw_rectangle(
            0, 438, 640, 42, color=(20, 28, 38), thickness=1, fill=True)
        frame.draw_string_advanced(
            12, 447, 20, message, color=(255, 255, 255))

    @staticmethod
    def _clamp(value, minimum, maximum):
        return max(minimum, min(maximum, value))

    def _home_both(self):
        pan_ok = motor.go_to_home(self.PAN_ID)
        time.sleep_ms(10)
        tilt_ok = motor.go_to_home(self.TILT_ID)
        if pan_ok and tilt_ok:
            self.app.current_pan = 0
            self.app.current_tilt = 0
            return True
        return False

    def _start_tracking(self, event=None):
        self.thresholds = self.store.load()
        if len(self.thresholds) < 2:
            self._show_status("至少需要两个已保存的 LAB 阈值", False)
            return
        self.red_index %= len(self.thresholds)
        self.green_index %= len(self.thresholds)
        if self.red_index == self.green_index:
            self._show_status("红光和绿光必须选择不同的阈值", False)
            return
        red_threshold = tuple(self.thresholds[self.red_index]["values"])
        green_threshold = tuple(self.thresholds[self.green_index]["values"])
        try:
            if not self._home_both():
                self._show_status("启动前双轴回零失败", False)
                return
            self._show_status("双轴回零，请稍候", True)
            time.sleep_ms(self.HOME_WAIT_MS)
            self._set_lvgl_visible(False)
            self._run_tracking(red_threshold, green_threshold)
            self._show_status("激光跟踪已停止", True)
        except Exception as exc:
            print("start laser tracking:", exc)
            self._show_status("激光跟踪运行错误", False)
        finally:
            self.running = False
            self._set_lvgl_visible(True)

    def _run_tracking(self, red_threshold, green_threshold):
        pan_pid = PIDController(0.012, 0.0003, 0.0015)
        tilt_pid = PIDController(0.012, 0.0003, 0.0015)
        pan_target = 0.0
        tilt_target = 0.0
        last_pan_command = 0
        last_tilt_command = 0
        last_control = time.ticks_ms()
        self.running = True

        while self.running:
            os.exitpoint()
            points = self.touch.read(1)
            if len(points) and points[0].event == TOUCH.EVENT_DOWN:
                point = points[0]
                if point.y < 60 and point.x < 160:
                    break
                if point.y < 60 and point.x > 460:
                    self._home_both()
                    break

            frame = self.app.app_manager.pl.sensor.snapshot(
                chn=CAM_CHN_ID_1)
            tracking_roi = self._tracking_roi(frame)
            red_blob = self._find_laser(
                frame, red_threshold, tracking_roi)
            green_blob = self._find_laser(
                frame, green_threshold, tracking_roi,
                pixels_min=self.GREEN_BLOB_PIXELS_MIN,
                width_min=self.GREEN_BLOB_WIDTH_MIN,
                height_min=self.GREEN_BLOB_HEIGHT_MIN,
                width_max=self.GREEN_BLOB_WIDTH_MAX,
                height_max=self.GREEN_BLOB_HEIGHT_MAX)

            now = time.ticks_ms()
            if red_blob is not None and green_blob is not None:
                if time.ticks_diff(now, last_control) >= self.CONTROL_INTERVAL_MS:
                    dt = time.ticks_diff(now, last_control) / 1000.0
                    error_x = red_blob.cx() - green_blob.cx()
                    error_y = red_blob.cy() - green_blob.cy()
                    pan_target = self._clamp(
                        pan_target + self.pan_sign * pan_pid.update(error_x, dt),
                        self.PAN_MIN, self.PAN_MAX)
                    tilt_target = self._clamp(
                        tilt_target + self.tilt_sign * tilt_pid.update(error_y, dt),
                        self.TILT_MIN, self.TILT_MAX)
                    pan_command = int(round(pan_target))
                    tilt_command = int(round(tilt_target))
                    if pan_command != last_pan_command:
                        if motor.set_absolute_angle(self.PAN_ID, pan_command):
                            last_pan_command = pan_command
                            self.app.current_pan = pan_command
                    if tilt_command != last_tilt_command:
                        time.sleep_ms(10)
                        if motor.set_absolute_angle(self.TILT_ID, tilt_command):
                            last_tilt_command = tilt_command
                            self.app.current_tilt = tilt_command
                    last_control = now
            else:
                pan_pid.reset()
                tilt_pid.reset()
                last_control = now

            self._draw_tracking_roi(frame, tracking_roi)
            self._draw_blob(frame, red_blob, (255, 0, 0), "RED")
            self._draw_blob(frame, green_blob, (255, 255, 255), "GREEN")
            self._draw_run_controls(frame, red_blob, green_blob)
            Display.show_image(
                frame, 0, 0, Display.LAYER_OSD3, alpha=255)
            time.sleep_ms(10)

    def cleanup(self):
        self.running = False
        self.red_label = None
        self.green_label = None
        self.pan_direction_label = None
        self.tilt_direction_label = None
        self.status_label = None
        self.lvgl_blank = None
        gc.collect()

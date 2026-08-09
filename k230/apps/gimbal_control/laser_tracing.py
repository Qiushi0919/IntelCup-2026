import gc
import os
import time
import image
import lvgl as lv

from machine import TOUCH
from media.display import Display
from media.sensor import CAM_CHN_ID_1

from temp import motor
from apps.gimbal_control.laser_tracking import PIDController
from apps.gimbal_control.threshold_store import ThresholdStore


class LaserTracingPage:
    """Extract a black-line skeleton once and move a red laser along it."""

    PAN_ID = 0
    TILT_ID = 1
    PAN_MIN = -6.0
    PAN_MAX = 22.0
    TILT_MIN = -4.0
    TILT_MAX = 21.0
    HOME_WAIT_MS = 1200
    CONTROL_INTERVAL_MS = 120

    BLACK_AREA_MIN = 80
    BLACK_PIXELS_MIN = 80
    RED_PIXELS_MIN = 4
    RED_PIXELS_MAX = 500
    RED_WIDTH_MAX = 32
    RED_HEIGHT_MAX = 32

    PROCESS_SCALE = 2
    SKELETON_MAX_ITERATIONS = 32
    SKELETON_PIXEL_MAX = 12000
    PATH_SAMPLE_DISTANCE = 4
    PATH_JOIN_DISTANCE_MAX = 12
    PATH_MIN_POINTS = 6
    TARGET_TOLERANCE = 8
    TARGET_STABLE_FRAMES = 3
    BINARY_WHITE_THRESHOLD = (128, 255)
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
        self.black_index = 0
        self.red_index = 1
        self.pan_sign = 1
        self.tilt_sign = -1
        self.black_label = None
        self.red_label = None
        self.pan_direction_label = None
        self.tilt_direction_label = None
        self.status_label = None
        self.lvgl_blank = None
        self.running = False

    def display(self):
        motor.set_uart(self.app.app_manager.gimbal_uart)
        self.thresholds = self.store.load()
        self.black_index = 0
        self.red_index = 1 if len(self.thresholds) > 1 else 0
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
            self.parent, "激光循迹 · 选择黑线和红色激光阈值",
            120, 16, 0x0891B2)

        self._make_threshold_panel(
            20, 62, "黑色线条阈值", True, 0x334155)
        self._make_threshold_panel(
            330, 62, "红色激光阈值", False, 0xDC2626)

        self._make_label(
            self.parent, "启动后只提取一次骨架；若激光反向运动，请停止并反转方向。",
            75, 230, 0x6B7280)
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
            self.parent, "启动激光循迹", self._start_tracing,
            190, 62, 0x0891B2).set_pos(225, 335)
        if len(self.thresholds) < 2:
            self._show_status("请先在阈值调节中至少保存两个阈值", False)

    def _make_threshold_panel(self, x, y, title, is_black, color):
        panel = lv.obj(self.parent)
        panel.set_pos(x, y)
        panel.set_size(290, 150)
        panel.set_style_radius(12, 0)
        panel.set_style_border_width(2, 0)
        panel.set_style_border_color(lv.color_hex(color), 0)
        panel.set_style_pad_all(0, 0)
        panel.clear_flag(lv.obj.FLAG.SCROLLABLE)
        self._make_label(panel, title, 14, 12, color)
        previous = self._previous_black if is_black else self._previous_red
        following = self._next_black if is_black else self._next_red
        self._make_button(panel, "<", previous, 48, 42, 0x64748B).set_pos(12, 48)
        self._make_button(panel, ">", following, 48, 42, color).set_pos(230, 48)
        label = self._make_label(
            panel, self._threshold_name(is_black), 82, 60)
        if is_black:
            self.black_label = label
        else:
            self.red_label = label
        self._make_label(
            panel, self._threshold_values_text(is_black),
            14, 112, 0x6B7280)

    def _threshold_name(self, is_black):
        if not self.thresholds:
            return "未保存"
        index = self.black_index if is_black else self.red_index
        return self.thresholds[index]["name"]

    def _threshold_values_text(self, is_black):
        if not self.thresholds:
            return "LAB: --"
        index = self.black_index if is_black else self.red_index
        return "LAB: {}".format(self.thresholds[index]["values"])

    def _cycle_threshold(self, is_black, delta):
        if not self.thresholds:
            return
        if is_black:
            self.black_index = (self.black_index + delta) % len(self.thresholds)
        else:
            self.red_index = (self.red_index + delta) % len(self.thresholds)
        self._create_ui()

    def _previous_black(self, event=None):
        self._cycle_threshold(True, -1)

    def _next_black(self, event=None):
        self._cycle_threshold(True, 1)

    def _previous_red(self, event=None):
        self._cycle_threshold(False, -1)

    def _next_red(self, event=None):
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
            print("laser tracing LVGL layer:", exc)

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

    def _find_red_laser(self, frame, threshold, roi):
        blobs = frame.find_blobs(
            [threshold], roi=roi, x_stride=1, y_stride=1,
            area_threshold=4, pixels_threshold=self.RED_PIXELS_MIN,
            merge=False)
        candidates = []
        for blob in blobs:
            if blob.pixels() > self.RED_PIXELS_MAX:
                continue
            if blob.w() > self.RED_WIDTH_MAX:
                continue
            if blob.h() > self.RED_HEIGHT_MAX:
                continue
            candidates.append(blob)
        return self._largest_blob(candidates)

    @staticmethod
    def _pixel_is_white(pixel):
        if isinstance(pixel, tuple):
            return pixel[0] + pixel[1] + pixel[2] >= 600
        return pixel is not None and pixel >= 128

    def _find_white_seed(self, binary_image, rect):
        x, y, width, height = rect
        for pixel_y in range(y, y + height):
            for pixel_x in range(x, x + width):
                if self._pixel_is_white(
                        binary_image.get_pixel(pixel_x, pixel_y)):
                    return (pixel_x, pixel_y)
        return None

    def _morphological_skeleton(self, component):
        working = component.copy()
        opened = component.copy()
        layer = component.copy()
        skeleton = component.copy()
        skeleton.clear()
        iterations = 0
        for _ in range(self.SKELETON_MAX_ITERATIONS):
            remaining = working.find_blobs(
                [self.BINARY_WHITE_THRESHOLD], area_threshold=1,
                pixels_threshold=1, merge=False)
            if not remaining:
                break
            # Work images are grayscale. Reusing them avoids RGB565 copies
            # and repeated heap allocation during the one-time extraction.
            opened.copy_from(working)
            opened.open(1)
            layer.copy_from(working)
            layer.difference(opened)
            skeleton.b_or(layer)
            working.erode(1)
            iterations += 1
            os.exitpoint()
        working = None
        opened = None
        layer = None
        gc.collect()
        print("laser tracing skeleton iterations:", iterations)
        return skeleton

    @staticmethod
    def _neighbor_keys(key, pixels, width):
        x = key % width
        y = key // width
        neighbors = []
        for offset_y in (-1, 0, 1):
            for offset_x in (-1, 0, 1):
                if offset_x == 0 and offset_y == 0:
                    continue
                neighbor_x = x + offset_x
                neighbor_y = y + offset_y
                if (neighbor_x < 0 or neighbor_x >= width
                        or neighbor_y < 0):
                    continue
                neighbor = neighbor_y * width + neighbor_x
                if neighbor in pixels:
                    neighbors.append(neighbor)
        return neighbors

    @classmethod
    def _order_skeleton_pixels(cls, pixel_keys, width, start_hint=None):
        if not pixel_keys:
            return []
        pixels = pixel_keys if isinstance(pixel_keys, set) else set(pixel_keys)
        endpoints = []
        for key in pixels:
            if len(cls._neighbor_keys(key, pixels, width)) == 1:
                endpoints.append(key)
        choices = endpoints if endpoints else list(pixels)
        if start_hint is None:
            current = min(choices)
        else:
            hint_x, hint_y = start_hint
            current = min(
                choices,
                key=lambda key: ((key % width - hint_x) ** 2
                                 + (key // width - hint_y) ** 2))

        remaining = set(pixels)
        ordered = []
        previous = None
        while current in remaining:
            ordered.append(current)
            remaining.remove(current)
            candidates = cls._neighbor_keys(current, remaining, width)
            if not candidates:
                break
            if previous is None or len(candidates) == 1:
                following = min(candidates)
            else:
                current_x = current % width
                current_y = current // width
                previous_x = previous % width
                previous_y = previous // width
                direction_x = current_x - previous_x
                direction_y = current_y - previous_y
                following = max(
                    candidates,
                    key=lambda key: (
                        direction_x * (key % width - current_x)
                        + direction_y * (key // width - current_y)))
            previous = current
            current = following
        return ordered

    @classmethod
    def _connected_skeleton_components(cls, pixel_keys, width):
        remaining = set(pixel_keys)
        components = []
        while remaining:
            seed = next(iter(remaining))
            remaining.remove(seed)
            stack = [seed]
            component = set([seed])
            while stack:
                current = stack.pop()
                for neighbor in cls._neighbor_keys(
                        current, remaining, width):
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
            components.append(component)
        return components

    @staticmethod
    def _key_distance_squared(first, second, width):
        delta_x = first % width - second % width
        delta_y = first // width - second // width
        return delta_x * delta_x + delta_y * delta_y

    def _build_motion_key_path(self, pixel_keys, width, start_hint=None):
        components = self._connected_skeleton_components(pixel_keys, width)
        segments = []
        for component in components:
            ordered = self._order_skeleton_pixels(component, width)
            if len(ordered) >= 2:
                segments.append(ordered)
        if not segments:
            return []

        if start_hint is None:
            first_index = min(
                range(len(segments)), key=lambda index: segments[index][0])
            reverse_first = False
        else:
            hint_x, hint_y = start_hint

            def hint_distance(key):
                return ((key % width - hint_x) ** 2
                        + (key // width - hint_y) ** 2)

            first_index = 0
            reverse_first = False
            best_distance = None
            for index, segment in enumerate(segments):
                start_distance = hint_distance(segment[0])
                end_distance = hint_distance(segment[-1])
                distance = min(start_distance, end_distance)
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    first_index = index
                    reverse_first = end_distance < start_distance

        first = segments.pop(first_index)
        if reverse_first:
            first.reverse()
        path = list(first)
        maximum_gap_squared = self.PATH_JOIN_DISTANCE_MAX ** 2

        while segments:
            current = path[-1]
            best_index = None
            best_reverse = False
            best_distance = None
            for index, segment in enumerate(segments):
                start_distance = self._key_distance_squared(
                    current, segment[0], width)
                end_distance = self._key_distance_squared(
                    current, segment[-1], width)
                distance = min(start_distance, end_distance)
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_index = index
                    best_reverse = end_distance < start_distance
            if best_distance is None or best_distance > maximum_gap_squared:
                break
            following = segments.pop(best_index)
            if best_reverse:
                following.reverse()
            path.extend(following)

        if (len(path) > 2
                and self._key_distance_squared(
                    path[-1], path[0], width) <= maximum_gap_squared):
            path.append(path[0])
        return path

    def _make_skeleton_mask(self, frame, skeleton, crop_x, crop_y):
        mask = image.Image(frame.width(), frame.height(), image.GRAYSCALE)
        mask.clear()
        mask.draw_image(
            skeleton,
            crop_x,
            crop_y,
            x_scale=float(self.PROCESS_SCALE),
            y_scale=float(self.PROCESS_SCALE),
            alpha=256)
        return mask

    def _extract_path(self, frame, black_threshold, red_threshold, roi):
        # Apply the saved LAB threshold before resizing. Mean-pooling a thin
        # black line with its bright background changes its LAB values and can
        # make an otherwise correct threshold miss the line completely.
        black_blobs = frame.find_blobs(
            [black_threshold], roi=roi, x_stride=1, y_stride=1,
            area_threshold=self.BLACK_AREA_MIN,
            pixels_threshold=self.BLACK_PIXELS_MIN,
            merge=False)
        black_blob = self._largest_blob(black_blobs)
        if black_blob is None:
            raise RuntimeError("ROI内未找到黑线连通区域")
        print(
            "laser tracing black blob: rect={}, pixels={}".format(
                black_blob.rect(), black_blob.pixels()))

        padding = 2
        roi_x, roi_y, roi_width, roi_height = roi
        crop_x = max(roi_x, black_blob.x() - padding)
        crop_y = max(roi_y, black_blob.y() - padding)
        crop_right = min(
            roi_x + roi_width,
            black_blob.x() + black_blob.w() + padding)
        crop_bottom = min(
            roi_y + roi_height,
            black_blob.y() + black_blob.h() + padding)
        crop_rect = (
            crop_x, crop_y, crop_right - crop_x, crop_bottom - crop_y)
        component = frame.copy(roi=crop_rect)
        component.binary([black_threshold])
        component = component.to_grayscale()
        # Max-pool the already binary image so any black-line pixel survives
        # the 2x reduction, then force the result back to strict 0/255.
        component = component.midpoint_pooled(
            self.PROCESS_SCALE, self.PROCESS_SCALE, bias=1.0)
        component.binary([self.BINARY_WHITE_THRESHOLD])

        white_blobs = component.find_blobs(
            [self.BINARY_WHITE_THRESHOLD], x_stride=1, y_stride=1,
            area_threshold=1, pixels_threshold=1, merge=False)
        component_blob = self._largest_blob(white_blobs)
        if component_blob is None:
            raise RuntimeError("黑线二值连通区域为空")
        seed = self._find_white_seed(component, component_blob.rect())
        if seed is None:
            raise RuntimeError("黑线二值区域没有前景像素")
        component.flood_fill(
            seed[0], seed[1], seed_threshold=0.0,
            floating_threshold=0.0, color=255,
            clear_background=True)

        skeleton = self._morphological_skeleton(component)
        component = None
        gc.collect()
        initial_red = self._find_red_laser(frame, red_threshold, roi)
        start_hint = None
        if initial_red is not None:
            start_hint = (
                (initial_red.cx() - crop_x) // self.PROCESS_SCALE,
                (initial_red.cy() - crop_y) // self.PROCESS_SCALE)

        skeleton_pixels = set()
        skeleton_width = skeleton.width()
        for pixel_y in range(skeleton.height()):
            if pixel_y % 8 == 0:
                os.exitpoint()
            for pixel_x in range(skeleton_width):
                if self._pixel_is_white(skeleton.get_pixel(pixel_x, pixel_y)):
                    skeleton_pixels.add(pixel_y * skeleton_width + pixel_x)
                    if len(skeleton_pixels) > self.SKELETON_PIXEL_MAX:
                        raise RuntimeError("黑线骨架过于复杂")
        skeleton_mask = self._make_skeleton_mask(
            frame, skeleton, crop_x, crop_y)
        skeleton = None
        ordered = self._build_motion_key_path(
            skeleton_pixels, skeleton_width, start_hint)
        skeleton_pixels = None
        if not ordered:
            raise RuntimeError("黑线骨架路径为空")

        sampled = [ordered[0]]
        minimum_squared = self.PATH_SAMPLE_DISTANCE ** 2
        for key in ordered[1:]:
            previous = sampled[-1]
            delta_x = key % skeleton_width - previous % skeleton_width
            delta_y = key // skeleton_width - previous // skeleton_width
            if delta_x * delta_x + delta_y * delta_y >= minimum_squared:
                sampled.append(key)
        if sampled[-1] != ordered[-1]:
            sampled.append(ordered[-1])

        path = []
        for key in sampled:
            local_x = key % skeleton_width
            local_y = key // skeleton_width
            path.append((
                crop_x + local_x * self.PROCESS_SCALE
                + self.PROCESS_SCALE // 2,
                crop_y + local_y * self.PROCESS_SCALE
                + self.PROCESS_SCALE // 2))
        full_blob_rect = black_blob.rect()
        print(
            "laser tracing path: skeleton={}, sampled={}".format(
                len(ordered), len(path)))
        return path, skeleton_mask, full_blob_rect

    @staticmethod
    def _draw_path(self, frame, skeleton_mask, path, blob_rect,
                   target_index, roi):
        frame.replace((255, 255, 255), mask=skeleton_mask)
        self._draw_tracking_roi(frame, roi)
        if blob_rect is not None:
            frame.draw_rectangle(
                blob_rect, color=(255, 140, 0), thickness=2)
        if target_index < len(path):
            target = path[target_index]
            frame.draw_circle(
                target[0], target[1], 9,
                color=(255, 0, 255), thickness=3)

    @staticmethod
    def _draw_red_blob(frame, blob):
        if blob is None:
            return
        frame.draw_rectangle(blob.rect(), color=(255, 0, 0), thickness=3)
        frame.draw_cross(
            blob.cx(), blob.cy(), color=(255, 0, 0),
            size=8, thickness=2)
        frame.draw_string_advanced(
            max(0, blob.x()), max(62, blob.y() - 22),
            20, "RED", color=(255, 0, 0))

    @staticmethod
    def _draw_controls(frame, red_blob, target_index, path_length):
        frame.draw_rectangle(
            0, 0, 145, 52, color=(70, 80, 95), thickness=1, fill=True)
        frame.draw_string_advanced(
            12, 14, 22, "停止返回", color=(255, 255, 255))
        frame.draw_rectangle(
            475, 0, 165, 52,
            color=(190, 35, 35), thickness=1, fill=True)
        frame.draw_string_advanced(
            490, 14, 22, "回零停止", color=(255, 255, 255))
        if red_blob is None:
            message = "未识别到红色激光"
        else:
            message = "路径点 {}/{}  红光({},{})".format(
                min(target_index + 1, path_length), path_length,
                red_blob.cx(), red_blob.cy())
        frame.draw_rectangle(
            0, 438, 640, 42,
            color=(20, 28, 38), thickness=1, fill=True)
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

    def _start_tracing(self, event=None):
        self.thresholds = self.store.load()
        if len(self.thresholds) < 2:
            self._show_status("至少需要两个已保存的 LAB 阈值", False)
            return
        self.black_index %= len(self.thresholds)
        self.red_index %= len(self.thresholds)
        if self.black_index == self.red_index:
            self._show_status("黑线和红光必须选择不同的阈值", False)
            return
        black_threshold = tuple(
            self.thresholds[self.black_index]["values"])
        red_threshold = tuple(self.thresholds[self.red_index]["values"])
        completed = False
        try:
            if not self._home_both():
                self._show_status("启动前双轴回零失败", False)
                return
            self._show_status("双轴回零，请稍候", True)
            time.sleep_ms(self.HOME_WAIT_MS)
            self._set_lvgl_visible(False)
            completed = self._run_tracing(black_threshold, red_threshold)
            if completed:
                self._show_status("激光循迹已完成一次", True)
            else:
                self._show_status("激光循迹已停止", True)
        except Exception as exc:
            print("start laser tracing:", exc)
            if "有效黑线骨架" in str(exc):
                self._show_status("未提取到有效黑线骨架，请检查黑线阈值", False)
            elif "ROI内未找到黑线" in str(exc):
                self._show_status("ROI 内没有找到黑线连通区域", False)
            elif "二值" in str(exc):
                self._show_status("黑线二值区域为空，请检查画面", False)
            elif "骨架路径为空" in str(exc):
                self._show_status("已找到黑线，但骨架路径生成失败", False)
            elif "骨架过于复杂" in str(exc):
                self._show_status("黑线骨架过于复杂，请收紧黑线阈值", False)
            else:
                self._show_status("激光循迹运行错误", False)
        finally:
            self.running = False
            self._set_lvgl_visible(True)
            gc.collect()

    def _run_tracing(self, black_threshold, red_threshold):
        captured = self.app.app_manager.pl.sensor.snapshot(
            chn=CAM_CHN_ID_1)
        tracking_roi = self._tracking_roi(captured)
        preview = captured.copy()
        self._draw_tracking_roi(preview, tracking_roi)
        preview.draw_string_advanced(
            185, 215, 26, "正在提取黑线骨架...",
            color=(0, 255, 255))
        Display.show_image(
            preview, 0, 0, Display.LAYER_OSD3, alpha=255)
        preview = None
        path, skeleton_mask, blob_rect = self._extract_path(
            captured, black_threshold, red_threshold, tracking_roi)
        captured = None
        gc.collect()
        if path is None or len(path) < self.PATH_MIN_POINTS:
            raise RuntimeError("未提取到有效黑线骨架")

        pan_pid = PIDController(0.012, 0.0003, 0.0015)
        tilt_pid = PIDController(0.012, 0.0003, 0.0015)
        pan_target = 0.0
        tilt_target = 0.0
        last_pan_command = 0
        last_tilt_command = 0
        last_control = time.ticks_ms()
        target_index = 0
        stable_frames = 0
        self.running = True

        while self.running and target_index < len(path):
            os.exitpoint()
            points = self.touch.read(1)
            if len(points) and points[0].event == TOUCH.EVENT_DOWN:
                point = points[0]
                if point.y < 60 and point.x < 160:
                    return False
                if point.y < 60 and point.x > 460:
                    self._home_both()
                    return False

            frame = self.app.app_manager.pl.sensor.snapshot(
                chn=CAM_CHN_ID_1)
            red_blob = self._find_red_laser(
                frame, red_threshold, tracking_roi)
            now = time.ticks_ms()
            if red_blob is None:
                stable_frames = 0
                pan_pid.reset()
                tilt_pid.reset()
                last_control = now
            else:
                target_x, target_y = path[target_index]
                error_x = target_x - red_blob.cx()
                error_y = target_y - red_blob.cy()
                if (abs(error_x) <= self.TARGET_TOLERANCE
                        and abs(error_y) <= self.TARGET_TOLERANCE):
                    stable_frames += 1
                    if stable_frames >= self.TARGET_STABLE_FRAMES:
                        target_index += 1
                        stable_frames = 0
                        pan_pid.reset()
                        tilt_pid.reset()
                        last_control = now
                else:
                    stable_frames = 0

                if (target_index < len(path)
                        and time.ticks_diff(
                            now, last_control) >= self.CONTROL_INTERVAL_MS):
                    target_x, target_y = path[target_index]
                    error_x = target_x - red_blob.cx()
                    error_y = target_y - red_blob.cy()
                    dt = time.ticks_diff(now, last_control) / 1000.0
                    pan_target = self._clamp(
                        pan_target + self.pan_sign
                        * pan_pid.update(error_x, dt),
                        self.PAN_MIN, self.PAN_MAX)
                    tilt_target = self._clamp(
                        tilt_target + self.tilt_sign
                        * tilt_pid.update(error_y, dt),
                        self.TILT_MIN, self.TILT_MAX)
                    pan_command = int(round(pan_target))
                    tilt_command = int(round(tilt_target))
                    if pan_command != last_pan_command:
                        if motor.set_absolute_angle(
                                self.PAN_ID, pan_command):
                            last_pan_command = pan_command
                            self.app.current_pan = pan_command
                    if tilt_command != last_tilt_command:
                        time.sleep_ms(10)
                        if motor.set_absolute_angle(
                                self.TILT_ID, tilt_command):
                            last_tilt_command = tilt_command
                            self.app.current_tilt = tilt_command
                    last_control = now

            self._draw_path(
                frame, skeleton_mask, path, blob_rect,
                target_index, tracking_roi)
            self._draw_red_blob(frame, red_blob)
            self._draw_controls(
                frame, red_blob, target_index, len(path))
            Display.show_image(
                frame, 0, 0, Display.LAYER_OSD3, alpha=255)
            time.sleep_ms(10)
        return target_index >= len(path)

    def cleanup(self):
        self.running = False
        self.black_label = None
        self.red_label = None
        self.pan_direction_label = None
        self.tilt_direction_label = None
        self.status_label = None
        self.lvgl_blank = None
        gc.collect()

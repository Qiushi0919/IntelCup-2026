from __future__ import annotations

import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
CAPTURE_DIR = APP_DIR / "captures"
RECORD_DIR = APP_DIR / "recordings"
DEFAULT_CAMERA_URL = "rtsp://172.25.135.2:554"


class CameraWorker:
    """后台读取 RTSP，保持界面流畅并在断线后自动重连。"""

    def __init__(self, frame_queue: queue.Queue, status_queue: queue.Queue):
        self.frame_queue = frame_queue
        self.status_queue = status_queue
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.url = DEFAULT_CAMERA_URL

    def start(self, url: str) -> None:
        self.stop()
        self.url = url
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self.thread = None

    def _open_camera(self) -> cv2.VideoCapture:
        if self.url.lower().startswith("rtsp://"):
            # 强制 RTSP 使用 TCP，手机热点环境下通常比 UDP 稳定。
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                "rtsp_transport;tcp|stimeout;5000000|max_delay;500000"
            )
        else:
            os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
        capture = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def _put_latest_frame(self, frame) -> None:
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            pass

    def _run(self) -> None:
        retry_delay = 1.0

        while not self.stop_event.is_set():
            self.status_queue.put(("status", "正在连接摄像头…"))
            capture = self._open_camera()

            if not capture.isOpened():
                capture.release()
                self.status_queue.put(("status", f"连接失败，{retry_delay:.0f} 秒后重试"))
                self.stop_event.wait(retry_delay)
                retry_delay = min(retry_delay + 1.0, 5.0)
                continue

            retry_delay = 1.0
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            source_fps = capture.get(cv2.CAP_PROP_FPS)
            self.status_queue.put(
                ("connected", {"width": width, "height": height, "fps": source_fps})
            )

            consecutive_failures = 0
            while not self.stop_event.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= 10:
                        self.status_queue.put(("status", "视频中断，正在重新连接…"))
                        break
                    time.sleep(0.05)
                    continue

                consecutive_failures = 0
                self._put_latest_frame((time.perf_counter(), frame))

            capture.release()

        self.status_queue.put(("status", "已停止"))


class CameraViewer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AMB82-Mini 无线摄像头")
        self.geometry("1100x760")
        self.minsize(760, 540)
        self.configure(bg="#101418")

        CAPTURE_DIR.mkdir(exist_ok=True)
        RECORD_DIR.mkdir(exist_ok=True)

        self.frame_queue: queue.Queue = queue.Queue(maxsize=1)
        self.status_queue: queue.Queue = queue.Queue()
        self.worker = CameraWorker(self.frame_queue, self.status_queue)

        self.current_frame = None
        self.current_photo = None
        self.recording = False
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.recording_path: Optional[Path] = None
        self.frame_times: list[float] = []
        self.last_frame_time = 0.0

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(20, self._update_ui)
        self.after(300, self.connect_camera)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#101418")
        style.configure("TLabel", background="#101418", foreground="#e9eef2")
        style.configure("TButton", padding=(12, 7))
        style.configure("Accent.TButton", background="#2672ff", foreground="white")
        style.map("Accent.TButton", background=[("active", "#4387ff")])

        top = ttk.Frame(self, padding=(14, 12))
        top.pack(fill=tk.X)

        ttk.Label(top, text="摄像头地址").pack(side=tk.LEFT)
        self.url_var = tk.StringVar(value=DEFAULT_CAMERA_URL)
        self.url_entry = ttk.Entry(top, textvariable=self.url_var, width=42)
        self.url_entry.pack(side=tk.LEFT, padx=(8, 10), fill=tk.X, expand=True)

        self.connect_button = ttk.Button(
            top, text="重新连接", style="Accent.TButton", command=self.connect_camera
        )
        self.connect_button.pack(side=tk.LEFT)

        controls = ttk.Frame(self, padding=(14, 0, 14, 10))
        controls.pack(fill=tk.X)

        self.snapshot_button = ttk.Button(
            controls, text="截图", command=self.save_snapshot, state=tk.DISABLED
        )
        self.snapshot_button.pack(side=tk.LEFT)

        self.record_button = ttk.Button(
            controls, text="开始录像", command=self.toggle_recording, state=tk.DISABLED
        )
        self.record_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(controls, text="打开截图目录", command=self.open_capture_dir).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        self.info_var = tk.StringVar(value="等待连接")
        ttk.Label(controls, textvariable=self.info_var).pack(side=tk.RIGHT)

        self.video_panel = tk.Label(
            self,
            bg="#050708",
            fg="#8c98a2",
            text="正在等待摄像头画面…",
            font=("Microsoft YaHei UI", 16),
        )
        self.video_panel.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))

        bottom = ttk.Frame(self, padding=(14, 0, 14, 12))
        bottom.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(bottom, textvariable=self.status_var).pack(side=tk.LEFT)

        ttk.Label(
            bottom,
            text="快捷键：S 截图　R 开始/停止录像　Esc 退出",
        ).pack(side=tk.RIGHT)

        self.bind("<KeyPress-s>", lambda _event: self.save_snapshot())
        self.bind("<KeyPress-S>", lambda _event: self.save_snapshot())
        self.bind("<KeyPress-r>", lambda _event: self.toggle_recording())
        self.bind("<KeyPress-R>", lambda _event: self.toggle_recording())
        self.bind("<Escape>", lambda _event: self._on_close())

    def connect_camera(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("地址为空", "请输入 RTSP 地址。")
            return

        self._stop_recording()
        self.current_frame = None
        self.frame_times.clear()
        self.snapshot_button.configure(state=tk.DISABLED)
        self.record_button.configure(state=tk.DISABLED)
        self.status_var.set("正在连接摄像头…")
        self.worker.start(url)

    def process_frame(self, frame):
        """
        目标识别扩展入口。

        后续接入 YOLO 等模型时，在这里执行推理并把检测框画到 frame 上。
        """
        return frame

    def _update_ui(self) -> None:
        self._consume_status_messages()

        try:
            frame_time, frame = self.frame_queue.get_nowait()
            self.last_frame_time = frame_time
            self.current_frame = frame

            processed = self.process_frame(frame.copy())
            if self.recording:
                self._write_recording_frame(processed)

            self._display_frame(processed)
            self._update_fps(frame_time, processed)
        except queue.Empty:
            pass

        self.after(20, self._update_ui)

    def _consume_status_messages(self) -> None:
        while True:
            try:
                event, data = self.status_queue.get_nowait()
            except queue.Empty:
                break

            if event == "status":
                self.status_var.set(str(data))
            elif event == "connected":
                width = data["width"]
                height = data["height"]
                fps = data["fps"]
                self.status_var.set(f"连接成功：{width} × {height}，源帧率 {fps:.1f}")
                self.snapshot_button.configure(state=tk.NORMAL)
                self.record_button.configure(state=tk.NORMAL)

    def _display_frame(self, frame) -> None:
        panel_width = max(self.video_panel.winfo_width(), 2)
        panel_height = max(self.video_panel.winfo_height(), 2)
        frame_height, frame_width = frame.shape[:2]
        scale = min(panel_width / frame_width, panel_height / frame_height)

        display_width = max(int(frame_width * scale), 1)
        display_height = max(int(frame_height * scale), 1)
        resized = cv2.resize(
            frame,
            (display_width, display_height),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
        )
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        self.current_photo = ImageTk.PhotoImage(image=image)
        self.video_panel.configure(image=self.current_photo, text="")

    def _update_fps(self, frame_time: float, frame) -> None:
        self.frame_times.append(frame_time)
        cutoff = frame_time - 1.0
        self.frame_times = [timestamp for timestamp in self.frame_times if timestamp >= cutoff]
        fps = max(len(self.frame_times) - 1, 0)
        height, width = frame.shape[:2]
        recording_text = "　● 录像中" if self.recording else ""
        self.info_var.set(f"{width} × {height}　{fps} FPS{recording_text}")

    def save_snapshot(self) -> None:
        if self.current_frame is None:
            return

        filename = datetime.now().strftime("capture_%Y%m%d_%H%M%S.jpg")
        path = CAPTURE_DIR / filename
        if cv2.imwrite(str(path), self.current_frame):
            self.status_var.set(f"截图已保存：{path.name}")
        else:
            messagebox.showerror("保存失败", "无法保存截图。")

    def toggle_recording(self) -> None:
        if self.current_frame is None:
            return
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        height, width = self.current_frame.shape[:2]
        filename = datetime.now().strftime("record_%Y%m%d_%H%M%S.mp4")
        self.recording_path = RECORD_DIR / filename
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self.video_writer = cv2.VideoWriter(
            str(self.recording_path), fourcc, 25.0, (width, height)
        )

        if not self.video_writer.isOpened():
            self.video_writer.release()
            self.video_writer = None
            messagebox.showerror("录像失败", "无法创建录像文件。")
            return

        self.recording = True
        self.record_button.configure(text="停止录像")
        self.status_var.set(f"正在录像：{self.recording_path.name}")

    def _write_recording_frame(self, frame) -> None:
        if self.video_writer is not None:
            self.video_writer.write(frame)

    def _stop_recording(self) -> None:
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None

        if self.recording and self.recording_path:
            self.status_var.set(f"录像已保存：{self.recording_path.name}")

        self.recording = False
        self.recording_path = None
        self.record_button.configure(text="开始录像")

    def open_capture_dir(self) -> None:
        os.startfile(CAPTURE_DIR)

    def _on_close(self) -> None:
        self._stop_recording()
        self.worker.stop()
        self.destroy()


if __name__ == "__main__":
    CameraViewer().mainloop()

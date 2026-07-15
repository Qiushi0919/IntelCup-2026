from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import sys
import threading
import time
from typing import Any

from PyQt5.QtCore import (
    QObject,
    QProcess,
    QProcessEnvironment,
    QThread,
    QTimer,
    pyqtSignal,
)

from inspection_log import InspectionLogStore


GROUND_STATION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = GROUND_STATION_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
INSPECTION_PACKAGE_ROOT = PROJECT_ROOT
QWEN_MODEL_DIR = WORKSPACE_ROOT / "models" / "qwen3-vl-2b-instruct-int4"
QWEN_WORKER = GROUND_STATION_DIR / "inspection_qwen_worker.py"
QWEN_PYTHON = Path.home() / ".conda" / "envs" / "gluon" / "python.exe"

if str(INSPECTION_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(INSPECTION_PACKAGE_ROOT))


class InspectionVisionThread(QThread):
    result_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._latest_frame = None
        self._frame_sequence = 0
        self._stop_requested = False

    def submit_frame(self, frame) -> None:
        if frame is None:
            return
        with self._lock:
            self._latest_frame = frame.copy()
            self._frame_sequence += 1

    def stop(self) -> None:
        self._stop_requested = True
        self.requestInterruption()
        self.wait(8000)

    def run(self) -> None:
        self._stop_requested = False
        engine = None
        try:
            self.status_changed.emit("loading", "正在加载人脸和中英文OCR模型")
            from inspection_demo.detectors import (
                OpenVinoNpuFaceDetector,
                YuNetFaceDetector,
            )
            from inspection_demo.engine import InspectionEngine
            from inspection_demo.model_assets import (
                ensure_yunet_model,
                openvino_npu_face_model,
            )

            try:
                face_detector = OpenVinoNpuFaceDetector(
                    openvino_npu_face_model()
                )
                detector_status = "NPU人脸检测与CPU中英文OCR已启动"
            except Exception as npu_error:
                face_detector = YuNetFaceDetector(ensure_yunet_model())
                detector_status = (
                    "NPU不可用，已回退CPU人脸检测与OCR："
                    f"{type(npu_error).__name__}"
                )
            engine = InspectionEngine(
                face_detector,
                face_interval=0.06,
                ocr_interval=3.0,
                enable_face=True,
                enable_ocr=True,
                enable_fire=False,
            )
            self.status_changed.emit("ready", detector_status)
            consumed_sequence = -1
            while not self._stop_requested:
                with self._lock:
                    sequence = self._frame_sequence
                    frame = (
                        self._latest_frame.copy()
                        if self._latest_frame is not None and sequence != consumed_sequence
                        else None
                    )
                if frame is None:
                    self.msleep(35)
                    continue
                consumed_sequence = sequence
                result = engine.process(frame, time.monotonic())
                self.result_ready.emit(result.to_dict())
                self.msleep(20)
        except Exception as exc:
            self.status_changed.emit(
                "error",
                f"视觉巡检启动失败：{type(exc).__name__}: {exc}",
            )
        finally:
            if engine is not None:
                engine.close()
            self.status_changed.emit("stopped", "视觉巡检已停止")


class InspectionCoordinator(QObject):
    overlay_ready = pyqtSignal(object)
    entry_created = pyqtSignal(object)
    entry_updated = pyqtSignal(object)
    vision_status_changed = pyqtSignal(str, str)
    qwen_status_changed = pyqtSignal(str, str)
    alert_raised = pyqtSignal(str, str)
    diagnostic = pyqtSignal(str, str)

    def __init__(self, log_root: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.store = InspectionLogStore(log_root)
        self.vision_thread = InspectionVisionThread(self)
        self.vision_thread.result_ready.connect(self._on_vision_result)
        self.vision_thread.status_changed.connect(self.vision_status_changed)

        self._active = False
        self._stream_connected = False
        self._latest_frame = None
        self._latest_state: dict[str, Any] = {}
        self._last_event_at = {"人脸": 0.0, "文字": 0.0, "火源": 0.0}
        self._last_text_fingerprint = ""
        self._entries: dict[str, dict[str, Any]] = {
            entry["id"]: entry for entry in self.store.load_entries(limit=120)
        }

        self._qwen_process: QProcess | None = None
        self._qwen_stdout = ""
        self._qwen_stderr = ""
        self._qwen_ready = False
        self._qwen_busy = False
        self._current_request_id = ""
        self._qwen_queue: deque[tuple[dict[str, Any], str]] = deque()

        interval = float(os.environ.get("INTELCUP_QWEN_INTERVAL_SECONDS", "8"))
        self.periodic_timer = QTimer(self)
        self.periodic_timer.setInterval(round(max(3.0, min(60.0, interval)) * 1000))
        self.periodic_timer.timeout.connect(self._request_periodic_analysis)

        self.resource_timer = QTimer(self)
        self.resource_timer.setInterval(5000)
        self.resource_timer.timeout.connect(self._resource_tick)

    @property
    def log_root(self) -> Path:
        return self.store.root

    @property
    def active(self) -> bool:
        return self._active

    def saved_entries(self) -> list[dict[str, Any]]:
        return self.store.load_entries(limit=60)

    def start(self) -> None:
        if self._active:
            return
        self._active = True
        if not self.vision_thread.isRunning():
            self.vision_thread.start()
        self.periodic_timer.start()
        self.resource_timer.start()
        self._ensure_qwen_process()

    def set_stream_connected(self, connected: bool) -> None:
        self._stream_connected = bool(connected)
        if connected and not self._active:
            self.start()

    def stop(self) -> None:
        self._active = False
        self.periodic_timer.stop()
        self.resource_timer.stop()
        if self.vision_thread.isRunning():
            self.vision_thread.stop()
        process = self._qwen_process
        self._qwen_process = None
        self._qwen_ready = False
        self._qwen_busy = False
        if process is not None and process.state() != QProcess.NotRunning:
            process.closeWriteChannel()
            if not process.waitForFinished(1800):
                process.kill()
                process.waitForFinished(1200)

    def submit_frame(self, frame, flight_state: dict[str, Any]) -> None:
        if not self._active or not self._stream_connected or frame is None:
            return
        self._latest_frame = frame.copy()
        self._latest_state = dict(flight_state)
        self.vision_thread.submit_frame(frame)

    def report_fire(self, detection: Any, flight_state: dict[str, Any]) -> None:
        if not self._active or not self._stream_connected:
            return
        now = time.monotonic()
        if now - self._last_event_at["火源"] < 8.0:
            return
        self._last_event_at["火源"] = now
        payload = {
            "kind": "fire",
            "bbox": list(detection.bbox),
            "confidence": float(detection.confidence),
            "text": "",
        }
        summary = f"识别到疑似火源，连续帧置信度 {detection.confidence:.0%}"
        self._create_event("火源", "小模型命中", summary, [payload], flight_state)

    def retry_qwen(self) -> None:
        self._ensure_qwen_process()

    def _on_vision_result(self, result: dict[str, Any]) -> None:
        if not self._active or not self._stream_connected:
            return
        faces = list(result.get("faces", []))
        texts = list(result.get("texts", []))
        self.overlay_ready.emit(faces)
        now = time.monotonic()

        if faces and now - self._last_event_at["人脸"] >= 10.0:
            self._last_event_at["人脸"] = now
            confidence = max(float(item.get("confidence", 0.0)) for item in faces)
            summary = f"识别到 {len(faces)} 张人脸，最高置信度 {confidence:.0%}"
            self._create_event(
                "人脸",
                "小模型命中",
                summary,
                faces,
                self._latest_state,
            )

        recognized = [str(item.get("text", "")).strip() for item in texts]
        recognized = [item for item in recognized if item]
        fingerprint = "|".join(recognized[:8])
        if (
            fingerprint
            and fingerprint != self._last_text_fingerprint
            and now - self._last_event_at["文字"] >= 15.0
        ):
            self._last_text_fingerprint = fingerprint
            self._last_event_at["文字"] = now
            preview = " / ".join(recognized[:4])
            summary = f"识别到中英文文字：{preview}"
            self._create_event(
                "文字",
                "小模型命中",
                summary,
                texts,
                self._latest_state,
            )

    def _create_event(
        self,
        kind: str,
        trigger: str,
        summary: str,
        detections: list[dict[str, Any]],
        flight_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        if self._latest_frame is None:
            return None
        entry = self.store.create_entry(
            kind,
            trigger,
            summary,
            self._latest_frame,
            flight_state,
            detections,
        )
        self._entries[entry["id"]] = entry
        self.entry_created.emit(entry)
        self.alert_raised.emit(kind, summary)
        self._enqueue_qwen(entry, self._event_prompt(entry), priority=True)
        return entry

    def _request_periodic_analysis(self) -> None:
        if (
            not self._active
            or not self._stream_connected
            or not self._qwen_ready
            or self._qwen_busy
            or self._qwen_queue
            or self._latest_frame is None
        ):
            return
        entry = self.store.create_entry(
            "周期巡检",
            "Qwen定时分析",
            "Qwen-VL按计划复核当前图传画面",
            self._latest_frame,
            self._latest_state,
            [],
        )
        self._entries[entry["id"]] = entry
        self.entry_created.emit(entry)
        self._enqueue_qwen(entry, self._periodic_prompt(entry), priority=False)

    def _enqueue_qwen(
        self,
        entry: dict[str, Any],
        prompt: str,
        priority: bool,
    ) -> None:
        item = (entry, prompt)
        if len(self._qwen_queue) >= 24:
            dropped, _dropped_prompt = self._qwen_queue.pop()
            updated = self.store.update_analysis(
                dropped,
                "",
                error="Qwen等待队列已满，请在释放内存后重试",
            )
            self._entries[dropped["id"]] = updated
            self.entry_updated.emit(updated)
        if priority:
            self._qwen_queue.appendleft(item)
        else:
            self._qwen_queue.append(item)
        self._dispatch_qwen()

    def _dispatch_qwen(self) -> None:
        if not self._qwen_ready or self._qwen_busy or not self._qwen_queue:
            return
        if not self._mock_enabled() and self._available_memory_gib() < 0.8:
            self.qwen_status_changed.emit("memory", "内存低于0.8GiB，Qwen任务暂缓")
            return
        entry, prompt = self._qwen_queue.popleft()
        screenshot = str(entry.get("screenshot", ""))
        if not screenshot or not Path(screenshot).exists():
            updated = self.store.update_analysis(entry, "", error="巡检截图不存在")
            self._entries[entry["id"]] = updated
            self.entry_updated.emit(updated)
            return
        process = self._qwen_process
        if process is None or process.state() == QProcess.NotRunning:
            self._qwen_queue.appendleft((entry, prompt))
            self._ensure_qwen_process()
            return
        request = {
            "request_id": entry["id"],
            "image_path": screenshot,
            "prompt": prompt,
        }
        self._qwen_busy = True
        self._current_request_id = entry["id"]
        self.qwen_status_changed.emit("busy", f"Qwen正在分析：{entry['kind']}")
        process.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))

    def _ensure_qwen_process(self) -> None:
        if not self._active:
            return
        if self._qwen_process is not None and self._qwen_process.state() != QProcess.NotRunning:
            return
        if not QWEN_PYTHON.exists() or not QWEN_MODEL_DIR.exists() or not QWEN_WORKER.exists():
            self.qwen_status_changed.emit("error", "Qwen环境、模型或工作进程文件不存在")
            return
        available = self._available_memory_gib()
        if not self._mock_enabled() and available < 1.4:
            self.qwen_status_changed.emit(
                "memory",
                f"等待可用内存达到1.4GiB，当前 {available:.2f}GiB",
            )
            return

        process = QProcess(self)
        process.setProgram(str(QWEN_PYTHON))
        arguments = [
            "-u",
            str(QWEN_WORKER),
            "--model",
            str(QWEN_MODEL_DIR),
            "--device",
            "GPU",
            "--max-image-side",
            "448",
            "--max-new-tokens",
            "48",
        ]
        if self._mock_enabled():
            arguments.append("--mock")
        process.setArguments(arguments)
        process.setWorkingDirectory(str(WORKSPACE_ROOT))
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUTF8", "1")
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_qwen_stdout)
        process.readyReadStandardError.connect(self._read_qwen_stderr)
        process.errorOccurred.connect(self._qwen_process_error)
        process.finished.connect(self._qwen_process_finished)
        self._qwen_process = process
        self._qwen_ready = False
        self.qwen_status_changed.emit("loading", "正在启动Qwen3-VL GPU常驻进程")
        process.start()

    def _read_qwen_stdout(self) -> None:
        process = self._qwen_process
        if process is None:
            return
        self._qwen_stdout += bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        lines = self._qwen_stdout.split("\n")
        self._qwen_stdout = lines.pop()
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self.diagnostic.emit("INFO", f"Qwen输出：{line.strip()}")
                continue
            self._handle_qwen_payload(payload)

    def _handle_qwen_payload(self, payload: dict[str, Any]) -> None:
        payload_type = payload.get("type")
        if payload_type == "status":
            status = str(payload.get("status", "loading"))
            message = str(payload.get("message", "Qwen状态更新"))
            self._qwen_ready = status == "ready"
            self.qwen_status_changed.emit(status, message)
            if self._qwen_ready:
                self._dispatch_qwen()
            return
        if payload_type == "fatal":
            self._qwen_ready = False
            self.qwen_status_changed.emit("error", str(payload.get("message", "Qwen加载失败")))
            return
        if payload_type not in {"result", "error"}:
            return
        request_id = str(payload.get("request_id", self._current_request_id))
        entry = self._entries.get(request_id)
        if entry is not None:
            if payload_type == "result":
                updated = self.store.update_analysis(
                    entry,
                    str(payload.get("text", "")),
                    float(payload.get("elapsed_s", 0.0)),
                )
            else:
                updated = self.store.update_analysis(
                    entry,
                    "",
                    float(payload.get("elapsed_s", 0.0)),
                    error=str(payload.get("message", "Qwen分析失败")),
                )
            self._entries[request_id] = updated
            self.entry_updated.emit(updated)
        self._qwen_busy = False
        self._current_request_id = ""
        self.qwen_status_changed.emit("ready", "Qwen3-VL GPU已就绪")
        self._dispatch_qwen()

    def _read_qwen_stderr(self) -> None:
        process = self._qwen_process
        if process is None:
            return
        self._qwen_stderr += bytes(process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        lines = self._qwen_stderr.split("\n")
        self._qwen_stderr = lines.pop()
        for line in lines[-4:]:
            if line.strip():
                self.diagnostic.emit("INFO", f"Qwen提示：{line.strip()}")

    def _qwen_process_error(self, _error) -> None:
        self._qwen_ready = False
        self._qwen_busy = False
        self.qwen_status_changed.emit("error", "Qwen进程启动失败")

    def _qwen_process_finished(self, exit_code: int, _status) -> None:
        self._qwen_ready = False
        self._qwen_busy = False
        self._qwen_process = None
        if self._active:
            self.qwen_status_changed.emit("error", f"Qwen进程已退出，代码 {exit_code}")

    def _resource_tick(self) -> None:
        if not self._active:
            return
        if self._qwen_process is None or self._qwen_process.state() == QProcess.NotRunning:
            self._ensure_qwen_process()
        elif self._qwen_ready and not self._qwen_busy:
            self._dispatch_qwen()

    @staticmethod
    def _event_prompt(entry: dict[str, Any]) -> str:
        kind = entry.get("kind", "目标")
        summary = entry.get("summary", "")
        instructions = {
            "人脸": "确认画面中是否有人，描述其大致位置和可见安全风险；不要猜测身份、性别或年龄。",
            "文字": "核对画面中文字，给出准确中文或英文内容，并说明它在巡检场景中的含义。",
            "火源": "复核是否存在火源、烟雾或高温风险，说明位置；若只是红色标志物要明确指出。",
        }.get(kind, "描述目标和可能风险，不要猜测看不清的内容。")
        return (
            "你是无人机飞行巡检助手。小模型给出的初步结果是："
            f"{summary}。{instructions}用不超过两句中文回答。"
        )

    @staticmethod
    def _periodic_prompt(entry: dict[str, Any]) -> str:
        state = entry.get("flight_state", {})
        return (
            "你是无人机飞行巡检助手。请检查当前图传画面，重点关注人员、人脸、"
            "中英文文字、火源、烟雾、车辆和其他明显风险。不要猜测看不清的内容。"
            f"当前高度约 {float(state.get('altitude', 0.0)):.2f} 米。"
            "用不超过两句中文给出巡检结论。"
        )

    @staticmethod
    def _available_memory_gib() -> float:
        try:
            import psutil

            return float(psutil.virtual_memory().available) / (1024**3)
        except Exception:
            return 99.0

    @staticmethod
    def _mock_enabled() -> bool:
        return os.environ.get("INTELCUP_QWEN_MOCK", "").strip() == "1"

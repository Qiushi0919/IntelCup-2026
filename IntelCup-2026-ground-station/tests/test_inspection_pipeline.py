from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
from PyQt5.QtCore import QCoreApplication, QEventLoop, QTimer


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GROUND_STATION_DIR = PROJECT_ROOT / "ground_station"
if str(GROUND_STATION_DIR) not in sys.path:
    sys.path.insert(0, str(GROUND_STATION_DIR))

from inspection_log import InspectionLogStore  # noqa: E402
from inspection_service import (  # noqa: E402
    InspectionCoordinator,
    QWEN_MODEL_DIR,
    QWEN_PYTHON,
)


class InspectionPipelineTests(unittest.TestCase):
    def test_append_only_log_can_be_reloaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = InspectionLogStore(Path(directory))
            frame = np.zeros((120, 160, 3), dtype=np.uint8)
            entry = store.create_entry(
                "文字",
                "单元测试",
                "识别到 TEST 测试",
                frame,
                {"x": 35, "y": 35, "altitude": 1.2, "yaw": 20},
                [],
            )
            updated = store.update_analysis(entry, "画面文字为 TEST 测试。", 0.15)

            loaded = store.load_entries()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["id"], updated["id"])
            self.assertEqual(loaded[0]["qwen_status"], "分析完成")
            self.assertTrue(Path(loaded[0]["screenshot"]).exists())
            self.assertEqual(len(store.jsonl_path.read_text("utf-8").splitlines()), 2)

    def test_mock_qwen_worker_uses_json_lines_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            request = {
                "request_id": "demo-1",
                "image_path": str(Path(directory) / "unused.jpg"),
                "prompt": "检查画面",
            }
            completed = subprocess.run(
                [
                    sys.executable,
                    "-u",
                    str(GROUND_STATION_DIR / "inspection_qwen_worker.py"),
                    "--model",
                    directory,
                    "--mock",
                ],
                input=json.dumps(request, ensure_ascii=False) + "\n",
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"},
                capture_output=True,
                check=True,
                timeout=10,
            )
            payloads = [json.loads(line) for line in completed.stdout.splitlines()]
            self.assertEqual(payloads[0]["status"], "ready")
            self.assertEqual(payloads[1]["type"], "result")
            self.assertEqual(payloads[1]["request_id"], "demo-1")

    @unittest.skipUnless(
        QWEN_PYTHON.exists() and QWEN_MODEL_DIR.exists(),
        "Local Qwen runtime is not installed",
    )
    def test_coordinator_persists_mock_qwen_result(self) -> None:
        app = QCoreApplication.instance() or QCoreApplication([])
        previous_mock = os.environ.get("INTELCUP_QWEN_MOCK")
        os.environ["INTELCUP_QWEN_MOCK"] = "1"
        try:
            with tempfile.TemporaryDirectory() as directory:
                coordinator = InspectionCoordinator(Path(directory))
                updates: list[dict] = []
                coordinator.entry_updated.connect(updates.append)
                coordinator.set_stream_connected(True)
                coordinator.submit_frame(
                    np.zeros((120, 160, 3), dtype=np.uint8),
                    {"x": 35, "y": 35, "altitude": 1.2, "yaw": 20},
                )
                coordinator.report_fire(
                    SimpleNamespace(bbox=(20, 30, 40, 50), confidence=0.88),
                    {"x": 35, "y": 35, "altitude": 1.2, "yaw": 20},
                )

                loop = QEventLoop()
                coordinator.entry_updated.connect(lambda _entry: loop.quit())
                QTimer.singleShot(8000, loop.quit)
                loop.exec_()
                coordinator.stop()

                self.assertEqual(len(updates), 1)
                self.assertEqual(updates[0]["qwen_status"], "分析完成")
                loaded = coordinator.store.load_entries()
                self.assertEqual(loaded[0]["qwen_status"], "分析完成")
        finally:
            if previous_mock is None:
                os.environ.pop("INTELCUP_QWEN_MOCK", None)
            else:
                os.environ["INTELCUP_QWEN_MOCK"] = previous_mock
            app.processEvents()


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from flight_log_recorder import FlightLogRecorder
from models import CameraState, DroneState


class FlightLogRecognitionTests(unittest.TestCase):
    def test_recognition_image_and_confidence_are_exported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            recorder = FlightLogRecorder(Path(temp_dir))
            camera = CameraState(connected=True, fps=15.0)
            locked = DroneState(armed=False)
            flying = DroneState(armed=True, x=123.0, y=234.0, altitude=1.2)
            recorder.observe_state(locked, camera, [], [], {})
            recorder.observe_state(flying, camera, [], [], {})
            recorder.update_latest_frame(np.zeros((360, 640, 3), dtype=np.uint8))

            saved = recorder.record_recognition(
                target_type="人脸识别",
                label="lucy",
                confidence=0.934,
                state=flying,
                bbox=(100, 80, 160, 180),
                frame_width=640,
                frame_height=360,
                overlay_label="FACE lucy",
            )
            fire_saved = recorder.record_recognition(
                target_type="火源识别",
                label="火源",
                confidence=0.887,
                state=flying,
                bbox=(280, 140, 100, 100),
                frame_width=640,
                frame_height=360,
                overlay_label="FIRE",
            )

            self.assertTrue(saved)
            self.assertTrue(fire_saved)
            output_path = recorder.export_markdown()
            markdown = output_path.read_text(encoding="utf-8")
            self.assertIn("## 视觉识别结果", markdown)
            self.assertIn("人脸识别 · lucy", markdown)
            self.assertIn("识别置信度：93.4%", markdown)
            self.assertIn("火源识别 · 火源", markdown)
            self.assertIn("识别置信度：88.7%", markdown)
            for recognition in recorder.active.recognition_records:
                image_path = output_path.parent / recognition.image_filename
                self.assertTrue(image_path.exists())
                self.assertIsNotNone(cv2.imread(str(image_path)))


if __name__ == "__main__":
    unittest.main()

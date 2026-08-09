from __future__ import annotations

import sys
import unittest
from pathlib import Path

import cv2
import numpy as np


GROUND_STATION_DIR = Path(__file__).resolve().parents[1]
if str(GROUND_STATION_DIR) not in sys.path:
    sys.path.insert(0, str(GROUND_STATION_DIR))

from ocr_recognition_service import (
    CHARSET_FILE,
    DETECTION_MODEL,
    RECOGNITION_MODEL,
    LocalOCRRecognizer,
)


class OCRRecognitionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recognizer = LocalOCRRecognizer()

    def test_model_assets_are_complete(self) -> None:
        self.assertGreater(DETECTION_MODEL.stat().st_size, 2_000_000)
        self.assertGreater(RECOGNITION_MODEL.stat().st_size, 70_000_000)
        charset = "".join(CHARSET_FILE.read_text(encoding="utf-8").splitlines())
        self.assertEqual(len(charset), 3944)

    def test_detects_and_recognizes_multiple_text_regions(self) -> None:
        frame = np.full((720, 1280, 3), 255, dtype=np.uint8)
        cv2.putText(
            frame,
            "FIRE 123",
            (90, 280),
            cv2.FONT_HERSHEY_SIMPLEX,
            3.0,
            (0, 0, 0),
            7,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "INTEL CUP",
            (90, 500),
            cv2.FONT_HERSHEY_SIMPLEX,
            2.6,
            (0, 0, 0),
            6,
            cv2.LINE_AA,
        )

        matches = self.recognizer.recognize(frame)
        texts = {match.text for match in matches}
        self.assertIn("FIRE123", texts)
        self.assertIn("INTELCUP", texts)
        for match in matches:
            self.assertGreater(match.confidence, 0.8)
            self.assertEqual(match.frame_width, 1280)
            self.assertEqual(match.frame_height, 720)
            for x, y in match.polygon:
                self.assertGreaterEqual(x, 0)
                self.assertLess(x, 1280)
                self.assertGreaterEqual(y, 0)
                self.assertLess(y, 720)


if __name__ == "__main__":
    unittest.main()

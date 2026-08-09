from __future__ import annotations

import sys
import unittest
from pathlib import Path

import cv2


GROUND_STATION_DIR = Path(__file__).resolve().parents[1]
if str(GROUND_STATION_DIR) not in sys.path:
    sys.path.insert(0, str(GROUND_STATION_DIR))

from face_recognition_service import ASSET_DIR, LocalFaceRecognizer


class FaceRecognitionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.recognizer = LocalFaceRecognizer()

    def _recognize_reference(self, filename: str):
        frame = cv2.imread(str(ASSET_DIR / filename))
        self.assertIsNotNone(frame)
        matches = self.recognizer.recognize(frame)
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_lucy_reference_is_recognized(self) -> None:
        match = self._recognize_reference("lucy.png")
        self.assertEqual(match.name, "Lucy")
        self.assertTrue(match.matched)
        self.assertGreaterEqual(match.confidence, 0.95)

    def test_mark_reference_is_recognized(self) -> None:
        match = self._recognize_reference("mark.jpg")
        self.assertEqual(match.name, "Mark")
        self.assertTrue(match.matched)
        self.assertGreaterEqual(match.confidence, 0.95)

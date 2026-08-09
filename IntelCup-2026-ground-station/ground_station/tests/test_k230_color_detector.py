from __future__ import annotations

import sys
import unittest
from pathlib import Path

import cv2
import numpy as np


GROUND_STATION_DIR = Path(__file__).resolve().parents[1]
if str(GROUND_STATION_DIR) not in sys.path:
    sys.path.insert(0, str(GROUND_STATION_DIR))

from k230_color_detector import (  # noqa: E402
    K230RedBlobDetector,
    RedBlobConfirmationTracker,
)


class K230ColorDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = K230RedBlobDetector()
        self.large_red_frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.rectangle(
            self.large_red_frame,
            (240, 120),
            (400, 280),
            (0, 0, 255),
            -1,
        )

    def test_large_red_blob_is_detected(self) -> None:
        detections = self.detector.detect(self.large_red_frame)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].kind, "k230_red_blob")
        self.assertGreater(detections[0].area, 20_000)

    def test_small_red_blob_is_ignored(self) -> None:
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.rectangle(frame, (300, 170), (320, 190), (0, 0, 255), -1)
        self.assertEqual(self.detector.detect(frame), [])

    def test_confirmation_occurs_only_on_frame_twenty(self) -> None:
        tracker = RedBlobConfirmationTracker(required_frames=20)
        for expected_frame in range(1, 20):
            detections = self.detector.detect(self.large_red_frame)
            self.assertIsNone(tracker.update(detections))
            self.assertEqual(detections[0].consecutive_frames, expected_frame)
            self.assertFalse(detections[0].confirmed)

        detections = self.detector.detect(self.large_red_frame)
        confirmed = tracker.update(detections)
        self.assertIsNotNone(confirmed)
        self.assertEqual(confirmed.consecutive_frames, 20)
        self.assertTrue(confirmed.confirmed)

    def test_missing_frame_resets_confirmation_count(self) -> None:
        tracker = RedBlobConfirmationTracker(required_frames=20)
        for _ in range(12):
            tracker.update(self.detector.detect(self.large_red_frame))
        tracker.update([])

        detections = self.detector.detect(self.large_red_frame)
        self.assertIsNone(tracker.update(detections))
        self.assertEqual(detections[0].consecutive_frames, 1)

    def test_confirmed_blob_remains_available_after_first_notification(self) -> None:
        tracker = RedBlobConfirmationTracker(required_frames=20)
        for _ in range(20):
            tracker.update(self.detector.detect(self.large_red_frame))

        detections = self.detector.detect(self.large_red_frame)
        self.assertIsNone(tracker.update(detections))
        self.assertTrue(detections[0].confirmed)
        self.assertEqual(detections[0].consecutive_frames, 21)


if __name__ == "__main__":
    unittest.main()

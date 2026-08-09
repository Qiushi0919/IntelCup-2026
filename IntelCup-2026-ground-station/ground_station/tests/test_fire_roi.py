import unittest

from models import (
    bbox_inside_center_roi,
    FireDetection,
    fire_detection_inside_center_roi,
)


def detection(bbox):
    x, y, width, height = bbox
    return FireDetection(
        bbox=bbox,
        confidence=0.95,
        area=float(width * height),
        center_x=x + width // 2,
        center_y=y + height // 2,
        frame_width=1000,
        frame_height=800,
        consecutive_frames=20,
        required_frames=20,
        confirmed=True,
    )


class FireRoiTests(unittest.TestCase):
    def test_blob_fully_inside_center_roi_is_accepted(self):
        self.assertTrue(fire_detection_inside_center_roi(detection((300, 240, 300, 240))))

    def test_blob_crossing_roi_edge_is_rejected(self):
        self.assertFalse(fire_detection_inside_center_roi(detection((200, 240, 100, 200))))

    def test_blob_on_roi_boundary_is_accepted(self):
        self.assertTrue(fire_detection_inside_center_roi(detection((250, 200, 500, 400))))

    def test_face_box_uses_the_same_center_roi(self):
        self.assertTrue(bbox_inside_center_roi((300, 250, 200, 200), 1000, 800))
        self.assertFalse(bbox_inside_center_roi((200, 250, 200, 200), 1000, 800))


if __name__ == "__main__":
    unittest.main()

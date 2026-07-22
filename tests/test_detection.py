import unittest
from importlib.util import find_spec

HAS_OPENCV = find_spec("cv2") is not None and find_spec("numpy") is not None
if HAS_OPENCV:
    import cv2
    import numpy as np
    from a075_bridge.detection import DetectorSettings, find_fuel


@unittest.skipUnless(HAS_OPENCV, "OpenCV and NumPy are not installed")
class DetectionTests(unittest.TestCase):
    def test_detects_yellow_circle(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 50, (0, 255, 255), -1)
        boxes = find_fuel(frame, DetectorSettings())
        self.assertEqual(1, len(boxes))
        x, y, width, height = boxes[0]
        self.assertLess(x, 320)
        self.assertGreater(x + width, 320)
        self.assertLess(y, 240)
        self.assertGreater(y + height, 240)

    def test_ignores_non_yellow_circle(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 50, (255, 0, 0), -1)
        self.assertEqual([], find_fuel(frame, DetectorSettings()))

    def test_detects_washed_out_ball_across_fov(self):
        settings = DetectorSettings(
            hue_low=4,
            hue_high=42,
            saturation_low=45,
            value_low=55,
            min_circularity=0.72,
        )
        for center in ((45, 45), (320, 45), (595, 45), (45, 435), (320, 240), (595, 435)):
            with self.subTest(center=center):
                frame = np.full((480, 640, 3), (75, 110, 140), dtype=np.uint8)
                cv2.circle(frame, center, 35, (75, 180, 240), -1)
                self.assertEqual(1, len(find_fuel(frame, settings)))

    def test_ignores_warm_background_and_skin_tones(self):
        settings = DetectorSettings(
            hue_low=4,
            hue_high=42,
            saturation_low=45,
            value_low=55,
            min_circularity=0.72,
        )
        frame = np.full((480, 640, 3), (75, 110, 140), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 50, (80, 115, 155), -1)
        self.assertEqual([], find_fuel(frame, settings))

    def test_marker_line_does_not_split_ball(self):
        settings = DetectorSettings(
            hue_low=4,
            hue_high=42,
            saturation_low=45,
            value_low=55,
            min_circularity=0.72,
        )
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 55, (75, 180, 240), -1)
        cv2.line(frame, (285, 230), (355, 250), (30, 30, 30), 4)
        self.assertEqual(1, len(find_fuel(frame, settings)))


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

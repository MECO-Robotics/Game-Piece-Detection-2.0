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

    def test_splits_two_touching_balls_at_same_depth(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (280, 240), 55, (75, 180, 240), -1)
        cv2.circle(frame, (380, 240), 55, (75, 180, 240), -1)
        depth = np.full((240, 320), 100, dtype=np.uint8)

        boxes = find_fuel(frame, DetectorSettings(), depth)

        self.assertEqual(2, len(boxes))
        centers = sorted(x + width // 2 for x, _, width, _ in boxes)
        self.assertLess(centers[0], 320)
        self.assertGreater(centers[1], 320)

    def test_splits_uneven_overlapping_balls_without_depth(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (290, 240), 40, (75, 180, 240), -1)
        cv2.circle(frame, (346, 225), 34, (75, 180, 240), -1)

        self.assertEqual(2, len(find_fuel(frame, DetectorSettings())))

    def test_splits_three_touching_balls(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for center in ((265, 255), (375, 255), (320, 160)):
            cv2.circle(frame, center, 58, (75, 180, 240), -1)
        depth = np.full((240, 320), 100, dtype=np.uint8)

        self.assertEqual(3, len(find_fuel(frame, DetectorSettings(), depth)))

    def test_has_no_small_candidate_limit(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for row in range(10):
            for column in range(10):
                cv2.circle(
                    frame,
                    (100 + column * 40, 50 + row * 40),
                    20,
                    (75, 180, 240),
                    -1,
                )
        depth = np.full((240, 320), 100, dtype=np.uint8)

        self.assertEqual(
            100,
            len(find_fuel(frame, DetectorSettings(min_area_px=80), depth)),
        )

    def test_depth_discontinuity_splits_overlapping_balls(self):
        settings = DetectorSettings(split_peak_ratio=0.90, depth_split_threshold=12)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (295, 240), 60, (75, 180, 240), -1)
        cv2.circle(frame, (365, 240), 60, (75, 180, 240), -1)
        depth = np.full((240, 320), 140, dtype=np.uint8)
        cv2.circle(depth, (147, 120), 30, 80, -1)
        cv2.circle(depth, (182, 120), 30, 115, -1)

        boxes = find_fuel(frame, settings, depth)

        self.assertEqual(2, len(boxes))

    def test_smooth_depth_on_one_ball_does_not_split_it(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(frame, (320, 240), 60, (75, 180, 240), -1)
        yy, xx = np.indices((240, 320))
        radius = np.sqrt((xx - 160) ** 2 + (yy - 120) ** 2)
        depth = np.where(radius <= 30, 90 + radius.astype(np.uint8) // 3, 140).astype(
            np.uint8
        )

        self.assertEqual(1, len(find_fuel(frame, DetectorSettings(), depth)))


if __name__ == "__main__":
    unittest.main()

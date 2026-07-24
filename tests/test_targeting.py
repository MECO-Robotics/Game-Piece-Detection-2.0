import unittest
from importlib.util import find_spec

HAS_OPENCV = find_spec("cv2") is not None and find_spec("numpy") is not None
if HAS_OPENCV:
    import numpy as np

    from a075_bridge.targeting import (
        build_detection_frame,
        decode_detection_frame,
        encode_detection_frame,
        unavailable_frame,
    )


@unittest.skipUnless(HAS_OPENCV, "OpenCV and NumPy are not installed")
class TargetingTests(unittest.TestCase):
    def test_normalizes_box_and_includes_depth(self):
        depth = np.full((240, 320), 75, dtype=np.uint8)

        frame = build_detection_frame(
            "left",
            12,
            [(288, 216, 64, 48)],
            640,
            480,
            depth,
            source_time_seconds=3.5,
        )

        self.assertEqual(1, len(frame.targets))
        target = frame.targets[0]
        self.assertAlmostEqual(0.0, target.center_x)
        self.assertAlmostEqual(0.0, target.center_y)
        self.assertAlmostEqual(0.1, target.width)
        self.assertAlmostEqual(0.1, target.height)
        self.assertAlmostEqual(0.01, target.area)
        self.assertEqual(75.0, target.depth_raw)

    def test_round_trips_message(self):
        original = build_detection_frame(
            "right",
            9,
            [(0, 0, 64, 48)],
            640,
            480,
            None,
            source_time_seconds=1.25,
        )

        self.assertEqual(original, decode_detection_frame(encode_detection_frame(original)))

    def test_unavailable_frame_has_no_targets(self):
        frame = unavailable_frame("left", 4, source_time_seconds=2.0)

        self.assertFalse(frame.camera_connected)
        self.assertEqual((), frame.targets)


if __name__ == "__main__":
    unittest.main()

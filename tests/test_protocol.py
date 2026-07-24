import struct
import unittest

from a075_bridge.protocol import CONFIG_FORMAT, FrameDecodeError, decode_frame, encode_config


class ProtocolTests(unittest.TestCase):
    def test_decode_extracts_jpeg(self):
        jpeg = b"\xff\xd8camera-jpeg\xff\xd9"
        depth_image = bytes(range(256)) * 300
        ir_and_status = bytes(320 * 240 * 2)
        depth = depth_image + ir_and_status
        frame = (
            struct.pack("<QQ", 42, 1234)
            + encode_config()
            + struct.pack("<ii", len(depth), len(jpeg))
            + depth
            + jpeg
        )
        decoded = decode_frame(frame)
        self.assertEqual(42, decoded.frame_id)
        self.assertEqual(1234, decoded.timestamp_ms)
        self.assertEqual(jpeg, decoded.jpeg)
        self.assertEqual(depth_image, decoded.depth)
        self.assertEqual(320, decoded.depth_width)
        self.assertEqual(240, decoded.depth_height)
        self.assertEqual(1, decoded.depth_bytes_per_pixel)

    def test_rejects_truncated_frame(self):
        with self.assertRaises(FrameDecodeError):
            decode_frame(b"short")

    def test_rejects_non_jpeg_rgb_mode(self):
        config = struct.pack(CONFIG_FORMAT, 1, 1, 255, 1, 2, 7, 0, 0, 0)
        frame = struct.pack("<QQ", 1, 2) + config + struct.pack("<ii", 0, 4) + b"nope"
        with self.assertRaises(FrameDecodeError):
            decode_frame(frame)

    def test_rejects_short_depth_payload(self):
        jpeg = b"\xff\xd8jpeg\xff\xd9"
        depth = bytes(100)
        frame = (
            struct.pack("<QQ", 1, 2)
            + encode_config()
            + struct.pack("<ii", len(depth), len(jpeg))
            + depth
            + jpeg
        )
        with self.assertRaises(FrameDecodeError):
            decode_frame(frame)


if __name__ == "__main__":
    unittest.main()

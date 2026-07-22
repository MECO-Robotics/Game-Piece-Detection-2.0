import struct
import unittest

from a075_bridge.protocol import CONFIG_FORMAT, FrameDecodeError, decode_frame, encode_config


class ProtocolTests(unittest.TestCase):
    def test_decode_extracts_jpeg(self):
        jpeg = b"\xff\xd8camera-jpeg\xff\xd9"
        depth = b"depth-and-status"
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

    def test_rejects_truncated_frame(self):
        with self.assertRaises(FrameDecodeError):
            decode_frame(b"short")

    def test_rejects_non_jpeg_rgb_mode(self):
        config = struct.pack(CONFIG_FORMAT, 1, 1, 255, 1, 2, 7, 0, 0, 0)
        frame = struct.pack("<QQ", 1, 2) + config + struct.pack("<ii", 0, 4) + b"nope"
        with self.assertRaises(FrameDecodeError):
            decode_frame(frame)


if __name__ == "__main__":
    unittest.main()

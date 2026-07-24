"""Best-effort transport from isolated camera namespaces to the host."""

from __future__ import annotations

import logging
import socket

from .targeting import DetectionFrame, encode_detection_frame

LOG = logging.getLogger("a075-bridge")


class DetectionSender:
    def __init__(self, socket_path: str | None):
        self.socket_path = socket_path
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._warned_unavailable = False

    def send(self, frame: DetectionFrame) -> None:
        if not self.socket_path:
            return
        try:
            self.socket.sendto(encode_detection_frame(frame), self.socket_path)
            self._warned_unavailable = False
        except (FileNotFoundError, ConnectionRefusedError, OSError) as exc:
            if not self._warned_unavailable:
                LOG.warning(
                    "target publisher unavailable at %s: %s",
                    self.socket_path,
                    exc,
                )
                self._warned_unavailable = True

    def close(self) -> None:
        self.socket.close()

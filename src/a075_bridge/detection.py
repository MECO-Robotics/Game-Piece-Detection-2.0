"""Illumination-tolerant yellow-ball detector for the PhotonVision feed."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DetectorSettings:
    hue_low: int = 4
    hue_high: int = 42
    saturation_low: int = 45
    value_low: int = 55
    lab_yellow_low: int = 158
    yellow_dominance_low: int = 40
    min_area_px: float = 100.0
    min_circularity: float = 0.72


def find_fuel(frame: np.ndarray, settings: DetectorSettings) -> list[tuple[int, int, int, int]]:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    lower = np.array((settings.hue_low, settings.saturation_low, settings.value_low))
    upper = np.array((settings.hue_high, 255, 255))
    mask = cv2.inRange(hsv, lower, upper)

    blue, green, red = cv2.split(frame)
    yellow_dominance = (
        np.minimum(red.astype(np.int16), green.astype(np.int16)) - blue.astype(np.int16)
    )
    chroma_mask = np.where(
        (lab[:, :, 2] >= settings.lab_yellow_low)
        & (yellow_dominance >= settings.yellow_dominance_low),
        255,
        0,
    ).astype(np.uint8)
    mask = cv2.bitwise_and(mask, chroma_mask)

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

    boxes: list[tuple[int, int, int, int]] = []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < settings.min_area_px:
            continue
        # Highlights and marker writing can split the color mask. The convex hull
        # recovers the physical outline instead of scoring each fragment.
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        perimeter = cv2.arcLength(hull, True)
        if perimeter <= 0:
            continue
        circularity = 4.0 * np.pi * hull_area / (perimeter * perimeter)
        x, y, width, height = cv2.boundingRect(hull)
        aspect = width / height if height else 0.0
        if circularity >= settings.min_circularity and 0.6 <= aspect <= 1.5:
            boxes.append((x, y, width, height))
    return sorted(boxes, key=lambda box: box[2] * box[3], reverse=True)


def annotate(frame: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    for index, (x, y, width, height) in enumerate(boxes, start=1):
        cv2.rectangle(frame, (x, y), (x + width, y + height), (255, 0, 255), 2)
        cv2.putText(
            frame,
            f"FUEL {index}",
            (x, max(18, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2,
            cv2.LINE_AA,
        )
    return frame

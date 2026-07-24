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
    split_peak_ratio: float = 0.85
    depth_split_threshold: int = 12
    depth_min_valid_fraction: float = 0.25


def _yellow_mask(frame: np.ndarray, settings: DetectorSettings) -> np.ndarray:
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
    return mask


def _component_cores(binary: np.ndarray, minimum_area: int) -> list[np.ndarray]:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    return [
        np.where(labels == label, 255, 0).astype(np.uint8)
        for label in range(1, count)
        if stats[label, cv2.CC_STAT_AREA] >= minimum_area
    ]


def _geometry_cores(
    component: np.ndarray, settings: DetectorSettings
) -> list[np.ndarray]:
    distance = cv2.distanceTransform(component, cv2.DIST_L2, 5)
    maximum = float(distance.max())
    if maximum < 2.0:
        return []
    peaks = np.where(distance >= maximum * settings.split_peak_ratio, 255, 0).astype(
        np.uint8
    )
    peaks = cv2.morphologyEx(
        peaks,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    return _component_cores(peaks, max(3, int(settings.min_area_px * 0.03)))


def _depth_cores(
    component: np.ndarray, depth: np.ndarray, settings: DetectorSettings
) -> list[np.ndarray]:
    inside = component != 0
    valid = depth > 0
    component_pixels = int(np.count_nonzero(inside))
    if component_pixels == 0:
        return []
    valid_fraction = np.count_nonzero(inside & valid) / component_pixels
    if valid_fraction < settings.depth_min_valid_fraction:
        return []

    values = depth.astype(np.int32)
    edges = np.zeros(component.shape, dtype=np.uint8)

    horizontal = inside[:, :-1] & inside[:, 1:] & valid[:, :-1] & valid[:, 1:]
    horizontal_jump = horizontal & (
        np.abs(values[:, :-1] - values[:, 1:]) >= settings.depth_split_threshold
    )
    edges[:, :-1][horizontal_jump] = 255
    edges[:, 1:][horizontal_jump] = 255

    vertical = inside[:-1, :] & inside[1:, :] & valid[:-1, :] & valid[1:, :]
    vertical_jump = vertical & (
        np.abs(values[:-1, :] - values[1:, :]) >= settings.depth_split_threshold
    )
    edges[:-1, :][vertical_jump] = 255
    edges[1:, :][vertical_jump] = 255

    separated = cv2.bitwise_and(component, cv2.bitwise_not(edges))
    separated = cv2.morphologyEx(
        separated,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    return _component_cores(separated, max(8, int(settings.min_area_px * 0.15)))


def _partition_from_cores(
    component: np.ndarray, cores: list[np.ndarray]
) -> list[np.ndarray]:
    if len(cores) < 2:
        return [component]

    seeds = np.full(component.shape, 255, dtype=np.uint8)
    for core in cores:
        seeds[core != 0] = 0
    _, nearest = cv2.distanceTransformWithLabels(
        seeds, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_CCOMP
    )
    return [
        np.where((component != 0) & (nearest == label), 255, 0).astype(np.uint8)
        for label in range(1, len(cores) + 1)
    ]


def _split_component(
    component: np.ndarray,
    depth: np.ndarray | None,
    settings: DetectorSettings,
) -> list[np.ndarray]:
    geometry_cores = _geometry_cores(component, settings)
    depth_cores = (
        _depth_cores(component, depth, settings)
        if depth is not None and settings.depth_split_threshold > 0
        else []
    )
    # Prefer the evidence that identifies more distinct objects. Geometry handles
    # balls at the same range; depth discontinuities help when balls overlap.
    cores = depth_cores if len(depth_cores) > len(geometry_cores) else geometry_cores
    return _partition_from_cores(component, cores)


def find_fuel(
    frame: np.ndarray,
    settings: DetectorSettings,
    depth: np.ndarray | None = None,
) -> list[tuple[int, int, int, int]]:
    mask = _yellow_mask(frame, settings)
    aligned_depth = None
    if depth is not None:
        aligned_depth = cv2.resize(
            depth, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_NEAREST
        )

    boxes: list[tuple[int, int, int, int]] = []
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    segments: list[np.ndarray] = []
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] < settings.min_area_px:
            continue
        component = np.where(labels == label, 255, 0).astype(np.uint8)
        segments.extend(_split_component(component, aligned_depth, settings))

    for segment in segments:
        contours, _ = cv2.findContours(
            segment, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
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

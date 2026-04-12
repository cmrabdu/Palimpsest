"""Image preprocessing — deskew, binarize, denoise for scanned pages."""

import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def pil_to_cv2(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV format (grayscale)."""
    arr = np.array(image)
    if len(arr.shape) == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return arr


def cv2_to_pil(arr: np.ndarray) -> Image.Image:
    """Convert OpenCV array back to PIL Image."""
    return Image.fromarray(arr)


def deskew(image: np.ndarray) -> np.ndarray:
    """Auto-detect and correct page rotation."""
    # Use Hough line transform to detect dominant angle
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)

    if lines is None:
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Only consider near-horizontal lines (text lines)
        if abs(angle) < 10:
            angles.append(angle)

    if not angles:
        return image

    median_angle = np.median(angles)
    if abs(median_angle) < 0.1:
        return image  # Already straight

    logger.debug(f"Deskewing by {median_angle:.2f}°")
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def binarize(image: np.ndarray) -> np.ndarray:
    """Adaptive binarization for uneven lighting (common with phone scans)."""
    binary = cv2.adaptiveThreshold(
        image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=21, C=10
    )
    return binary


def denoise(image: np.ndarray) -> np.ndarray:
    """Light denoising — preserves text/formula edges."""
    return cv2.fastNlMeansDenoising(image, h=10, templateWindowSize=7, searchWindowSize=21)


def preprocess(
    image: Image.Image,
    do_deskew: bool = True,
    do_binarize: bool = True,
    do_denoise: bool = False,
) -> Image.Image:
    """Full preprocessing pipeline for a single page.

    Args:
        image: Input PIL Image (grayscale).
        do_deskew: Correct page rotation.
        do_binarize: Apply adaptive binarization.
        do_denoise: Apply denoising (only for very noisy scans).

    Returns:
        Preprocessed PIL Image.
    """
    arr = pil_to_cv2(image)

    if do_deskew:
        arr = deskew(arr)

    if do_denoise:
        arr = denoise(arr)

    if do_binarize:
        arr = binarize(arr)

    return cv2_to_pil(arr)

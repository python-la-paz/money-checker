import cv2
import easyocr
import re
import numpy as np
import base64
from bisect import bisect_right

# Precompiled regex patterns
_RE_DIGITS = re.compile(r"^\d{3,}$")
_RE_SINGLE_LETTER = re.compile(r"^[A-Z]$")
_RE_FIND_NUMBERS = re.compile(r"\d+")

# Processing constants
MAX_WIDTH = 1500  # max px width before OCR (saves RAM & CPU proportionally)
MIN_WIDTH = 1500  # min px width – upscale small images for better OCR accuracy

# Restrict OCR charset per region → fewer candidates, faster inference
_ALLOWLIST_SERIAL = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_ALLOWLIST_DENOM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "

# Observed ranges by denomination (letter B)
# Pre-sorted at module load for binary search.
_RAW_RANGES = {
    "10": [
        (67250001, 67700000),
        (69050001, 69500000),
        (69500001, 69950000),
        (69950001, 70400000),
        (70400001, 70850000),
        (70850001, 71300000),
        (76310012, 85139995),
        (86400001, 86850000),
        (90900001, 91350000),
        (91800001, 92250000),
    ],
    "20": [
        (87280145, 91646549),
        (96650001, 97100000),
        (99800001, 100250000),
        (100250001, 100700000),
        (109250001, 109700000),
        (110600001, 111050000),
        (111050001, 111500000),
        (111950001, 112400000),
        (112400001, 112850000),
        (112850001, 113300000),
        (114200001, 114650000),
        (114650001, 115100000),
        (115100001, 115550000),
        (118700001, 119150000),
        (119150001, 119600000),
        (120500001, 120950000),
        (12168910, 12168999),
    ],
    "50": [
        (77100001, 77550000),
        (78000001, 78450000),
        (78900001, 96350000),
        (96350001, 96800000),
        (96800001, 97250000),
        (98150001, 98600000),
        (104900001, 105350000),
        (105350001, 105800000),
        (106700001, 107150000),
        (107600001, 107150000),
        (108050001, 108500000),
        (109400001, 109850000),
    ],
}

# Build sorted arrays + index arrays once at import time
OBSERVED_RANGES: dict[str, list[tuple[int, int]]] = {}
_RANGE_STARTS: dict[str, list[int]] = {}
_RANGE_ENDS: dict[str, list[int]] = {}

for _d, _rs in _RAW_RANGES.items():
    _sorted = sorted(_rs, key=lambda r: r[0])
    OBSERVED_RANGES[_d] = _sorted
    _RANGE_STARTS[_d] = [r[0] for r in _sorted]
    _RANGE_ENDS[_d] = [r[1] for r in _sorted]

VALID_DENOMINATIONS = ("10", "20", "50")  # tuple → faster `in`

DENOMINATION_WORDS = {
    "10": "DIEZ",
    "20": "VEINTE",
    "50": "CINCUENTA",
}

_DENOM_KEYWORDS = frozenset(
    list(DENOMINATION_WORDS.values()) + ["BOLIVIANOS", "BOLIVIANO"]
)


# OCR reader singleton
_reader = None


def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _reader


# Image preprocessing (optimized)
def preprocess_image(image_bytes: bytes):
    """
    Load image from bytes, UP-SCALE if narrower than MIN_WIDTH,
    DOWN-SCALE if wider than MAX_WIDTH, then apply histogram
    equalisation + median blur.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    del nparr  # free raw buffer immediately

    if img is None:
        raise ValueError("Could not decode the image")

    h, w = img.shape[:2]

    # ─ Up-scale small images for better OCR accuracy
    if w < MIN_WIDTH:
        scale = MIN_WIDTH / w
        img = cv2.resize(
            img,
            (MIN_WIDTH, int(h * scale)),
            interpolation=cv2.INTER_CUBIC,
        )
    # ─ Down-scale large images (saves RAM & CPU)
    elif w > MAX_WIDTH:
        scale = MAX_WIDTH / w
        img = cv2.resize(
            img,
            (MAX_WIDTH, int(h * scale)),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.equalizeHist(gray)
    del gray  # free intermediate

    denoised = cv2.medianBlur(enhanced, 3)
    del enhanced

    return img, denoised


# OCR extraction from three regions (optimized)
def extract_text_regions(img_original, img_processed):
    """
    Extract OCR text from three regions using character allowlists
    that restrict the search space and speed up inference.
    """
    height, width = img_processed.shape

    regions = {
        "top_right": {
            "coords": (width // 2, 0, width, height // 3),
            "label": "Top Right",
            "allowlist": _ALLOWLIST_SERIAL,
        },
        "bottom_left": {
            "coords": (0, 2 * height // 3, width // 2, height),
            "label": "Bottom Left",
            "allowlist": _ALLOWLIST_SERIAL,
        },
        "bottom_right": {
            "coords": (width // 2, height // 3, width, height),
            "label": "Bottom Right",
            "allowlist": _ALLOWLIST_DENOM,
        },
    }

    reader = get_reader()
    elements = []

    for region_id, info in regions.items():
        x0, y0, x1, y1 = info["coords"]
        region = img_processed[y0:y1, x0:x1]

        if region.size == 0:
            continue

        results = reader.readtext(
            region,
            detail=1,
            paragraph=False,
            allowlist=info["allowlist"],
        )

        for bbox, text, confidence in results:
            adjusted_bbox = [[p[0] + x0, p[1] + y0] for p in bbox]
            elements.append(
                {
                    "text": text,
                    "confidence": confidence,
                    "bbox": adjusted_bbox,
                    "region": info["label"],
                    "region_id": region_id,
                }
            )

    return elements


# Serial number search
def find_serial_numbers(ocr_elements):
    """
    Find serial numbers in Top Right and Bottom Left using
    precompiled regex patterns.
    """
    results = []
    serial_regions = ("Top Right", "Bottom Left")

    for region in serial_regions:
        region_elems = [e for e in ocr_elements if e["region"] == region]
        numbers = []
        letters = []

        for i, elem in enumerate(region_elems):
            cleaned = (
                elem["text"]
                .replace("O", "0")
                .replace("l", "1")
                .replace("I", "1")
                .upper()
                .strip()
            )
            if _RE_DIGITS.match(cleaned):
                numbers.append({**elem, "index": i, "digits": cleaned})
            if _RE_SINGLE_LETTER.match(cleaned):
                letters.append({**elem, "index": i, "letter": cleaned})

        for num_elem in numbers:
            for let_elem in letters:
                if abs(num_elem["index"] - let_elem["index"]) <= 2:
                    full_code = f"{num_elem['digits']} {let_elem['letter']}"
                    confidence = round(
                        (num_elem["confidence"] + let_elem["confidence"]) / 2 * 100,
                        2,
                    )
                    if confidence > 80:
                        already_exists = any(
                            r["full_code"] == full_code and r["region"] == region
                            for r in results
                        )
                        if not already_exists:
                            results.append(
                                {
                                    "digits": num_elem["digits"],
                                    "letter": let_elem["letter"],
                                    "full_code": full_code,
                                    "confidence": confidence,
                                    "bbox": num_elem["bbox"],
                                    "bbox_digits": num_elem["bbox"],
                                    "bbox_letter": let_elem["bbox"],
                                    "region": region,
                                }
                            )

    return results


# Denomination search
def find_denomination(ocr_elements):
    """
    Find denomination in Bottom Right using precompiled regex
    and frozenset keyword lookup.
    """
    info = {
        "number": None,
        "denomination_text": None,
        "confidence_number": None,
        "confidence_text": None,
        "bbox_number": None,
        "bbox_text": None,
    }

    elems = [e for e in ocr_elements if e["region"] == "Bottom Right"]
    if not elems:
        return info

    # Find denomination number
    for elem in elems:
        cleaned = elem["text"].replace("O", "0").replace("o", "0").strip()
        for num in _RE_FIND_NUMBERS.findall(cleaned):
            if num in VALID_DENOMINATIONS:
                info["number"] = num
                info["confidence_number"] = round(elem["confidence"] * 100, 2)
                info["bbox_number"] = elem["bbox"]
                break
        if info["number"]:
            break

    # Find BOLIVIANOS text
    for elem in elems:
        text_upper = elem["text"].upper().strip()
        if any(kw in text_upper for kw in _DENOM_KEYWORDS):
            info["denomination_text"] = text_upper
            info["confidence_text"] = round(elem["confidence"] * 100, 2)
            info["bbox_text"] = elem["bbox"]
            break

    # Combine if found in separate elements
    if not info["denomination_text"]:
        parts = []
        for elem in elems:
            t = elem["text"].upper().strip()
            if any(kw in t for kw in _DENOM_KEYWORDS):
                parts.append(t)
                if not info["bbox_text"]:
                    info["bbox_text"] = elem["bbox"]
                    info["confidence_text"] = round(elem["confidence"] * 100, 2)
        if parts:
            info["denomination_text"] = " ".join(parts)

    return info


# Range lookup with binary search
def _in_observed_range(denom: str, num: int):
    """O(log n) range check using bisect on pre-sorted start array."""
    starts = _RANGE_STARTS.get(denom)
    ends = _RANGE_ENDS.get(denom)
    if not starts:
        return None

    idx = bisect_right(starts, num) - 1
    if idx >= 0 and starts[idx] <= num <= ends[idx]:
        return (starts[idx], ends[idx])
    return None


# Bill validation
def validate_bill(serials: list, denomination: dict) -> dict:
    """
    Check if the bill is observed using binary search on sorted ranges.
    """
    result = {
        "valid": True,
        "message": "Billete Valido",
        "validation_details": {},
    }

    denom = denomination.get("number")
    if not denom:
        result["message"] = "Denomination not detected; cannot validate range."
        return result

    ranges = OBSERVED_RANGES.get(denom, [])
    if not ranges:
        result["message"] = (
            f"No observed ranges registered for denomination {denom} Bs."
        )
        return result

    for serial in serials:
        letter = serial.get("letter", "").upper()
        digits = serial.get("digits", "")

        if letter != "B":
            result["message"] = (
                f"La validación para la serie {serial['letter']} no aplica."
            )
            continue

        try:
            num_int = int(digits)
        except ValueError:
            result["message"] = (
                f"Serial {serial['full_code']}: could not convert to integer."
            )
            continue

        matched = _in_observed_range(denom, num_int)
        if matched:
            result["valid"] = False
            result["message"] = "Billete observado"
            result["validation_details"] = {
                "serial": serial["full_code"],
                "range": f"[{matched[0]} - {matched[1]}]",
                "denom": denom,
            }
            return result

    return result


# Draw bounding boxes on image
def draw_bounding_boxes(img_original, serials, denomination):
    """
    Draw bounding boxes on the image and return PNG bytes.
    Green = Top Right, Blue = Bottom Left, Red = Denomination.
    """
    img = img_original.copy()

    colors = {
        "Top Right": (0, 255, 0),  # green BGR
        "Bottom Left": (255, 100, 0),  # blue BGR
    }

    # Serial numbers
    for serial in serials:
        color = colors.get(serial["region"], (0, 255, 0))

        bbox_num = np.array(serial["bbox_digits"])
        bbox_let = np.array(serial["bbox_letter"])
        x_min = int(min(np.min(bbox_num[:, 0]), np.min(bbox_let[:, 0])))
        y_min = int(min(np.min(bbox_num[:, 1]), np.min(bbox_let[:, 1])))
        x_max = int(max(np.max(bbox_num[:, 0]), np.max(bbox_let[:, 0])))
        y_max = int(max(np.max(bbox_num[:, 1]), np.max(bbox_let[:, 1])))

        cv2.rectangle(img, (x_min, y_min), (x_max, y_max), color, 3)
        cv2.putText(
            img,
            f"Serial: {serial['full_code']}",
            (x_min, y_min - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
        )

    # Denomination
    denom_bboxes = []
    if denomination.get("bbox_number"):
        denom_bboxes.append(np.array(denomination["bbox_number"]))
    if denomination.get("bbox_text"):
        denom_bboxes.append(np.array(denomination["bbox_text"]))

    if denom_bboxes:
        all_pts = np.vstack(denom_bboxes)
        x_min = int(np.min(all_pts[:, 0]))
        y_min = int(np.min(all_pts[:, 1]))
        x_max = int(np.max(all_pts[:, 0]))
        y_max = int(np.max(all_pts[:, 1]))
        denom_color = (0, 0, 255)  # red BGR
        cv2.rectangle(img, (x_min, y_min), (x_max, y_max), denom_color, 3)
        label = f"Bs {denomination.get('number', '?')}"
        cv2.putText(
            img,
            label,
            (x_min, y_min - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            denom_color,
            2,
        )

    _, buffer = cv2.imencode(".png", img)
    return buffer.tobytes()


# Main analysis pipeline
def analyze_bill(image_bytes: bytes) -> dict:
    """
    Full pipeline: preprocess → OCR → detect serial + denomination
    → validate range → generate annotated image.
    """
    img_original, img_processed = preprocess_image(image_bytes)

    elements = extract_text_regions(img_original, img_processed)
    del img_processed  # free grayscale array after OCR

    serials = find_serial_numbers(elements)
    denomination = find_denomination(elements)

    validation = validate_bill(serials, denomination)

    annotated_bytes = draw_bounding_boxes(img_original, serials, denomination)
    del img_original  # free original after annotation

    img_base64 = base64.b64encode(annotated_bytes).decode("utf-8")
    del annotated_bytes

    return {
        "serials": [
            {
                "full_code": s["full_code"],
                "digits": s["digits"],
                "letter": s["letter"],
                "region": s["region"],
                "confidence_percent": s["confidence"],
            }
            for s in serials
        ],
        "denomination": {
            "number": denomination["number"],
            "text": denomination["denomination_text"],
            "confidence_number": denomination["confidence_number"],
            "confidence_text": denomination["confidence_text"],
        },
        "validation": validation,
        "annotated_image_base64": img_base64,
    }

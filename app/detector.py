import cv2
import easyocr
import re
import numpy as np
import base64

# Observed ranges by denomination for 'B' series
# Format: { denomination: [(range_start, range_end), ...] }
OBSERVED_RANGES = {
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

VALID_DENOMINATIONS = ["10", "20", "50"]

DENOMINATION_WORDS = {
    "10": "DIEZ",
    "20": "VEINTE",
    "50": "CINCUENTA",
}


# OCR reader singleton
_reader = None


def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


# Image preprocessing
def preprocess_image(image_bytes: bytes):
    """Load image from bytes and apply OCR preprocessing."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode the image")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.equalizeHist(gray)
    denoised = cv2.medianBlur(enhanced, 3)
    return img, denoised


# OCR extraction from three regions
def extract_text_regions(img_original, img_processed):
    """
    Extract OCR text from three regions of the banknote:
      - Top Right:     serial number + letter
      - Bottom Left:   serial number + letter
      - Bottom Right:  large denomination number + BOLIVIANOS text
    """
    height, width = img_processed.shape

    regions = {
        "top_right": {
            "coords": (width // 2, 0, width, height // 3),
            "label": "Top Right",
        },
        "bottom_left": {
            "coords": (0, 2 * height // 3, width // 2, height),
            "label": "Bottom Left",
        },
        "bottom_right": {
            "coords": (width // 2, height // 3, width, height),
            "label": "Bottom Right",
        },
    }

    reader = get_reader()
    elements = []

    for region_id, info in regions.items():
        x0, y0, x1, y1 = info["coords"]
        region = img_processed[y0:y1, x0:x1]

        if region.size == 0:
            continue

        results = reader.readtext(region, detail=1, paragraph=False)

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
    Find serial numbers (digits + letter) in Top Right and Bottom Left
    by matching separate OCR elements (number in one element, letter in another).
    """
    results = []
    serial_regions = ["Top Right", "Bottom Left"]

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
            if re.match(r"^\d{3,}$", cleaned):
                numbers.append({**elem, "index": i, "digits": cleaned})
            if re.match(r"^[A-Z]$", cleaned):
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
                                    "confidence": round(
                                        (
                                            num_elem["confidence"]
                                            + let_elem["confidence"]
                                        )
                                        / 2
                                        * 100,
                                        2,
                                    ),
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
    Find denomination in Bottom Right:
      - Large number (10, 20, 50)
      - Text "DIEZ/VEINTE/CINCUENTA BOLIVIANOS"
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
        for num in re.findall(r"\d+", cleaned):
            if num in VALID_DENOMINATIONS:
                info["number"] = num
                info["confidence_number"] = round(elem["confidence"] * 100, 2)
                info["bbox_number"] = elem["bbox"]
                break
        if info["number"]:
            break

    # Find BOLIVIANOS text
    keywords = list(DENOMINATION_WORDS.values()) + ["BOLIVIANOS", "BOLIVIANO"]
    for elem in elems:
        text_upper = elem["text"].upper().strip()
        if any(kw in text_upper for kw in keywords):
            info["denomination_text"] = text_upper
            info["confidence_text"] = round(elem["confidence"] * 100, 2)
            info["bbox_text"] = elem["bbox"]
            break

    # Combine if found in separate elements
    if not info["denomination_text"]:
        parts = []
        for elem in elems:
            t = elem["text"].upper().strip()
            if any(kw in t for kw in keywords):
                parts.append(t)
                if not info["bbox_text"]:
                    info["bbox_text"] = elem["bbox"]
                    info["confidence_text"] = round(elem["confidence"] * 100, 2)
        if parts:
            info["denomination_text"] = " ".join(parts)

    return info


# Bill validation (observed range check)
def validate_bill(serials: list, denomination: dict) -> dict:
    """
    Check if the bill is observed:
      - Serial letter must be 'B'
      - Serial number must fall within the observed range for the denomination
    Only stores the matched range detail (not every range checked).
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

        matched_range = None
        for range_start, range_end in ranges:
            if range_start <= num_int <= range_end:
                matched_range = (range_start, range_end)
                break

        if matched_range:
            result["valid"] = False
            result["message"] = "Billete observado"
            result["validation_details"] = {
                "serial": serial["full_code"],
                "range": f"[{matched_range[0]} - {matched_range[1]}]",
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
    Full pipeline: preprocess -> OCR -> detect serial + denomination
    -> validate range -> generate annotated image.
    Returns a dictionary with all relevant information.
    """
    img_original, img_processed = preprocess_image(image_bytes)

    elements = extract_text_regions(img_original, img_processed)

    serials = find_serial_numbers(elements)
    denomination = find_denomination(elements)

    validation = validate_bill(serials, denomination)

    annotated_bytes = draw_bounding_boxes(img_original, serials, denomination)
    img_base64 = base64.b64encode(annotated_bytes).decode("utf-8")

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

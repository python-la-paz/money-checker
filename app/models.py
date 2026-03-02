"""
Pydantic models for the Bolivian banknote detection API.
"""

from pydantic import BaseModel
from typing import Optional


class DetectedSerial(BaseModel):
    full_code: str
    digits: str
    letter: str
    region: str
    confidence_percent: float


class DetectedDenomination(BaseModel):
    number: Optional[str] = None
    text: Optional[str] = None
    confidence_number: Optional[float] = None
    confidence_text: Optional[float] = None


class Validation(BaseModel):
    valid: bool
    message: str
    validation_details: list[str]


class OCRElement(BaseModel):
    text: str
    confidence: float
    region: str


class AnalysisResponse(BaseModel):
    serials: list[DetectedSerial]
    denomination: DetectedDenomination
    validation: Validation
    annotated_image_base64: str


class RangeInput(BaseModel):
    denomination: str
    range_start: int
    range_end: int

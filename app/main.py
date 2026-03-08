import copy
import asyncio
import requests
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime
from .database import Database
from .metadata import MetadataExtractor
from .logger import logger
from .detector import analyze_bill, preload_model

app = FastAPI(title='Verificador de Serie "B"', version="1.0.0")

# Thread pool for CPU-bound OCR work (sized for 1.3 CPU limit)
_ocr_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")

# File upload configuration
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB in bytes
API_DETECTOR_URL = os.getenv("API_DETECTOR_URL", None)
# Initialize database
db = Database()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Metadata extractor
metadata_extractor = MetadataExtractor()


@app.on_event("startup")
async def startup_event():
    """Initialize database connection and preload OCR model on startup"""
    await db.connect()
    logger.info("Database connected")
    # Preload EasyOCR model in background thread so first request is fast
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(_ocr_pool, preload_model)
    logger.info("OCR model preloaded")


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection on shutdown"""
    await db.disconnect()
    logger.info("Database disconnected")


@app.get("/", response_class=HTMLResponse)
async def get_landing():
    """Serve the landing page"""
    return open("app/templates/index.html", "r", encoding="utf-8").read()


@app.get("/disclaimer", response_class=HTMLResponse)
async def get_disclaimer():
    """Serve the disclaimer page"""
    return open("app/templates/disclaimer.html", "r", encoding="utf-8").read()


@app.get("/about", response_class=HTMLResponse)
async def get_about():
    """Serve the about page"""
    return open("app/templates/about.html", "r", encoding="utf-8").read()


@app.post("/api/upload-photo")
async def upload_photo(request: Request, file: UploadFile = File(...)):
    """
    Upload a photo and store metadata

    Extracts metadata including:
    - IP address (considering proxy headers)
    - Geolocation
    - File information
    - Timestamp
    """
    try:
        # Read file contents
        contents = await file.read()

        # Validate file size (max 1 MB)
        if len(contents) > MAX_FILE_SIZE:
            file_size_mb = len(contents) / (1024 * 1024)
            return {
                "status": "error",
                "message": f"El archivo es demasiado grande ({file_size_mb:.2f} MB). El tamaño máximo permitido es 1 MB",
            }, 400

        # Extract metadata from request
        metadata = await metadata_extractor.extract(request, file)

        logger.info(f"Photo upload from {metadata['ip_address']}")

        # Save file
        file_path = os.path.join("uploads", metadata["filename"])
        os.makedirs("uploads", exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(contents)
            metadata["file_size"] = len(contents)
        # logic to analyze image  and return JSON to storage results and send to frontend for display
        if API_DETECTOR_URL:
            try:
                response = requests.post(
                    API_DETECTOR_URL,
                    files={"file": (metadata["filename"], contents, file.content_type)},
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
            except requests.RequestException as e:
                logger.error(f"Error calling API Detector: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error calling API Detector: {str(e)}",
                )
        else:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(_ocr_pool, analyze_bill, contents)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error processing the image: {str(e)}",
                )
        # Example response structure
        # {
        #  "serials": [
        #    {
        #      "full_code": "string",
        #      "digits": "string",
        #      "letter": "string",
        #      "region": "string",
        #      "confidence_percent": 0
        #    }
        #  ],
        #  "denomination": {
        #    "number": "string",
        #    "text": "string",
        #    "confidence_number": 0,
        #    "confidence_text": 0
        #  },
        #  "validation": {
        #          "valid": false,
        #          "message": "Billete observado",
        #          "validation_details": {
        #            "serial": "012168910 B",
        #            "range": "[12168910 - 12168999]",
        #            "denom": "20"
        #          }
        #  },
        #  "annotated_image_base64": "string"
        # }
        result_storage = copy.deepcopy(result)
        del result_storage["annotated_image_base64"]
        metadata["analysis_result"] = result_storage
        metadata["api_used"] = bool(API_DETECTOR_URL)
        # Store in MongoDB
        await db.save_upload(metadata)
        result["status"] = "success"
        return result

    except Exception as e:
        logger.error(f"Error uploading photo: {str(e)}")
        return {"status": "error", "message": str(e)}, 500


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from datetime import datetime
from typing import Optional, Dict
import httpx
from .database import Database
from .metadata import MetadataExtractor
from .logger import logger
from .detector import analyze_bill, OBSERVED_RANGES
from .models import AnalysisResponse, RangeInput

app = FastAPI(title='Verificador de Serie "B"', version="1.0.0")

# Initialize database
db = Database()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Metadata extractor
metadata_extractor = MetadataExtractor()


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    await db.connect()
    logger.info("Database connected")


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
        # Extract metadata from request
        metadata = await metadata_extractor.extract(request, file)

        logger.info(f"Photo upload from {metadata['ip_address']}")

        # Save file
        file_path = os.path.join("uploads", metadata["filename"])
        os.makedirs("uploads", exist_ok=True)

        with open(file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
            metadata["file_size"] = len(contents)
        # logic to analyze image  and return JSON to storage results and send to frontend for display

        try:
            result = analyze_bill(contents)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing the image: {str(e)}",
            )
        # TODO: Structure the results and return to frontend for display
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

        # Store in MongoDB
        await db.save_upload(metadata)
        return {
            "status": "success",
            "message": "Photo uploaded successfully",
            "metadata": {
                "filename": metadata["filename"],
                "timestamp": metadata["timestamp"],
                "file_size": metadata["file_size"],
                "content_type": metadata["content_type"],
            },
        }

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

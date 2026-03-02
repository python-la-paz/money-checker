from fastapi import UploadFile, Request
from datetime import datetime
import uuid
from typing import Optional, Dict
import httpx
from .logger import logger

try:
    import geoip2.database

    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False
    logger.warning("geoip2 not installed. Location detection will be unavailable.")


class MetadataExtractor:
    """Extract metadata from requests and files"""

    def __init__(self):
        self.geoip_reader = None
        if GEOIP_AVAILABLE:
            self._init_geoip()

    def _init_geoip(self):
        """Initialize GeoIP database"""
        try:
            import os

            geoip_path = os.getenv("GEOIP_DATABASE_PATH", "./geoip/GeoLite2-City.mmdb")
            if os.path.exists(geoip_path):
                self.geoip_reader = geoip2.database.Reader(geoip_path)
                logger.info("GeoIP database loaded")
            else:
                logger.warning(f"GeoIP database not found at {geoip_path}")
        except Exception as e:
            logger.warning(f"Failed to initialize GeoIP: {str(e)}")

    async def extract(self, request: Request, file: UploadFile) -> dict:
        """Extract metadata from request and file"""

        # Get IP address (considering proxy headers)
        ip_address = self._get_client_ip(request)

        # Get geolocation if available
        location = None
        if self.geoip_reader:
            location = self._get_location(ip_address)

        # Get file information
        filename = self._generate_filename(file.filename)

        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": ip_address,
            "location": location,
            "filename": filename,
            "original_filename": file.filename,
            "content_type": file.content_type,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "referer": request.headers.get("referer", ""),
            "accept_language": request.headers.get("accept-language", ""),
            "host": request.headers.get("host", ""),
        }

        # Add proxy information if available
        x_forwarded_for = request.headers.get("x-forwarded-for")
        x_forwarded_proto = request.headers.get("x-forwarded-proto")
        x_forwarded_host = request.headers.get("x-forwarded-host")

        if x_forwarded_for or x_forwarded_proto or x_forwarded_host:
            metadata["proxy_info"] = {
                "x_forwarded_for": x_forwarded_for,
                "x_forwarded_proto": x_forwarded_proto,
                "x_forwarded_host": x_forwarded_host,
            }

        return metadata

    def _get_client_ip(self, request: Request) -> str:
        """
        Get client IP address considering proxy headers

        Checks in order:
        1. X-Forwarded-For header (common proxy header)
        2. CF-Connecting-IP (Cloudflare)
        3. X-Real-IP (Nginx proxy)
        4. Direct connection IP
        """

        # Check X-Forwarded-For (may contain multiple IPs)
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            # Take the first IP in the chain
            ip = x_forwarded_for.split(",")[0].strip()
            logger.info(f"IP from X-Forwarded-For: {ip}")
            return ip

        # Check Cloudflare
        cf_connecting_ip = request.headers.get("cf-connecting-ip")
        if cf_connecting_ip:
            logger.info(f"IP from CF-Connecting-IP: {cf_connecting_ip}")
            return cf_connecting_ip

        # Check X-Real-IP (Nginx)
        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            logger.info(f"IP from X-Real-IP: {x_real_ip}")
            return x_real_ip

        # Direct connection
        ip = request.client.host if request.client else "unknown"
        logger.info(f"Direct connection IP: {ip}")
        return ip

    def _get_location(self, ip_address: str) -> Optional[Dict]:
        """Get geolocation for IP address"""
        try:
            if ip_address in ["127.0.0.1", "localhost", "unknown"]:
                return None

            response = self.geoip_reader.city(ip_address)

            location = {
                "country": response.country.iso_code,
                "country_name": response.country.name,
                "city": response.city.name,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "timezone": response.location.time_zone,
            }

            logger.info(
                f"Location found for {ip_address}: {response.country.name}, {response.city.name}"
            )
            return location

        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"No location found for IP: {ip_address}")
            return None
        except Exception as e:
            logger.warning(f"Error getting location for {ip_address}: {str(e)}")
            return None

    def _generate_filename(self, original_filename: str) -> str:
        """Generate a unique filename"""
        # Get file extension
        ext = ""
        if "." in original_filename:
            ext = original_filename.rsplit(".", 1)[1]

        # Generate unique name with timestamp and UUID
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        filename = f"{timestamp}_{unique_id}.{ext}"
        return filename

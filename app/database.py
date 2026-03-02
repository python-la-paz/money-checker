from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os
from dotenv import load_dotenv
from .logger import logger

load_dotenv()


class Database:
    """MongoDB connection and operations"""

    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.db: AsyncIOMotorDatabase = None
        self.mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.database_name = os.getenv("DATABASE_NAME", "mydatabase")

    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.mongodb_url)
            self.db = self.client[self.database_name]

            # Verify connection
            await self.client.admin.command("ping")
            logger.info("Successfully connected to MongoDB")

            # Create indexes
            await self._create_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    async def _create_indexes(self):
        """Create database indexes"""
        try:
            uploads_collection = self.db["uploads"]

            # Create indexes for common queries
            await uploads_collection.create_index("timestamp")
            await uploads_collection.create_index("ip_address")
            await uploads_collection.create_index([("timestamp", -1)])

            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Error creating indexes: {str(e)}")

    async def save_upload(self, metadata: dict):
        """Save upload metadata to MongoDB"""
        try:
            uploads_collection = self.db["uploads"]
            result = await uploads_collection.insert_one(metadata)
            logger.info(f"Upload saved with ID: {result.inserted_id}")
            return result
        except Exception as e:
            logger.error(f"Error saving upload: {str(e)}")
            raise

    async def get_recent_uploads(self, skip: int = 0, limit: int = 10) -> list:
        """Get recent uploads with pagination"""
        try:
            uploads_collection = self.db["uploads"]
            uploads = (
                await uploads_collection.find()
                .sort("timestamp", -1)
                .skip(skip)
                .limit(limit)
                .to_list(None)
            )

            # Convert ObjectId to string for JSON serialization
            for upload in uploads:
                upload["_id"] = str(upload["_id"])

            return uploads
        except Exception as e:
            logger.error(f"Error fetching uploads: {str(e)}")
            raise

    async def count_uploads(self) -> int:
        """Count total uploads"""
        try:
            uploads_collection = self.db["uploads"]
            return await uploads_collection.count_documents({})
        except Exception as e:
            logger.error(f"Error counting uploads: {str(e)}")
            return 0

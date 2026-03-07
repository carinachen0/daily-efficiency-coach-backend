from __future__ import annotations

import os
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.models import MONGO_INDEXES


class MongoDB:
    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self) -> None:
        uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB", "daily_efficiency_coach")

        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

        # connectivity check
        await self.client.admin.command("ping")

        # ensure indexes for correctness
        await self._ensure_indexes()

    async def disconnect(self) -> None:
        if self.client:
            self.client.close()
        self.client = None
        self.db = None

    def collection(self, name: str):
        if not self.db:
            raise RuntimeError("MongoDB not connected.")
        return self.db[name]

    async def _ensure_indexes(self) -> None:
        if not self.db:
            raise RuntimeError("MongoDB not connected.")

        for collection_name, indexes in MONGO_INDEXES.items():
            col = self.db[collection_name]
            for idx in indexes:
                keys = idx["keys"]
                unique = bool(idx.get("unique", False))
                name = idx.get("name")

                pymongo_keys = []
                for field, direction in keys:
                    pymongo_keys.append(
                        (field, ASCENDING if direction in (1, "asc", "ASC") else direction)
                    )

                await col.create_index(pymongo_keys, unique=unique, name=name)


mongodb = MongoDB()


async def connect_to_mongo() -> None:
    await mongodb.connect()


async def close_mongo_connection() -> None:
    await mongodb.disconnect()
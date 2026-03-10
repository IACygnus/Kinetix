"""
Script para crear tablas en la base de datos - v2.0
"""
import asyncio
import logging
from app.db.base_class import Base
from app.db.models.user import User
from app.db.models.test import TestExecution, TestResult
from app.db.session import engine

logger = logging.getLogger(__name__)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Tablas creadas/verificadas exitosamente")


if __name__ == "__main__":
    asyncio.run(create_tables())

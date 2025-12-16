"""
Script para crear tablas en la base de datos
"""
import asyncio
from app.db.base_class import Base
from app.db.models.user import User
from app.db.models.test import TestExecution, TestResult
from app.db.session import engine

async def create_tables():
    async with engine.begin() as conn:
        # Eliminar todas las tablas (cuidado en producción!)
        await conn.run_sync(Base.metadata.drop_all)
        # Crear todas las tablas
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Tablas creadas exitosamente")

if __name__ == "__main__":
    asyncio.run(create_tables())

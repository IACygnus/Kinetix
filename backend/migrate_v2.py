"""
Script de migracion v1.3 -> v2.0
Agrega campos username y role a tabla users.
Ejecutar con: python migrate_v2.py
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
from app.core.security import get_password_hash
from app.core.config import settings
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    async with engine.begin() as conn:
        logger.info("Iniciando migracion v2.0...")

        # 1. Verificar si la columna 'username' ya existe
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'username'
        """))
        has_username = result.first() is not None

        if not has_username:
            logger.info("Agregando columna 'username' a tabla users...")
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(50);
            """))
            # Actualizar registros existentes: usar email como username
            await conn.execute(text("""
                UPDATE users SET username = split_part(email, '@', 1)
                WHERE username IS NULL;
            """))
            await conn.execute(text("""
                ALTER TABLE users ALTER COLUMN username SET NOT NULL;
            """))
            await conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
            """))

        # 2. Verificar si la columna 'role' ya existe
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'role'
        """))
        has_role = result.first() is not None

        if not has_role:
            logger.info("Agregando columna 'role' a tabla users...")
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'viewer';
            """))
            # Migrar is_superuser -> role
            await conn.execute(text("""
                UPDATE users SET role = 'admin' WHERE is_superuser = TRUE;
            """))
            await conn.execute(text("""
                UPDATE users SET role = 'viewer' WHERE role IS NULL OR role = '';
            """))

        # 3. Verificar si la columna 'full_name' es NOT NULL
        result = await conn.execute(text("""
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'full_name'
        """))
        row = result.first()
        if row and row[0] == 'YES':
            await conn.execute(text("""
                UPDATE users SET full_name = 'Usuario' WHERE full_name IS NULL;
            """))
            await conn.execute(text("""
                ALTER TABLE users ALTER COLUMN full_name SET NOT NULL;
            """))

        # 4. Agregar columna created_by si no existe
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'created_by'
        """))
        if result.first() is None:
            logger.info("Agregando columna 'created_by' a tabla users...")
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS created_by UUID
                REFERENCES users(id) ON DELETE SET NULL;
            """))

        # 5. Verificar que existe el admin seed
        result = await conn.execute(text("""
            SELECT id FROM users WHERE username = 'admin'
        """))
        admin = result.first()

        if admin is None:
            logger.info("Creando usuario admin por defecto...")
            admin_id = str(uuid.uuid4())
            hashed_pw = get_password_hash(settings.ADMIN_DEFAULT_PASSWORD)
            await conn.execute(text("""
                INSERT INTO users (id, username, email, full_name, hashed_password, role, is_active, created_at, updated_at)
                VALUES (:id, 'admin', 'admin@sqa.local', 'Administrador SQA', :pw, 'admin', TRUE, NOW(), NOW())
            """), {"id": admin_id, "pw": hashed_pw})

        logger.info("Migracion v2.0 completada exitosamente")


if __name__ == "__main__":
    asyncio.run(migrate())

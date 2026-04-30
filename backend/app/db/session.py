from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Cuando se usa el pooler de Supabase (pgBouncer en Transaction mode, puerto 6543),
# asyncpg no puede usar prepared statements — se desactivan con statement_cache_size=0.
# Con conexión directa (puerto 5432) no hace falta y se omite.
_connect_args = {"statement_cache_size": 0} if settings.USE_POOLER else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=not settings.is_production,
    pool_size=5,       # Supabase free tier tiene límite de conexiones
    max_overflow=10,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

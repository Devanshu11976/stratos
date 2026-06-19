"""
Database engine and session management.

Provides the async SQLAlchemy engine, the async session factory, and
session-acquisition helpers for both Litestar request handling and
out-of-request contexts (RQ workers, scripts). This module is
intentionally framework-agnostic — it does not import Litestar — so the
same engine/session machinery can be reused by background workers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

settings = get_settings()

# --- Async engine --------------------------------------------------------
# `pool_pre_ping` guards against stale connections after Postgres restarts
# or load-balancer idle timeouts. Pool sizing is environment-driven so it
# can be tuned per deployment without a code change.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
    future=True,
    connect_args={"connect_timeout": 10},  # Fail fast on connection issues
)

# --- Session factory -------------------------------------------------------
# `expire_on_commit=False` keeps ORM instances usable after commit, which
# matters when a response is serialized immediately after a write.
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Litestar dependency that yields a request-scoped `AsyncSession`.

    Register with `Provide(get_db_session)` in the Litestar app/route
    dependencies. The session commits automatically on a clean exit and
    rolls back if an exception propagates, then is always closed.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for obtaining a session outside of a Litestar request.

    Useful for RQ background workers and one-off scripts where Litestar's
    dependency injection system is not available, e.g.:

        async with session_scope() as session:
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db_connections() -> None:
    """Dispose of the engine's connection pool.

    Call this during application shutdown (e.g. a Litestar `on_shutdown`
    hook) to cleanly release all pooled connections.
    """
    await engine.dispose()
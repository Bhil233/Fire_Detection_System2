from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import (
    MYSQL_CHARSET,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_URL,
    MYSQL_USER,
)


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory = None


def _build_mysql_url() -> str:
    if MYSQL_URL:
        if MYSQL_URL.startswith("mysql+pymysql://"):
            return MYSQL_URL.replace("mysql+pymysql://", "mysql+aiomysql://", 1)
        if MYSQL_URL.startswith("mysql://"):
            return MYSQL_URL.replace("mysql://", "mysql+aiomysql://", 1)
        return MYSQL_URL

    user = quote_plus(MYSQL_USER)
    password = quote_plus(MYSQL_PASSWORD)
    host = MYSQL_HOST
    port = MYSQL_PORT
    database = MYSQL_DATABASE
    charset = MYSQL_CHARSET
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}?charset={charset}"


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(_build_mysql_url(), pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


async def init_database() -> None:
    from models import data_monitor  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def get_existing_columns(sync_conn) -> set[str]:
            inspector = inspect(sync_conn)
            return {column["name"] for column in inspector.get_columns("monitor_records")}

        existing_columns = await conn.run_sync(get_existing_columns)
        column_defs = {
            "fire_confidence": "FLOAT NULL",
            "yolo_confidence": "FLOAT NULL",
            "temperature": "FLOAT NULL",
            "smoke_density": "FLOAT NULL",
        }
        for column_name, column_def in column_defs.items():
            if column_name not in existing_columns:
                await conn.execute(
                    text(f"ALTER TABLE monitor_records ADD COLUMN {column_name} {column_def}")
                )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as db:
        yield db

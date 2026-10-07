"""Alembic 실행 환경. 비동기 엔진과 앱 설정(app.config)의 접속 정보를 사용한다.

- 프로파일(local/dev/product)은 APP_PROFILE로 정해지며, 접속 정보는 앱과 같은 설정 로더에서 읽는다.
- 테스트처럼 이미 열린 연결을 넘기고 싶으면 config.attributes["connection"]에 동기 연결을 넣는다.
"""

import asyncio
from logging.config import fileConfig
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings
from app.infra.db import models  # noqa: F401  (모델을 메타데이터에 등록하기 위해 import)
from app.infra.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config
if config.config_file_name is not None and config.attributes.get("connection") is None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB에 접속하지 않고 SQL 스크립트만 만든다."""
    context.configure(
        url=str(get_settings().database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(str(get_settings().database_url))
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        do_run_migrations(connection)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

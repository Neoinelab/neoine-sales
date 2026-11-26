#!/usr/bin/env python3
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
# How to run: uv run --project backend python excel-upload/import_contracts.py FILE.xlsx --dry-run
# Run through backend's locked environment; do not use `uv run import_contracts.py` isolation.

import argparse
import os
import sys
from pathlib import Path

import anyio
from contract_store import import_contracts
from contract_workbook import ContractImportError, read_workbook
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings

ENV_FILE = Path(__file__).resolve().parents[1] / "backend" / ".env"


async def run(filename: Path, *, dry_run: bool) -> tuple[int, int]:
    rows = read_workbook(filename)
    env_file = ENV_FILE
    if not await anyio.Path(env_file).is_file():
        raise ContractImportError(0, "backend/.env 파일이 없습니다.")
    os.environ["APP_ENV_FILE"] = str(env_file)
    get_settings.cache_clear()
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"timeout": 10},
    )
    try:
        return await import_contracts(engine, rows, dry_run=dry_run)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Excel 계약을 DB에 일괄 등록합니다.")
    parser.add_argument("filename", type=Path, help="contracts_20261123.xlsx 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 매핑/중복/사용자 확인")
    args = parser.parse_args()
    filename = args.filename
    if not filename.exists():
        filename = Path(__file__).resolve().parent / filename

    async def execute() -> tuple[int, int]:
        return await run(filename, dry_run=args.dry_run)

    try:
        created, skipped = anyio.run(execute)
    except ContractImportError as error:
        print(str(error), file=sys.stderr)
        return 1
    except ValidationError:
        print("backend/.env 설정 검증 실패. 설정 형식을 확인하세요.", file=sys.stderr)
        return 1
    except SQLAlchemyError, OSError, TimeoutError:
        print(
            "DB 처리 실패: 연결·최신 마이그레이션·제약을 확인하세요. 전체 반영은 취소됩니다.",
            file=sys.stderr,
        )
        return 1
    mode = "검증 완료(쓰기 없음), 생성 예정" if args.dry_run else "반영 완료, 생성"
    print(f"{mode}: {created}건, 기존 동일 계약 건너뜀: {skipped}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

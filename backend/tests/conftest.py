"""전역 fixture. 통합 테스트용 임시 DB는 세션당 한 번 만들고 마이그레이션을 적용한 뒤 지운다."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import SQLAlchemyError

from tests.support.database import (
    apply_migrations,
    create_database,
    drop_database,
    resolve_admin_url,
    run_async,
)
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import URL


def _first_line(error: BaseException) -> str:
    return (str(error).strip().splitlines() or [""])[0][:160]


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[URL]:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail(
            "TEST_DATABASE_ADMIN_URL이 없고 local 프로파일 설정도 없어 통합 테스트를 건너뜁니다"
        )
    try:
        url = run_async(create_database(admin_url))
    except (OSError, SQLAlchemyError) as exc:
        # DB에 접속할 수 없거나 권한이 없는 환경 문제만 건너뛴다. 그 외 오류는 실패로 드러낸다.
        skip_or_fail(f"임시 DB를 만들 수 없어 통합 테스트를 건너뜁니다: {_first_line(exc)}")
    try:
        run_async(apply_migrations(url))
        yield url
    finally:
        run_async(drop_database(admin_url, url.database or ""))

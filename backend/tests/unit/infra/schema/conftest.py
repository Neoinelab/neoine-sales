"""스키마 카탈로그 단위 테스트 공통 fixture.

`database_at`: 리비전별 임시 DB를 (처음 요청할 때) 만들어 주는 팩토리. 과거 리비전 스키마를 전제한
테스트가 새 리비전 때문에 깨지지 않도록 head 대신 target을 고정한다. 모듈 안에서
`test_database_url`을 이 팩토리의 결과로 덮어쓰면 `unit/infra/conftest.py`의 `session`도 따라온다.
(덮어쓴 fixture와 순환하지 않도록 이 fixture는 test_database_url에 의존하지 않는다.)
"""

from typing import TYPE_CHECKING

import pytest

from tests.support.database import (
    apply_migrations,
    create_database,
    drop_database,
    resolve_admin_url,
    run_async,
)
from tests.support.skips import skip_or_fail

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from sqlalchemy.engine import URL


@pytest.fixture(scope="session")
def database_at() -> Iterator[Callable[[str], URL]]:
    admin_url = resolve_admin_url()
    if admin_url is None:
        skip_or_fail("관리자 접속 정보가 없어 과거 리비전 스키마 테스트를 건너뜁니다")
    created: dict[str, URL] = {}

    def get(revision: str) -> URL:
        if revision not in created:
            url = run_async(create_database(admin_url))
            run_async(apply_migrations(url, target=revision))
            created[revision] = url
        return created[revision]

    yield get
    for url in created.values():
        run_async(drop_database(admin_url, url.database or ""))

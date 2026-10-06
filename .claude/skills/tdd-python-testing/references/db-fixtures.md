# 통합 테스트용 임시 DB fixture

## 목차

1. 현재 상태
2. 설계
3. fixture 스케치
4. 규칙과 주의

## 1. 현재 상태

**아직 구현되어 있지 않다.** 이 문서는 첫 통합 테스트(Repository 구현 등)를 작성할 때 `backend/tests/integration/conftest.py`에 만들 fixture의 설계다. 구현할 때는 Alembic 마이그레이션 구조가 먼저 있어야 하며, 없으면 `Base.metadata.create_all`로 시작하고 마이그레이션이 생기면 교체한다. 구현 후 이 문서의 "현재 상태"를 갱신한다.

## 2. 설계

- 컨테이너(Testcontainers)는 사용하지 않는다. **실제로 설치된 PostgreSQL**(개발자 PC의 로컬 DB, CI agent의 로컬 DB)에서 테스트 전용 DB를 임시로 만들고 지운다.
- 관리자 접속 URL은 환경변수 `TEST_DATABASE_ADMIN_URL`로 받는다(예: `postgresql+asyncpg://app:app@localhost:5432/postgres`). 이 role에는 `CREATEDB` 권한이 필요하다(개발 가이드 3.4절).
- 세션마다 `app_test_<무작위>` 이름의 DB를 `CREATE DATABASE`로 만들고, 스키마를 적용하고, 세션 종료 시 `DROP DATABASE`한다. 이름이 매번 달라 같은 agent에서 병렬 빌드가 돌아도 충돌하지 않는다.
- 테스트 간 격리는 테스트마다 트랜잭션을 열고 롤백하거나 테이블을 TRUNCATE한다.
- **개발·dev·product 데이터가 있는 DB에는 절대 연결하지 않는다.** `TEST_DATABASE_ADMIN_URL`이 없으면 통합 테스트는 건너뛴다(skip).

## 3. fixture 스케치

```python
# tests/integration/conftest.py  (스케치: 구현 시 mypy strict와 Ruff 규칙에 맞게 다듬는다)
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@pytest.fixture(scope="session")
def admin_url() -> str:
    url = os.environ.get("TEST_DATABASE_ADMIN_URL")
    if not url:
        pytest.skip("TEST_DATABASE_ADMIN_URL이 없어 통합 테스트를 건너뜁니다")
    return url


@pytest_asyncio.fixture(scope="session")
async def test_engine(admin_url: str) -> AsyncIterator[AsyncEngine]:
    name = f"app_test_{uuid.uuid4().hex[:8]}"
    admin = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_async_engine(make_url(admin_url).set(database=name))
    # TODO: 스키마 적용(Alembic upgrade 또는 metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()
```

## 4. 규칙과 주의

- DB 이름은 코드가 생성한 값만 SQL에 넣는다(사용자 입력 금지). Ruff `S608` 경고가 나면 해당 줄에만 근거와 함께 `noqa`를 단다.
- `pytest-asyncio`의 세션 범위 async fixture는 이벤트 루프 범위 설정이 필요할 수 있다. 구현 시 현재 설치 버전의 문서를 Context7로 확인한다.
- Windows 개발자는 WSL2의 PostgreSQL을 쓰는 것을 권장한다(개발 가이드 3.4절).
- 통합 테스트에는 `@pytest.mark.integration` 마커를 달고, 마커를 `pyproject.toml`에 등록해 단위 테스트만 빠르게 돌릴 수 있게 한다.

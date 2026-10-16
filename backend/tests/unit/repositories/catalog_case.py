"""CodeRepository·BantLabelRepository 계약 테스트 공용 case(Fake와 SQL 구현 양쪽).

SQL 구현은 마이그레이션이 넣은 기본 코드·기본 Label이 같은 DB에 있을 수 있으므로, 계약 테스트는
비어 있는 저장소를 가정하지 않는다(자기가 만든 행만 골라 비교한다: `mine`). SQL 구현 모듈은
사용 시점에 가져와, 구현 전에도 이 모듈을 쓰는 다른 계약 테스트의 수집이 막히지 않게 한다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pytest

from tests.fakes.catalog import FakeBantLabelRepository, FakeCodeRepository
from tests.support.database import rolled_back_session
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Collection

    from sqlalchemy.engine import URL

    from app.application.ports.user_repository import UserRepository
    from app.domain.user.value_objects import UserId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


class CatalogCase:
    """한 구현(fake 또는 sql)의 코드·Label 저장소. Port 계약만 보고 쓴다."""

    def __init__(self, codes: Any, labels: Any, users: UserRepository | None) -> None:  # noqa: ANN401
        self.codes = codes
        self.labels = labels
        self._users = users

    async def ensure_user(self, user_id: UserId) -> None:
        """Label 생성자 행(FK)을 만든다. Fake는 필요 없다."""
        if self._users is not None:
            await ensure_users(self._users, user_id)

    async def mine_codes(self, kind: Any, ids: Collection[Any]) -> list[Any]:  # noqa: ANN401
        """저장소의 해당 종류 목록 중 ids에 있는 것만(저장소 순서 유지)."""
        return [c for c in await self.codes.list(kind) if c.id in ids]

    async def mine_labels(self, category: Any, ids: Collection[Any]) -> list[Any]:  # noqa: ANN401
        return [x for x in await self.labels.list(category) if x.id in ids]


@asynccontextmanager
async def open_catalog(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[CatalogCase]:
    if implementation == "fake":
        yield CatalogCase(FakeCodeRepository(), FakeBantLabelRepository(), None)
        return
    from app.infra.db.bant_label_repository import SqlBantLabelRepository  # noqa: PLC0415
    from app.infra.db.code_repository import SqlCodeRepository  # noqa: PLC0415

    from app.infra.db.user_repository import SqlUserRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield CatalogCase(
            SqlCodeRepository(session), SqlBantLabelRepository(session), SqlUserRepository(session)
        )

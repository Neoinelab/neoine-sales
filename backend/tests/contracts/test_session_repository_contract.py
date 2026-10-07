"""SessionRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다."""

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio

from app.domain.auth.principal import Principal, Role
from app.domain.auth.session import AuthSession, SessionId
from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.infra.db.session_repository import SqlSessionRepository
from tests.factories import NOW, later
from tests.fakes.repositories import FakeSessionRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.session_repository import SessionRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


def make_session(**overrides: object) -> AuthSession:
    values: dict[str, object] = {
        "id": SessionId(uuid4()),
        "principal": Principal("S-1", "kim@neoine.example", "김영업", Role.ADMIN),
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=8),
    }
    return AuthSession(**{**values, **overrides})  # type: ignore[arg-type]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[SessionRepository]:
    if request.param == "fake":
        yield FakeSessionRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlSessionRepository(session)


async def test_add_then_get_by_token_hash_round_trips(repository: SessionRepository) -> None:
    session = make_session()
    await repository.add(session, "hash-1")

    stored = await repository.get_by_token_hash("hash-1")

    assert stored == session
    assert stored is not None
    assert stored.principal == session.principal
    assert stored.expires_at == session.expires_at
    assert stored.revoked_at is None


async def test_unknown_hash_returns_none(repository: SessionRepository) -> None:
    assert await repository.get_by_token_hash("nope") is None


async def test_duplicate_hash_is_rejected(repository: SessionRepository) -> None:
    await repository.add(make_session(), "same")

    with pytest.raises(AlreadyExistsError):
        await repository.add(make_session(), "same")


async def test_update_persists_revocation(repository: SessionRepository) -> None:
    session = make_session()
    await repository.add(session, "hash-1")
    session.revoke(later(30))

    await repository.update(session)

    stored = await repository.get_by_token_hash("hash-1")
    assert stored is not None
    assert stored.revoked_at == later(30)


async def test_update_unknown_session_raises_not_found(repository: SessionRepository) -> None:
    with pytest.raises(NotFoundError):
        await repository.update(make_session())

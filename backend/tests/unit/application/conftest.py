from typing import TYPE_CHECKING

import pytest

from tests.factories import NOW
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def uow_factory(uow: FakeUnitOfWork) -> UnitOfWorkFactory:
    """항상 같은 Fake를 돌려준다. 실제 구현은 호출할 때마다 새 UoW(새 세션)를 만든다."""
    return lambda: uow

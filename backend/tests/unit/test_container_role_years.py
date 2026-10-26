"""조립 계약(R1·R2): Container와 FakeUseCases가 역할 변경·연도 유스케이스를 웹 Port대로 제공한다."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from app.application.deal.deal_years import GetDealYears
from app.application.user.change_user_role import ChangeUserRole

from app.container import Container
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
NEW_USE_CASES = ("change_user_role", "get_deal_years")


@pytest_asyncio.fixture
async def container() -> AsyncIterator[Container]:
    built = Container(make_settings(UNUSED_DATABASE_URL))  # 엔진만 만들 뿐 DB에는 접속하지 않는다
    yield built
    await built.dispose()


async def test_container_builds_change_user_role_and_deal_years(container: Container) -> None:
    assert isinstance(container.change_user_role(), ChangeUserRole)
    assert isinstance(container.get_deal_years(), GetDealYears)


@pytest.mark.parametrize("name", NEW_USE_CASES)
def test_the_web_port_the_container_and_the_fake_expose_the_use_case(name: str) -> None:
    assert hasattr(UseCaseProvider, name)
    assert hasattr(Container, name)
    assert hasattr(FakeUseCases, name)


async def test_the_container_still_exposes_the_existing_deal_reads(container: Container) -> None:
    for name in (
        "get_deal",
        "list_deals",
        "list_updated_periods",
        "list_deal_history",
        "get_deal_deletion_impact",
    ):
        assert callable(getattr(container, name)), name

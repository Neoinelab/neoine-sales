"""ForecastTallyRepository 계약 테스트 공용 case (Fake와 SQL, P6 R1).

집계는 Deal 저장소의 Deal 위에서 하므로 case는 `DealCase`(Deal·사용자·연락처 준비 도우미)와 집계
저장소를 함께 가진다. Fake는 같은 Deal 저장소를 읽는 `FakeForecastTallyRepository`, SQL은 같은
세션 위의 `SqlForecastTallyRepository`다(구현 모듈은 사용 시점에 가져온다).
"""

import itertools
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from tests.factories import later, make_deal
from tests.fakes.forecast import FakeForecastTallyRepository
from tests.support.database import rolled_back_session
from tests.support.user_ids import OWNER_ID
from tests.unit.repositories.deal_case import DealCase, _fake_case, _sql_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.domain.user.value_objects import UserId

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@dataclass
class ForecastCase:
    deals: DealCase
    forecast: Any
    _numbers: Any = field(default_factory=lambda: itertools.count(1), repr=False)

    async def add_deal(
        self,
        *,
        forecast: str = "pipeline",
        amount: int = 100,
        day: date = date(2026, 11, 15),
        owner: UserId = OWNER_ID,
        vendor_id: int | None = None,
    ) -> str:
        """집계 대상 Deal 하나를 저장하고 code를 돌려준다."""
        number = next(self._numbers)
        code = f"20261016-A{number:03d}"
        deal = make_deal(
            later(number),
            code=code,
            forecast_key=forecast,
            status_key="contract_completed" if forecast == "won" else "prospecting",
            revenue_amount=amount,
            revenue_date=day,
            owner_user_id=owner,
            vendor_id=vendor_id,
        )
        await self.deals.add(deal)
        return code


@asynccontextmanager
async def open_forecast_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[ForecastCase]:
    if implementation == "fake":
        case = _fake_case()
        yield ForecastCase(case, FakeForecastTallyRepository(case.deals))
        return
    from app.infra.db.forecast_repository import SqlForecastTallyRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield ForecastCase(_sql_case(session), SqlForecastTallyRepository(session))

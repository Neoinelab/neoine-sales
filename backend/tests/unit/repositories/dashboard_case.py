"""DashboardTallyRepository 계약 테스트 공용 case (Fake와 SQL).

집계는 Deal 저장소의 Deal 위에서 하므로 case는 `DealCase`(Deal·사용자·Vendor·코드 준비
도우미)와 집계 저장소를 함께 가진다. Fake는 같은 Deal 저장소를 읽는
`FakeDashboardTallyRepository`, SQL은 같은 세션 위의
`SqlDashboardTallyRepository`다(구현 모듈은 사용 시점에 가져온다).
"""

import itertools
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from tests.factories import later, make_deal
from tests.fakes.dashboard import FakeDashboardTallyRepository
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
class DashboardCase:
    deals: DealCase
    dashboard: Any
    _numbers: Any = field(default_factory=lambda: itertools.count(1), repr=False)

    async def add_deal(  # noqa: PLR0913 - 집계 대상 Deal의 독립적인 선택지
        self,
        *,
        status: str | None = None,
        forecast: str = "pipeline",
        amount: int = 100,
        day: date = date(2026, 11, 15),
        owner: UserId = OWNER_ID,
        vendor_id: int | None = None,
    ) -> str:
        """집계 대상 Deal 하나를 저장하고 code를 돌려준다. Won은 계약완료 Status와 함께만 있다."""
        number = next(self._numbers)
        code = f"20261016-A{number:03d}"
        deal = make_deal(
            later(number),
            code=code,
            forecast_key=forecast,
            status_key=status or ("contract_completed" if forecast == "won" else "prospecting"),
            revenue_amount=amount,
            revenue_date=day,
            owner_user_id=owner,
            vendor_id=vendor_id,
        )
        await self.deals.add(deal)
        return code


@asynccontextmanager
async def open_dashboard_case(
    implementation: str, test_database_url: URL | None
) -> AsyncIterator[DashboardCase]:
    if implementation == "fake":
        case = _fake_case()
        yield DashboardCase(case, FakeDashboardTallyRepository(case.deals))
        return
    from app.infra.db.dashboard_tally import SqlDashboardTallyRepository  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:  # type: ignore[arg-type]
        yield DashboardCase(_sql_case(session), SqlDashboardTallyRepository(session))

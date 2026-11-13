"""수행일 범위 판정 `ensure_acted_on_in_range`: 오늘 이후·Deal 등록일 이전은 거절, 경계는 허용.

업무 날짜는 서버 OS 로컬 시간대(Asia/Seoul로 고정)의 달력 날짜다(AC-R35, AC-R45).
"""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.deal_action import acted_on as rules
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from collections.abc import Callable

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 13, 14, 30, tzinfo=KST)
REGISTERED = datetime(2026, 11, 1, 9, 0, tzinfo=KST)
FUTURE = "수행일은 오늘 이후로 지정할 수 없습니다."
BEFORE_REGISTERED = "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.mark.parametrize("day", [date(2026, 11, 1), date(2026, 11, 10), date(2026, 11, 13)])
def test_dates_from_the_registration_day_to_today_are_accepted(day: date) -> None:
    """등록일 당일부터 오늘까지는 거절하지 않는다.

    테스트 코드: AC-121, AC-122
    """
    # when·then: 경계(등록일·오늘)와 그 사이 날짜는 오류 없이 지나간다
    rules.ensure_acted_on_in_range(day, now=NOW, deal_registered_at=REGISTERED)


def test_tomorrow_is_rejected() -> None:
    """내일부터는 거절한다.

    테스트 코드: AC-121
    """
    # when·then: 2026-11-14는 오늘 이후 오류다
    with raises_with(InvalidValueError, FUTURE):
        rules.ensure_acted_on_in_range(date(2026, 11, 14), now=NOW, deal_registered_at=REGISTERED)


def test_the_day_before_the_registration_day_is_rejected() -> None:
    """등록일 전날은 거절하고 문구에 등록일이 들어간다.

    테스트 코드: AC-122
    """
    # when·then: 2026-10-31은 등록일(11-01) 이전 오류다
    with raises_with(InvalidValueError, BEFORE_REGISTERED):
        rules.ensure_acted_on_in_range(date(2026, 10, 31), now=NOW, deal_registered_at=REGISTERED)


def test_the_registration_day_is_judged_by_the_business_date_of_the_deal_created_at() -> None:
    """Deal 등록일은 등록 시각의 업무 날짜(UTC가 아닌 서버 시간대)다.

    테스트 코드: AC-122
    """
    # given: UTC로는 10-31 16:00이지만 서울로는 11-01 01:00에 등록된 Deal
    registered = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)

    # when·then: 11-01은 등록일 당일이라 받고 10-31은 거절한다
    rules.ensure_acted_on_in_range(date(2026, 11, 1), now=NOW, deal_registered_at=registered)
    with raises_with(InvalidValueError, BEFORE_REGISTERED):
        rules.ensure_acted_on_in_range(date(2026, 10, 31), now=NOW, deal_registered_at=registered)

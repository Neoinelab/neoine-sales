"""수행일 결정 `resolve_acted_on`: 수행일이 없으면 오늘, 있으면 그 날짜(범위 안), 시각은 없다.

업무 날짜는 서버 OS 로컬 시간대(Asia/Seoul로 고정)의 달력 날짜다(AC-R34·R35).
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
TODAY = date(2026, 11, 13)
REGISTERED = datetime(2026, 11, 1, 9, 0, tzinfo=KST)
FUTURE = "수행일은 오늘 이후로 지정할 수 없습니다."


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


@pytest.mark.parametrize("acted_on", [None, TODAY])
def test_none_or_today_resolves_to_today(acted_on: date | None) -> None:
    """수행일이 없거나 오늘이면 오늘 날짜다(시각 없는 date).

    테스트 코드: AC-091
    """
    # when: 수행일 없음 또는 오늘로 결정한다
    resolved = rules.resolve_acted_on(acted_on, now=NOW, deal_registered_at=REGISTERED)
    # then: 2026-11-13 date다
    assert resolved == TODAY
    assert type(resolved) is date


def test_a_past_day_resolves_to_that_day() -> None:
    """지난 날짜는 시각 없이 그 날짜 그대로다(23:59:59로 바꾸지 않는다).

    테스트 코드: AC-092
    """
    # when: 2026-11-10으로 결정한다
    resolved = rules.resolve_acted_on(date(2026, 11, 10), now=NOW, deal_registered_at=REGISTERED)
    # then: 2026-11-10 date다
    assert resolved == date(2026, 11, 10)
    assert type(resolved) is date


def test_a_utc_request_just_after_local_midnight_counts_as_the_next_business_day() -> None:
    """오늘은 요청 시각의 업무 날짜(서버 시간대)다(UTC 15:00 = 서울 다음 날 00:00)."""
    # given: UTC 11-13 15:00 = 서울 11-14 00:00
    now = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
    # when: 수행일 없음, 서울 11-13(어제), 서울 11-14(오늘)로 결정한다
    omitted = rules.resolve_acted_on(None, now=now, deal_registered_at=REGISTERED)
    yesterday = rules.resolve_acted_on(date(2026, 11, 13), now=now, deal_registered_at=REGISTERED)
    today = rules.resolve_acted_on(date(2026, 11, 14), now=now, deal_registered_at=REGISTERED)
    # then: 생략은 11-14(UTC 날짜 11-13이 아님), 어제·오늘은 그대로 받는다
    assert omitted == date(2026, 11, 14)
    assert yesterday == date(2026, 11, 13)
    assert today == date(2026, 11, 14)
    # when·then: 서울 기준 내일(11-15)은 거절한다
    with raises_with(InvalidValueError, FUTURE):
        rules.resolve_acted_on(date(2026, 11, 15), now=now, deal_registered_at=REGISTERED)


def test_tomorrow_is_rejected() -> None:
    """내일부터는 거절한다.

    테스트 코드: AC-093
    """
    # when·then: 내일이면 InvalidValueError다
    with raises_with(InvalidValueError, FUTURE):
        rules.resolve_acted_on(date(2026, 11, 14), now=NOW, deal_registered_at=REGISTERED)


def test_the_day_before_the_registration_day_is_rejected_and_the_day_itself_is_accepted() -> None:
    """Deal 등록일 전날은 거절하고 등록일 당일은 받는다.

    테스트 코드: AC-094
    """
    # when·then: 등록일 전날은 InvalidValueError다
    with raises_with(
        InvalidValueError, "수행일은 Deal 등록일(2026-11-01) 이전으로 지정할 수 없습니다."
    ):
        rules.resolve_acted_on(date(2026, 10, 31), now=NOW, deal_registered_at=REGISTERED)
    # when: 등록일 당일로 결정한다
    resolved = rules.resolve_acted_on(date(2026, 11, 1), now=NOW, deal_registered_at=REGISTERED)
    # then: 그 날짜다
    assert resolved == date(2026, 11, 1)


def test_a_deal_registered_today_accepts_only_today() -> None:
    """오늘 등록된 Deal은 오늘만 받고 어제는 거절한다."""
    # given: 오늘 등록된 Deal
    registered = datetime(2026, 11, 13, 9, 0, tzinfo=KST)
    # when: 오늘로 결정한다
    resolved = rules.resolve_acted_on(TODAY, now=NOW, deal_registered_at=registered)
    # then: 오늘이다
    assert resolved == TODAY
    # when·then: 어제는 등록일 이전이라 거절한다
    with raises_with(
        InvalidValueError, "수행일은 Deal 등록일(2026-11-13) 이전으로 지정할 수 없습니다."
    ):
        rules.resolve_acted_on(date(2026, 11, 12), now=NOW, deal_registered_at=registered)


def test_the_registration_day_is_the_business_date_of_the_registration_time() -> None:
    """등록일은 등록 시각의 업무 날짜다(UTC 11-01 16:00 = 서울 11-02)."""
    # given: UTC로 기록된 등록 시각(서울 기준 11-02 01:00)
    registered = datetime(2026, 11, 1, 16, 0, tzinfo=UTC)
    # when·then: 서울 11-01은 등록일 이전이다
    with raises_with(
        InvalidValueError, "수행일은 Deal 등록일(2026-11-02) 이전으로 지정할 수 없습니다."
    ):
        rules.resolve_acted_on(date(2026, 11, 1), now=NOW, deal_registered_at=registered)


def test_a_request_time_without_a_timezone_is_rejected() -> None:
    """시간대 정보 없는 요청 시각은 거절한다.

    테스트 코드: RK-016
    """
    # when·then: naive 시각이면 오류다
    with pytest.raises(InvalidValueError):
        rules.resolve_acted_on(
            None, now=datetime(2026, 11, 13, 14, 30), deal_registered_at=REGISTERED
        )


def test_closing_on_the_same_day_as_the_basis_is_allowed_and_an_earlier_day_is_rejected() -> None:
    """이전 Next Action을 닫는 수행일은 기준 행 수행일과 같은 날부터 허용하고 앞서면 거절한다.

    테스트 코드: AC-100
    """
    # given: 기준 행 수행일 11-12
    basis = date(2026, 11, 12)
    # when·then: 같은 날과 이후는 통과한다
    rules.ensure_not_before_basis(date(2026, 11, 12), basis)
    rules.ensure_not_before_basis(date(2026, 11, 13), basis)
    # when·then: 하루라도 앞서면 문구와 함께 거절한다
    with raises_with(
        InvalidValueError,
        "이전 Next Action의 수행일(2026-11-12)보다 앞선 날짜로는 "
        "이전 Next Action을 종료할 수 없습니다.",
    ):
        rules.ensure_not_before_basis(date(2026, 11, 11), basis)

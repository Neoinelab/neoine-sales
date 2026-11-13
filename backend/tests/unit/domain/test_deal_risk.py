"""Deal Risk 계산(R03·R04·R06): 기한초과, 미업데이트, 종결 제외.

"오늘"과 `last_updated_on`은 업무 날짜(date)이고 경과 일수는 날짜끼리 뺀 값이다(RK-R5).
시각이 없으므로 시간대 변환은 이 계산에 없다.
"""

from datetime import date

import pytest

from app.domain.deal.risk import Risk, compute_risk, is_closed_forecast

TODAY = date(2026, 10, 20)
STALE_DAYS = 14
FRESH = date(2026, 10, 19)  # 1일 전
STALE_BOUNDARY = date(2026, 10, 6)  # 14일 전
ONE_DAY_BEFORE_BOUNDARY = date(2026, 10, 7)  # 13일 전
LONG_AGO = date(2026, 1, 1)


def _risk(
    *,
    forecast_key: str = "pipeline",
    due_date: date | None = None,
    last_updated_on: date = FRESH,
    today: date = TODAY,
    stale_days: int = STALE_DAYS,
) -> Risk | None:
    return compute_risk(
        forecast_key=forecast_key,
        due_date=due_date,
        last_updated_on=last_updated_on,
        today=today,
        stale_days=stale_days,
    )


def test_due_today_is_not_overdue() -> None:
    """Due가 오늘이면 기한초과가 아니다.

    테스트 코드: RK-010
    """
    # when: Due가 오늘인 Deal을 판정한다
    actual = _risk(due_date=TODAY)
    # then: risk가 없다
    assert actual is None


def test_due_yesterday_is_overdue() -> None:
    """Due가 어제면 기한초과다.

    테스트 코드: RK-009
    """
    # when: Due가 어제인 Deal을 판정한다
    actual = _risk(due_date=date(2026, 10, 19))
    # then: risk가 overdue다
    assert actual is Risk.OVERDUE


def test_due_tomorrow_is_not_overdue() -> None:
    """Due가 내일이면 기한초과가 아니다.

    테스트 코드: RK-010
    """
    # when: Due가 내일인 Deal을 판정한다
    actual = _risk(due_date=date(2026, 10, 21))
    # then: risk가 없다
    assert actual is None


def test_no_action_is_not_overdue() -> None:
    """기준 행이 없으면 기한초과가 아니다.

    테스트 코드: RK-011
    """
    # when: Due가 없는 Deal을 판정한다
    actual = _risk(due_date=None)
    # then: risk가 없다
    assert actual is None


def test_stale_from_exactly_stale_days() -> None:
    """마지막 갱신 후 14일째부터 미업데이트다.

    테스트 코드: RK-014
    """
    # when: 14일 전에 갱신한 Deal을 판정한다
    actual = _risk(last_updated_on=STALE_BOUNDARY)
    # then: risk가 stale이다
    assert actual is Risk.STALE


def test_not_stale_one_day_before() -> None:
    """마지막 갱신 후 13일째는 정상이다.

    테스트 코드: RK-014
    """
    # when: 13일 전에 갱신한 Deal을 판정한다
    actual = _risk(last_updated_on=ONE_DAY_BEFORE_BOUNDARY)
    # then: risk가 없다
    assert actual is None


def test_stale_far_beyond_the_boundary() -> None:
    """기준보다 훨씬 오래돼도 미업데이트다.

    테스트 코드: RK-014
    """
    # when: 아주 오래전에 갱신한 Deal을 판정한다
    actual = _risk(last_updated_on=LONG_AGO)
    # then: risk가 stale이다
    assert actual is Risk.STALE


def test_overdue_and_stale_is_overdue_stale() -> None:
    """기한초과이면서 미업데이트면 overdue_stale이다.

    테스트 코드: RK-017
    """
    # when: Due가 지났고 14일 전에 갱신한 Deal을 판정한다
    risk = _risk(due_date=date(2026, 10, 1), last_updated_on=STALE_BOUNDARY)

    # then: risk가 overdue_stale이다
    assert risk is Risk.OVERDUE_STALE


def test_overdue_only_is_not_marked_stale() -> None:
    """기한초과만이고 최근 갱신했으면 overdue다.

    테스트 코드: RK-017
    """
    # when: Due가 지났고 최근 갱신한 Deal을 판정한다
    actual = _risk(due_date=date(2026, 10, 1), last_updated_on=FRESH)
    # then: risk가 overdue다
    assert actual is Risk.OVERDUE


@pytest.mark.parametrize("forecast_key", ["won", "lost"])
def test_won_and_lost_have_no_risk(forecast_key: str) -> None:
    """Won·Lost는 기한이 지나고 오래돼도 경고가 없다.

    테스트 코드: RK-018
    """
    # when: Due가 지났고 오래전에 갱신한 Won·Lost Deal을 판정한다
    risk = _risk(
        forecast_key=forecast_key,
        due_date=date(2026, 10, 1),
        last_updated_on=LONG_AGO,
    )

    # then: risk가 없다
    assert risk is None


@pytest.mark.parametrize("forecast_key", ["pipeline", "best", "commit", "upside"])
def test_open_forecasts_keep_their_risk(forecast_key: str) -> None:
    """Won·Lost가 아닌 Forecast key는 경고를 판정한다.

    테스트 코드: RK-018
    """
    # when: Due가 지난 pipeline·best·commit·upside Deal을 판정한다
    actual = _risk(forecast_key=forecast_key, due_date=date(2026, 10, 1))
    # then: risk가 overdue다
    assert actual is Risk.OVERDUE


@pytest.mark.parametrize(
    ("forecast_key", "closed"),
    [("won", True), ("lost", True), ("pipeline", False), ("commit", False), ("Won", False)],
)
def test_closed_forecast_is_decided_by_key(forecast_key: str, closed: bool) -> None:
    """종결 Forecast는 이름이 아니라 key(won·lost)로 판정한다.

    테스트 코드: RK-018
    """
    # when: key로 종결 여부를 묻는다
    actual = is_closed_forecast(forecast_key)
    # then: won·lost만 종결이고 Won(대문자)은 아니다
    assert actual is closed


def test_custom_stale_days_is_used() -> None:
    """경고 기준 일수를 바꾸면 그 기준으로 판정한다.

    테스트 코드: RK-022
    """
    # given: 7일 전에 갱신한 Deal이다
    week_old = date(2026, 10, 13)

    # when: 기준 7일과 8일로 판정한다
    assert _risk(last_updated_on=week_old, stale_days=7) is Risk.STALE
    # then: 기준 7일이면 stale, 8일이면 정상이다
    assert _risk(last_updated_on=week_old, stale_days=8) is None


def test_stale_days_of_one_makes_yesterday_stale_and_today_fresh() -> None:
    """기준 1일이면 어제 갱신은 미업데이트, 오늘 갱신은 정상이다.

    테스트 코드: RK-015
    """
    # when: 어제와 오늘 갱신한 Deal을 기준 1일로 판정한다
    assert _risk(last_updated_on=FRESH, stale_days=1) is Risk.STALE
    # then: 어제 갱신은 stale, 오늘 갱신은 정상이다
    assert _risk(last_updated_on=TODAY, stale_days=1) is None


def test_stale_is_the_difference_of_dates_not_of_elapsed_hours() -> None:
    """경과 일수는 날짜끼리 뺀 값이다(같은 날이면 0일, 시각은 없다).

    테스트 코드: RK-016
    """
    # when: 오늘 갱신(0일)과 기준 1일, 어제 갱신(1일)과 기준 2일로 판정한다
    same_day = _risk(last_updated_on=TODAY, stale_days=1)
    yesterday = _risk(last_updated_on=FRESH, stale_days=2)
    # then: 둘 다 정상이다
    assert same_day is None
    assert yesterday is None

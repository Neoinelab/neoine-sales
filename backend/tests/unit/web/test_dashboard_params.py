"""Dashboard 요약 쿼리 모델(DashboardSearchParams): year 필수, 모르는 파라미터 거절, 범위 검증."""

import pytest
from pydantic import ValidationError

from app.application.dashboard.criteria import DashboardCriteria
from app.domain.forecast.period import ForecastPeriod
from app.domain.user.value_objects import UserId
from app.domain.vendor.values import VendorId
from app.web.schemas.dashboard import DashboardSearchParams
from tests.support.ids import new_id


def test_dashboard_params_require_year() -> None:
    """year가 없으면 검증 오류다.

    테스트 코드: DSH-002
    """
    # when·then: year 없이 만들면 ValidationError다
    with pytest.raises(ValidationError):
        DashboardSearchParams()  # type: ignore[call-arg]


def test_dashboard_params_reject_unknown_param_month() -> None:
    """모르는 키 month는 검증 오류다.

    테스트 코드: DSH-003
    """
    # when·then: month를 넣으면 ValidationError다
    with pytest.raises(ValidationError):
        DashboardSearchParams(year=2026, month=3)  # type: ignore[call-arg]


def test_dashboard_params_reject_any_other_unknown_param() -> None:
    """month 외의 모르는 키(vendor)도 검증 오류다.

    테스트 코드: DSH-003
    """
    # when·then: vendor를 넣으면 ValidationError다
    with pytest.raises(ValidationError):
        DashboardSearchParams(year=2026, vendor="SAP")  # type: ignore[call-arg]


@pytest.mark.parametrize("year", [1899, 10000])
def test_dashboard_params_reject_year_outside_the_range(year: int) -> None:
    """1900~9999 밖의 연도는 검증 오류다.

    테스트 코드: DSH-002
    """
    # when·then: 범위 밖 연도로 만들면 ValidationError다
    with pytest.raises(ValidationError):
        DashboardSearchParams(year=year)


@pytest.mark.parametrize("year", [1900, 9999])
def test_dashboard_params_accept_the_year_range_limits(year: int) -> None:
    """범위 양끝 연도 1900·9999는 받아들인다.

    테스트 코드: DSH-002
    """
    # when: 경계 연도로 만든다
    params = DashboardSearchParams(year=year)

    # then: 연도가 그대로다
    assert params.year == year


@pytest.mark.parametrize("quarter", [0, 5])
def test_dashboard_params_reject_out_of_range_quarter(quarter: int) -> None:
    """1~4 밖의 분기는 quarter 위치의 검증 오류다.

    테스트 코드: DSH-003
    """
    # when·then: 범위 밖 분기로 만들면 오류 위치가 quarter다
    with pytest.raises(ValidationError) as caught:
        DashboardSearchParams(year=2026, quarter=[quarter])

    assert caught.value.errors()[0]["loc"] == ("quarter",)


def test_a_non_numeric_year_is_a_validation_error() -> None:
    """숫자가 아닌 연도는 검증 오류다.

    테스트 코드: DSH-002
    """
    # when·then: 문자 연도로 만들면 ValidationError다
    with pytest.raises(ValidationError):
        DashboardSearchParams(year="abc")


def test_to_criteria_carries_period_owner_and_vendor() -> None:
    """쿼리를 조건으로 바꾸면 기간·담당자·Vendor가 그대로 담긴다.

    BDD 밖: 쿼리 모델 → `DashboardCriteria` 변환을 확인한다.
    """
    # given: 담당자·Vendor id
    owner, vendor = UserId(new_id()), VendorId(new_id())

    # when: 2026년 Q4와 함께 조건으로 바꾼다
    criteria = DashboardSearchParams(
        year=2026, quarter=[4], owner_user_id=owner, vendor_id=vendor
    ).to_criteria()

    # then: 조건이 같다
    assert criteria == DashboardCriteria(
        period=ForecastPeriod(year=2026, quarters=frozenset({4})),
        owner_user_id=owner,
        vendor_id=vendor,
    )


def test_to_criteria_without_optional_conditions_leaves_them_unset() -> None:
    """담당자·Vendor가 없으면 조건에도 비어 있다.

    BDD 밖: 쿼리 모델 → `DashboardCriteria` 변환을 확인한다.
    """
    # when: 연도만으로 조건을 만든다
    criteria = DashboardSearchParams(year=2026).to_criteria()

    # then: 기간은 연도뿐이고 담당자·Vendor가 없다
    assert criteria.period == ForecastPeriod(year=2026)
    assert criteria.owner_user_id is None
    assert criteria.vendor_id is None


def test_several_quarters_reach_the_criteria_period() -> None:
    """여러 분기는 오름차순 집합으로 조건의 기간에 담긴다.

    테스트 코드: DSH-006
    """
    # when: 분기 3, 1로 조건을 만든다
    criteria = DashboardSearchParams(year=2026, quarter=[3, 1]).to_criteria()

    # then: 기간의 분기 집합은 {1, 3}이다
    assert criteria.period == ForecastPeriod(year=2026, quarters=frozenset({1, 3}))


def test_all_four_quarters_become_no_quarter_condition() -> None:
    """넷 다 고르면 분기 조건이 없다.

    테스트 코드: DSH-006
    """
    # when: 분기 1~4로 조건을 만든다
    criteria = DashboardSearchParams(year=2026, quarter=[1, 2, 3, 4]).to_criteria()

    # then: 분기 조건이 없다
    assert criteria.period == ForecastPeriod(year=2026)


def test_the_same_quarter_twice_equals_once() -> None:
    """같은 분기를 두 번 주면 한 번과 같다.

    테스트 코드: DSH-006
    """
    # when: 분기 2, 2로 조건을 만든다
    twice = DashboardSearchParams(year=2026, quarter=[2, 2]).to_criteria()

    # then: 분기 집합은 {2}다
    assert twice.period == ForecastPeriod(year=2026, quarters=frozenset({2}))


def test_an_empty_quarter_list_is_no_quarter_condition() -> None:
    """빈 분기 목록은 분기 조건이 없다.

    테스트 코드: DSH-006
    """
    # when: 빈 분기 목록으로 조건을 만든다
    criteria = DashboardSearchParams(year=2026, quarter=[]).to_criteria()

    # then: 분기 조건이 없다
    assert criteria.period == ForecastPeriod(year=2026)


def test_more_than_four_quarter_values_are_rejected_and_four_are_accepted() -> None:
    """분기는 4개까지 받고 5개는 quarter 위치의 검증 오류다.

    테스트 코드: DSH-003
    """
    # when: 4개를 넣는다
    four = DashboardSearchParams(year=2026, quarter=[1, 2, 3, 4])

    # then: 받아들인다
    assert four.quarter == [1, 2, 3, 4]

    # when·then: 5개를 넣으면 오류 위치가 quarter다
    with pytest.raises(ValidationError) as caught:
        DashboardSearchParams(year=2026, quarter=[1, 2, 3, 4, 1])

    assert caught.value.errors()[0]["loc"] == ("quarter",)


def test_a_bad_item_reports_its_position_under_quarter() -> None:
    """잘못된 항목은 quarter 아래 위치로 보고한다.

    테스트 코드: DSH-003
    """
    # when·then: 분기 목록에 5가 섞이면 오류 위치가 quarter로 시작한다
    with pytest.raises(ValidationError) as caught:
        DashboardSearchParams(year=2026, quarter=[1, 5])

    assert caught.value.errors()[0]["loc"][0] == "quarter"

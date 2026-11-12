"""Status/Forecast 변경 계획(`plan_change`, R-1): 프런트 `sync.test.ts` T-SYNC-01~08 이식.

계획은 부수효과가 없고, 서버는 prompt 문구를 만들지 않는다(Q4).
"""

from app.domain.deal.sync import (
    AskForecast,
    AskStatus,
    Independent,
    NeedRevenue,
    SyncChange,
    SyncField,
    SyncPatch,
    plan_change,
)
from tests.support.sync_catalog import LOST, OPEN, WON, default_catalog

CATALOG = default_catalog()
CLOSING = SyncPatch(status_key="contract_completed", forecast_key="won")


def _status(value: str) -> SyncChange:
    return SyncChange(SyncField.STATUS, value)


def _forecast(value: str) -> SyncChange:
    return SyncChange(SyncField.FORECAST, value)


def test_status_to_contract_completed_also_sets_won_and_needs_revenue() -> None:
    """Status를 계약완료로 바꾸면 계획은 Won도 함께 두고 매출을 요구한다.

    테스트 코드: DD-013
    """
    # when: Status를 계약완료로 바꾸는 계획을 세운다
    plan = plan_change(OPEN, _status("contract_completed"), CATALOG)

    # then: 계약완료+Won 패치와 매출 필요(요청 필드 Status)다
    assert plan == NeedRevenue(patch=CLOSING, requested=SyncField.STATUS)


def test_forecast_to_won_also_sets_contract_completed_and_needs_revenue() -> None:
    """Forecast를 Won으로 바꾸면 계획은 계약완료도 함께 두고 매출을 요구한다.

    테스트 코드: DD-014
    """
    # when: Forecast를 Won으로 바꾸는 계획을 세운다
    plan = plan_change(OPEN, _forecast("won"), CATALOG)

    # then: 계약완료+Won 패치와 매출 필요(요청 필드 Forecast)다
    assert plan == NeedRevenue(patch=CLOSING, requested=SyncField.FORECAST)


def test_lost_to_won_needs_revenue_too() -> None:
    """Lost에서 Won으로 바꾸는 것도 종결이라 매출이 필요하다.

    테스트 코드: DD-015
    """
    # when: Forecast를 Won으로 바꾸는 계획을 세운다
    plan = plan_change(LOST, _forecast("won"), CATALOG)

    # then: 매출 필요 계획이고 패치는 계약완료+Won이다
    assert isinstance(plan, NeedRevenue)
    assert plan.patch == CLOSING


def test_forecast_to_lost_keeps_the_status() -> None:
    """진행 중 Deal을 Lost로 바꾸면 Status는 그대로 두는 독립 변경이다.

    테스트 코드: DD-021
    """
    # when: Forecast를 Lost로 바꾸는 계획을 세운다
    plan = plan_change(OPEN, _forecast("lost"), CATALOG)

    # then: Forecast만 바꾸는 독립 변경이다
    assert plan == Independent(patch=SyncPatch(forecast_key="lost"))


def test_leaving_won_asks_for_a_status_without_a_default() -> None:
    """Won에서 벗어나면 계약완료를 뺀 Status 선택지를 기본값 없이 묻는다.

    테스트 코드: DD-017
    """
    # when: Forecast를 Commit으로 바꾸는 계획을 세운다
    plan = plan_change(WON, _forecast("commit"), CATALOG)

    # then: Status 선택 필요, 기본값 없음, 선택지에 계약완료가 없고 6개다
    assert isinstance(plan, AskStatus)
    assert plan.default_key is None
    assert plan.patch == SyncPatch(forecast_key="commit")
    assert "contract_completed" not in plan.options
    assert len(plan.options) == 6


def test_won_to_lost_also_asks_for_a_status() -> None:
    """Won에서 Lost로 가도 Status를 묻는다.

    테스트 코드: DD-018
    """
    # when: Forecast를 Lost로 바꾸는 계획을 세운다
    plan = plan_change(WON, _forecast("lost"), CATALOG)
    # then: Status 선택 필요 계획이다
    assert isinstance(plan, AskStatus)


def test_leaving_lost_asks_for_a_status_defaulting_to_the_current_one() -> None:
    """Lost에서 되돌리면 Status를 묻고 기본값은 현재 Status다.

    테스트 코드: DD-020
    """
    # when: Forecast를 Best로 바꾸는 계획을 세운다
    plan = plan_change(LOST, _forecast("best"), CATALOG)

    # then: Status 선택 필요, 기본값은 가격협상, 선택지에 계약완료가 없다
    assert isinstance(plan, AskStatus)
    assert plan.default_key == "price_negotiation"
    assert "contract_completed" not in plan.options


def test_the_status_options_follow_the_catalog_order() -> None:
    """Status 선택지는 코드 목록 순서를 따른다.

    테스트 코드: DD-025
    """
    # when: Forecast를 Commit으로 바꾸는 계획을 세운다
    plan = plan_change(WON, _forecast("commit"), CATALOG)

    # then: 선택지가 코드 순서의 계약완료를 뺀 여섯 Status다
    assert isinstance(plan, AskStatus)
    assert plan.options == (
        "prospecting",
        "introduction",
        "poc_preparation",
        "poc_completed",
        "technical_evaluation",
        "price_negotiation",
    )


def test_leaving_contract_completed_asks_for_a_forecast_without_won() -> None:
    """계약완료에서 벗어나면 Won을 뺀 Forecast 선택지를 묻는다.

    테스트 코드: DD-019
    """
    # when: Status를 POC완료로 바꾸는 계획을 세운다
    plan = plan_change(WON, _status("poc_completed"), CATALOG)

    # then: Won을 뺀 코드 순서 Forecast 선택 필요 계획이다
    assert plan == AskForecast(
        options=("pipeline", "best", "most_likely", "commit", "lost"),
        patch=SyncPatch(status_key="poc_completed"),
    )


def test_other_changes_are_independent() -> None:
    """종결·되돌림이 아닌 Status·Forecast 변경은 요청한 값만 바꾸는 독립 변경이다.

    테스트 코드: DD-021
    """
    # when: Status와 Forecast를 각각 일반 값으로 바꾸는 계획을 세운다
    assert plan_change(OPEN, _status("poc_completed"), CATALOG) == Independent(
        patch=SyncPatch(status_key="poc_completed")
    )
    # then: 각각 요청한 값만 담은 독립 변경이다
    assert plan_change(OPEN, _forecast("best"), CATALOG) == Independent(
        patch=SyncPatch(forecast_key="best")
    )


def test_the_same_value_is_an_independent_change_with_an_empty_patch() -> None:
    """현재와 같은 값으로 바꾸는 계획은 빈 패치의 독립 변경이다.

    테스트 코드: DD-023
    """
    # when: 같은 값으로 바꾸는 계획을 세운다
    assert plan_change(WON, _forecast("won"), CATALOG) == Independent(patch=SyncPatch())
    # then: 모두 빈 패치의 독립 변경이다
    assert plan_change(WON, _status("contract_completed"), CATALOG) == Independent(
        patch=SyncPatch()
    )
    assert plan_change(LOST, _forecast("lost"), CATALOG) == Independent(patch=SyncPatch())


def test_renamed_codes_do_not_change_the_rules_because_they_work_on_keys() -> None:
    """코드 이름을 바꿔도 규칙은 key로 동작해 그대로다.

    테스트 코드: DD-025
    """
    # given: 계약완료·Won의 이름을 바꾼 코드 목록
    renamed = default_catalog(contract_completed="수주확정", won="성사")

    # when: 계약완료로 바꾸고 Won에서 벗어나는 계획을 세운다
    assert isinstance(plan_change(OPEN, _status("contract_completed"), renamed), NeedRevenue)
    # then: 종결은 매출 필요, Won 이탈은 Status 선택 필요다
    assert isinstance(plan_change(WON, _forecast("best"), renamed), AskStatus)

"""Deal 응답의 next_action.action_id: 기준 행(RK-R1)의 Action id를 JSON 정수로 낸다."""

from datetime import date
from typing import Any

from app.application.deal.dto import DealView
from app.application.ports.deal_repository import DealListItem, NextActionSummary
from app.domain.auth.principal import Role
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from app.domain.user.value_objects import UserRef
from app.main import create_app
from app.web.schemas.deal_response import DealDetailResponse, DealRowResponse
from tests.factories import NOW, make_deal
from tests.factories_contact import make_customer
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings
from tests.support.user_ids import OWNER_ID

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
NEXT_ACTION_KEYS = {"text", "due_date", "status", "action_id"}


def _view(next_action: NextActionSummary | None) -> DealView:
    return DealView(
        item=DealListItem(
            deal=make_deal(NOW, status_key="introduction", forecast_key="best"),
            next_action=next_action,
            earliest_open_due=None,
            last_updated_on=date(2026, 1, 1),
            license_contract_count=0,
            has_issued_license_contract=False,
            unread_comment_count=0,
        ),
        owner=UserRef(id=OWNER_ID, name="김영업", resigned=False, role=Role.SALES),
        customer=make_customer(),
        partner_contacts={},
        risk=None,
        status_days=0,
        vendor=None,
    )


def test_row_and_detail_carry_the_basis_action_id_as_an_integer() -> None:
    """목록 행과 상세의 next_action은 키가 정확히 text·due_date·status·action_id이고 id는 정수다.

    테스트 코드: RK-089
    """
    # given: 기준 행(Action id 41)이 있는 Deal 화면 값이다
    summary = NextActionSummary(
        text="견적 발송",
        due_date=date(2026, 1, 5),
        status=NextActionStatus.OPEN,
        action_id=DealActionId(41),
    )

    # when: 행과 상세 응답을 JSON으로 만든다
    row = DealRowResponse.from_view(_view(summary)).model_dump(mode="json")
    detail = DealDetailResponse.from_view(_view(summary)).model_dump(mode="json")

    # then: next_action의 키가 정확하고 action_id는 기준 행 id(JSON 정수)다
    for body in (row, detail):
        assert set(body["next_action"]) == NEXT_ACTION_KEYS
        assert body["next_action"]["action_id"] == 41
        assert type(body["next_action"]["action_id"]) is int
        assert body["next_action"]["due_date"] == "2026-01-05"
        assert body["next_action"]["status"] == "open"


def test_next_action_is_null_when_there_is_no_basis_row() -> None:
    """Next Action이 하나도 없는 Deal은 next_action이 null이다.

    테스트 코드: RK-089
    """
    # when: 기준 행이 없는 Deal의 행·상세 응답을 만든다
    row = DealRowResponse.from_view(_view(None)).model_dump(mode="json")
    detail = DealDetailResponse.from_view(_view(None)).model_dump(mode="json")

    # then: next_action 키는 있고 값은 null이다
    assert row["next_action"] is None
    assert detail["next_action"] is None


def test_openapi_requires_action_id_as_a_non_null_integer() -> None:
    """OpenAPI의 next_action 객체 스키마에서 action_id는 required integer(null 불가)다.

    테스트 코드: RK-089
    """
    # given: Fake 유스케이스로 만든 앱
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())

    # when: OpenAPI 스키마를 만든다
    schema: dict[str, Any] = app.openapi()["components"]["schemas"]["NextActionResponse"]

    # then: action_id가 필수이고 integer이며 null 허용이 아니다
    assert "action_id" in schema["required"]
    prop = schema["properties"]["action_id"]
    assert prop["type"] == "integer"
    assert "anyOf" not in prop

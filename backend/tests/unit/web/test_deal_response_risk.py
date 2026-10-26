"""Deal 응답의 risk·status_changed_at·status_days(P3 AC-01·10): 행과 상세가 같은 값을 노출한다."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from app.application.deal.dto import DealView
from app.application.ports.deal_repository import DealListItem
from app.domain.auth.principal import Role
from app.domain.deal.risk import Risk
from app.domain.user.value_objects import UserRef
from app.main import create_app
from app.web.schemas.deal_response import DealDetailResponse, DealRowResponse
from tests.factories import NOW, later, make_deal
from tests.factories_contact import make_customer
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from collections.abc import Callable

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
RISK_VALUES = {"overdue", "stale", "overdue_stale"}


def _view(*, risk: Risk | None, status_days: int) -> DealView:
    deal = make_deal(NOW, status_key="introduction", forecast_key="best")
    deal.touch(later(300))
    return DealView(
        item=DealListItem(deal=deal, next_action=None, last_updated_at=deal.created_at),
        owner=UserRef(id=OWNER_ID, name="김영업", resigned=False, role=Role.SALES),
        customer=make_customer(),
        partner_contacts={},
        risk=risk,
        status_days=status_days,
        vendor=None,
    )


def _schema(name: str) -> dict[str, Any]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases())
    schemas: dict[str, Any] = app.openapi()["components"]["schemas"]
    return dict(schemas[name])


def test_row_and_detail_expose_risk_status_changed_at_and_status_days(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")
    view = _view(risk=Risk.OVERDUE_STALE, status_days=6)

    row = DealRowResponse.from_view(view).model_dump(mode="json")
    detail = DealDetailResponse.from_view(view).model_dump(mode="json")

    for body in (row, detail):
        assert body["risk"] == "overdue_stale"
        assert body["status_days"] == 6
        # 시간 기준 서버 통일(AC2): 같은 순간(NOW=2026-01-01T09:00Z)을 서버 오프셋 문자열로 낸다.
        # 'Z' 비교를 '+09:00' 정확 비교로 바꾼 것이며 순간 일치는 아래 fromisoformat 단언이 지킨다.
        assert body["status_changed_at"] == "2026-01-01T18:00:00+09:00"
        assert datetime.fromisoformat(body["status_changed_at"]) == NOW
    assert row["updated_at"] != row["status_changed_at"]  # 진입 시각은 수정 시각과 다른 값이다


@pytest.mark.parametrize("risk", list(Risk))
def test_each_risk_value_is_serialized_as_its_key(risk: Risk) -> None:
    body = DealRowResponse.from_view(_view(risk=risk, status_days=0)).model_dump(mode="json")

    assert body["risk"] == risk.value


def test_no_risk_is_serialized_as_null() -> None:
    body = DealRowResponse.from_view(_view(risk=None, status_days=0)).model_dump(mode="json")

    assert "risk" in body
    assert body["risk"] is None


def test_status_changed_at_is_the_deal_entry_time_not_the_update_time() -> None:
    view = _view(risk=None, status_days=0)
    deal = view.item.deal

    response = DealRowResponse.from_view(view)

    assert response.status_changed_at == deal.status_changed_at
    assert response.status_changed_at == NOW
    assert response.updated_at - response.status_changed_at == timedelta(seconds=300)


@pytest.mark.parametrize("name", ["DealRowResponse", "DealDetailResponse"])
def test_openapi_lists_the_risk_enum_and_requires_the_new_fields(name: str) -> None:
    schema = _schema(name)
    properties = schema["properties"]
    new_fields = {"risk", "status_changed_at", "status_days"}
    assert new_fields <= set(properties)
    assert new_fields <= set(schema["required"])
    options = properties["risk"].get("anyOf", [properties["risk"]])
    enum_values = {value for option in options for value in option.get("enum", [])}
    assert enum_values == RISK_VALUES
    assert any(option.get("type") == "null" for option in options)
    assert properties["status_days"]["type"] == "integer"


@pytest.mark.parametrize("response_type", [DealRowResponse, DealDetailResponse])
def test_every_timestamp_of_a_deal_response_carries_the_server_offset(
    response_type: type[DealRowResponse] | type[DealDetailResponse],
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")
    body = response_type.from_view(_view(risk=None, status_days=0)).model_dump(mode="json")

    for field in ("created_at", "updated_at", "status_changed_at", "last_updated_at"):
        assert field in body, field
        assert body[field].endswith("+09:00"), (field, body[field])
    assert body["created_at"].endswith("+09:00")

"""Deal 응답의 vendor·solution(AC-13): `{id, name}` 또는 null. 구 문자열 필드는 없다."""

from uuid import uuid4

from app.application.deal.dto import DealView, NamedRef
from app.application.ports.deal_repository import DealListItem
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserRef
from app.web.schemas.deal_response import DealDetailResponse, DealRowResponse
from tests.factories import NOW, make_deal
from tests.factories_contact import make_customer
from tests.support.user_ids import OWNER_ID


def _view(vendor: NamedRef | None, solution: NamedRef | None) -> DealView:
    deal = make_deal(
        NOW,
        vendor_id=vendor.id if vendor else None,
        solution_id=solution.id if solution else None,
    )
    return DealView(
        item=DealListItem(deal=deal, next_action=None, last_updated_at=deal.updated_at),
        owner=UserRef(id=OWNER_ID, name="김영업", resigned=False, role=Role.SALES),
        customer=make_customer(),
        partner_contacts={},
        risk=None,
        status_days=0,
        vendor=vendor,
        solution=solution,
    )


def test_vendor_and_solution_are_id_name_objects() -> None:
    vendor, solution = NamedRef(uuid4(), "SAP"), NamedRef(uuid4(), "S/4HANA")
    view = _view(vendor, solution)

    for response in (DealRowResponse.from_view(view), DealDetailResponse.from_view(view)):
        body = response.model_dump(mode="json")
        assert body["vendor"] == {"id": str(vendor.id), "name": "SAP"}
        assert body["solution"] == {"id": str(solution.id), "name": "S/4HANA"}


def test_a_deal_without_vendor_and_solution_has_nulls() -> None:
    body = DealRowResponse.from_view(_view(None, None)).model_dump(mode="json")

    assert "vendor" in body
    assert body["vendor"] is None
    assert body["solution"] is None


def test_a_vendor_without_solution_has_a_null_solution() -> None:
    body = DealRowResponse.from_view(_view(NamedRef(uuid4(), "SAP"), None)).model_dump(mode="json")

    assert body["vendor"]["name"] == "SAP"
    assert body["solution"] is None

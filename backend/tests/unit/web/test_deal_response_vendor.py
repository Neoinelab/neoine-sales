"""Deal 응답의 vendor·solution(AC-6): vendor는 `{id, name}` 또는 null, solution은 문자열."""

from app.application.deal.dto import DealView, NamedRef
from app.application.ports.deal_repository import DealListItem
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserRef
from app.web.schemas.deal_response import DealDetailResponse, DealRowResponse
from tests.factories import NOW, make_deal
from tests.factories_contact import make_customer
from tests.support.ids import new_id
from tests.support.user_ids import OWNER_ID


def _view(vendor: NamedRef | None, solution: str = "S/4HANA") -> DealView:
    deal = make_deal(NOW, vendor_id=vendor.id if vendor else None, solution=solution)
    return DealView(
        item=DealListItem(deal=deal, next_action=None, last_updated_at=deal.updated_at),
        owner=UserRef(id=OWNER_ID, name="김영업", resigned=False, role=Role.SALES),
        customer=make_customer(),
        partner_contacts={},
        risk=None,
        status_days=0,
        vendor=vendor,
    )


def test_vendor_is_an_id_name_object() -> None:
    vendor = NamedRef(new_id(), "SAP")
    view = _view(vendor, "S/4HANA")

    for response in (DealRowResponse.from_view(view), DealDetailResponse.from_view(view)):
        body = response.model_dump(mode="json")
        assert body["vendor"] == {"id": vendor.id, "name": "SAP"}
        assert type(body["vendor"]["id"]) is int


def test_response_solution_is_plain_string() -> None:
    view = _view(NamedRef(new_id(), "SAP"), "ITDR")

    for response in (DealRowResponse.from_view(view), DealDetailResponse.from_view(view)):
        body = response.model_dump(mode="json")
        assert body["solution"] == "ITDR"
        assert type(body["solution"]) is str


def test_a_deal_without_a_vendor_has_a_null_vendor_and_keeps_the_solution_text() -> None:
    body = DealDetailResponse.from_view(_view(None, "ITDR")).model_dump(mode="json")

    assert "vendor" in body
    assert body["vendor"] is None
    assert body["solution"] == "ITDR"

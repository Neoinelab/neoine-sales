"""Deal 응답의 vendor·solution: vendor는 `{id, name}` 또는 null, solution은 문자열."""

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
        item=DealListItem(
            deal=deal,
            next_action=None,
            last_updated_at=deal.updated_at,
            license_contract_count=0,
            has_issued_license_contract=False,
        ),
        owner=UserRef(id=OWNER_ID, name="김영업", resigned=False, role=Role.SALES),
        customer=make_customer(),
        partner_contacts={},
        risk=None,
        status_days=0,
        vendor=vendor,
    )


def test_vendor_is_an_id_name_object() -> None:
    """Deal 응답의 vendor는 정수 id와 이름을 가진 객체다."""
    # given: Vendor SAP를 가진 Deal 보기
    vendor = NamedRef(new_id(), "SAP")
    view = _view(vendor, "S/4HANA")

    # when·then: 목록 행·상세 응답으로 바꾸면 vendor가 id(정수)와 이름 객체다
    for response in (DealRowResponse.from_view(view), DealDetailResponse.from_view(view)):
        body = response.model_dump(mode="json")
        assert body["vendor"] == {"id": vendor.id, "name": "SAP"}
        assert type(body["vendor"]["id"]) is int


def test_response_solution_is_plain_string() -> None:
    """Deal 응답의 solution은 평범한 문자열이다."""
    # given: Solution ITDR을 가진 Deal 보기
    view = _view(NamedRef(new_id(), "SAP"), "ITDR")

    # when·then: 목록 행·상세 응답으로 바꾸면 solution이 문자열 ITDR이다
    for response in (DealRowResponse.from_view(view), DealDetailResponse.from_view(view)):
        body = response.model_dump(mode="json")
        assert body["solution"] == "ITDR"
        assert type(body["solution"]) is str


def test_a_deal_without_a_vendor_has_a_null_vendor_and_keeps_the_solution_text() -> None:
    """Vendor가 없는 Deal은 vendor가 null이고 solution 텍스트는 유지된다."""
    # when: Vendor 없는 Deal 보기를 상세 응답으로 바꾼다
    body = DealDetailResponse.from_view(_view(None, "ITDR")).model_dump(mode="json")

    # then: vendor 키는 있고 null이며 solution은 그대로다
    assert "vendor" in body
    assert body["vendor"] is None
    assert body["solution"] == "ITDR"

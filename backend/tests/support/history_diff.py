"""Deal History diff 테스트 공용 준비: 이름 조회 대역, 기준 Deal, 변경 적용 도우미."""

import dataclasses
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.domain.bant.values import BantLabelId
from app.domain.deal.history import diff_deal
from app.domain.deal.values import RevenueAmount
from tests.factories import NOW, make_deal
from tests.support.user_ids import OWNER_ID, uid

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.deal.entities import Deal
    from app.domain.user.value_objects import UserId

CUSTOMER = UUID(int=1)
OTHER_CUSTOMER = UUID(int=2)
PARTNER_1 = UUID(int=11)
PARTNER_2 = UUID(int=12)
LABEL_FULL_BUDGET = BantLabelId(UUID(int=21))
LABEL_CEO = BantLabelId(UUID(int=22))
LABELS = {LABEL_FULL_BUDGET: "풀 예산 확보", LABEL_CEO: "CEO 보고 완료"}
STATUSES = {
    "prospecting": "기회발굴",
    "price_negotiation": "가격협상",
    "introduction": "제품소개",
    "contract_completed": "계약완료",
}
FORECASTS = {"pipeline": "Pipeline", "commit": "Commit", "best": "Best", "won": "Won"}
CONTACTS = {
    CUSTOMER: "한빛은행 정민수",
    OTHER_CUSTOMER: "대한상사 오세훈",
    PARTNER_1: "코어테크 민지훈",
    PARTNER_2: "에이원시스템 표성호",
}
USERS = {
    OWNER_ID: "기본 담당",
    uid("kim"): "김영업",
    uid("park"): "박영업",
    uid("lee"): "이영업(퇴사)",
}
CODE = "20261016-A7K2"
Row = tuple[str, str, str, str]  # (category, target, before, after)


class Lookup:
    """표시용 이름 조회 대역(코드 이름·사용자 표기·연락처 표기·Label 이름)."""

    def status_name(self, key: str) -> str:
        return STATUSES[key]

    def forecast_name(self, key: str) -> str:
        return FORECASTS[key]

    def user_label(self, user_id: UserId) -> str:
        return USERS[user_id]

    def contact_name(self, contact_id: UUID) -> str:
        return CONTACTS[contact_id]

    def label_name(self, label_id: BantLabelId | None) -> str:
        return "선택 안 함" if label_id is None else LABELS[label_id]


def base_deal(**overrides: Any) -> Deal:  # noqa: ANN401
    values: dict[str, Any] = {
        "code": CODE,
        "customer_id": CUSTOMER,
        "partner_id": PARTNER_1,
        "owner_user_id": uid("kim"),
        "status_key": "price_negotiation",
        "forecast_key": "commit",
        "revenue_amount": 1_000,
        "revenue_date": date(2026, 12, 1),
        "name": "A",
        "vendor": "V",
        "solution": "S",
        **overrides,
    }
    return make_deal(NOW, **values)


def revise_with(deal: Deal, **parts: Any) -> None:  # noqa: ANN401
    """폼 저장(revise)에서 일부 부분만 바꾼다(details, sync, customer_id, bant)."""
    values: dict[str, Any] = {
        "details": deal.details,
        "sync": deal.sync,
        "customer_id": deal.customer_id,
        "bant": deal.bant,
        **parts,
    }
    deal.revise(**values)


def edit_of(field: str, value: object) -> Callable[[Deal], None]:
    """base_deal의 details 한 필드를 바꾸는 변경(revise). 금액은 int를 준다."""

    def apply(deal: Deal) -> None:
        converted = RevenueAmount(value) if field == "revenue_amount" else value  # type: ignore[arg-type]
        changes: dict[str, Any] = {field: converted}
        revise_with(deal, details=dataclasses.replace(deal.details, **changes))

    return apply


def rows_of(before: Any, after: Any) -> list[Row]:  # noqa: ANN401
    drafts = diff_deal(before, after, Lookup())
    return [(str(d.category), d.target, d.before, d.after) for d in drafts]


def diff_after(change: Callable[[Deal], object], deal: Deal | None = None) -> list[Row]:
    """기준 Deal에 change를 적용한 전후 스냅숏의 diff를 (category, target, before, after)로."""
    target = deal or base_deal()
    before = target.snapshot()
    change(target)
    return rows_of(before, target.snapshot())

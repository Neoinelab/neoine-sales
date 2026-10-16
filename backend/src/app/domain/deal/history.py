"""Deal History: 변경 기록 값과 변경 전후 비교(diff).

`diff_deal`은 프런트 `shared/model/history.ts`의 `diffDeal`과 같은 순서·target·표기를 쓴다.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.domain.bant.values import BantCategory
from app.domain.common.korean import with_wa
from app.domain.common.krw import format_krw_full
from app.domain.contact.values import ContactKind
from app.domain.deal.sync import CoChange, SyncField

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from app.domain.bant.values import BantLabelId
    from app.domain.contact.values import ContactDetails, ContactId
    from app.domain.deal.code import DealCode
    from app.domain.deal.sync import SyncState
    from app.domain.deal.values import BantSelection, DealDetails, Poc, Quote
    from app.domain.user.value_objects import UserId

TARGET_MAX = 300
TEXT_MAX = 1000
ELLIPSIS = "…"
NO_PARTNER = "없음"
BANT_TARGET_NAMES = {
    BantCategory.BUDGET: "Budget",
    BantCategory.AUTHORITY: "Authority",
    BantCategory.NEED: "Need",
    BantCategory.TIMELINE: "Timeline",
}


class HistoryCategory(StrEnum):
    """History 구분. 값은 프런트 `HistoryCategory` 타입 그대로다."""

    CREATED = "created"
    STATUS = "status"
    FORECAST = "forecast"
    AMOUNT = "amount"
    EXPECTED_CLOSE = "expectedClose"
    OWNER = "owner"
    PARTNER = "partner"
    CONTACT = "contact"
    BANT = "bant"
    ACTION = "action"
    ATTACHMENT = "attachment"
    OTHER = "other"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + ELLIPSIS


@dataclass(frozen=True, slots=True)
class HistoryDraft:
    """History 한 건의 내용(구분, 대상, 전, 후). 너무 긴 값은 잘라 저장 한도를 지킨다."""

    category: HistoryCategory
    target: str
    before: str
    after: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", _clip(self.target, TARGET_MAX))
        object.__setattr__(self, "before", _clip(self.before, TEXT_MAX))
        object.__setattr__(self, "after", _clip(self.after, TEXT_MAX))


@dataclass(frozen=True, slots=True)
class DealHistoryEntry:
    """저장되는 History 항목. id는 저장할 때 DB가 정한다(저장 전에는 None)."""

    id: int | None
    deal_code: DealCode
    changed_at: datetime
    changed_by: UserId
    draft: HistoryDraft


@dataclass(frozen=True, slots=True)
class DealSnapshot:
    """변경 전후 비교에 필요한 Deal의 값(이후 Deal이 바뀌어도 변하지 않는다)."""

    sync: SyncState
    details: DealDetails
    customer_id: ContactId
    active_partner_id: ContactId | None
    bant: BantSelection


class HistoryLookup(Protocol):
    """값을 사람이 읽는 문자열로 바꾸는 조회(코드 이름, 사용자 표기, 연락처 표기, Label 이름)."""

    def status_name(self, key: str) -> str: ...

    def forecast_name(self, key: str) -> str: ...

    def user_label(self, user_id: UserId) -> str:
        """퇴사자는 '이름(퇴사)'."""
        ...

    def contact_name(self, contact_id: ContactId) -> str:
        """'회사 이름' 형식."""
        ...

    def label_name(self, label_id: BantLabelId | None) -> str:
        """없으면 '선택 안 함'."""
        ...


def created_draft() -> HistoryDraft:
    return HistoryDraft(HistoryCategory.CREATED, "Deal 등록", "", "Deal 등록")


def contact_info_text(details: ContactDetails) -> str:
    """'직급 X · 이메일 Y · 전화 Z'. 없는 값은 '-'."""
    email = details.email.value if details.email else "-"
    phone = details.phone.value if details.phone else "-"
    return f"직급 {details.title or '-'} · 이메일 {email} · 전화 {phone}"


def contact_change_target(role: ContactKind, details: ContactDetails) -> str:
    label = "고객" if role is ContactKind.CUSTOMER else "파트너"
    return f"{label} 연락처 정보 ({details.company} {details.name})"


def diff_deal(
    before: DealSnapshot,
    after: DealSnapshot,
    lookup: HistoryLookup,
    co_changed: Sequence[CoChange] = (),
) -> list[HistoryDraft]:
    """바뀐 필드마다 한 건, 고정 순서. 바뀐 것이 없으면 빈 목록."""
    pairs = [
        *_sync_pairs(before, after, lookup, {c.field for c in co_changed}),
        *_money_pairs(before.details, after.details),
        *_people_pairs(before, after, lookup),
        *_bant_pairs(before.bant, after.bant, lookup),
        *_detail_pairs(before.details, after.details),
    ]
    return [HistoryDraft(c, t, b, a) for c, t, b, a in pairs if b != a]


type _Pair = tuple[HistoryCategory, str, str, str]


def _noted(name: str, co_changed: bool, other: str) -> str:
    return f"{name} ({with_wa(other)} 함께 변경)" if co_changed else name


def _sync_pairs(
    before: DealSnapshot, after: DealSnapshot, lookup: HistoryLookup, co: set[SyncField]
) -> list[_Pair]:
    status_after = lookup.status_name(after.sync.status_key)
    forecast_after = lookup.forecast_name(after.sync.forecast_key)
    return [
        (
            HistoryCategory.STATUS,
            "Status",
            lookup.status_name(before.sync.status_key),
            _noted(status_after, SyncField.STATUS in co, f"Forecast {forecast_after}"),
        ),
        (
            HistoryCategory.FORECAST,
            "Forecast",
            lookup.forecast_name(before.sync.forecast_key),
            _noted(forecast_after, SyncField.FORECAST in co, f"Status {status_after}"),
        ),
    ]


def _money_pairs(before: DealDetails, after: DealDetails) -> list[_Pair]:
    return [
        (
            HistoryCategory.AMOUNT,
            "금액",
            format_krw_full(before.revenue_amount.value),
            format_krw_full(after.revenue_amount.value),
        ),
        (
            HistoryCategory.EXPECTED_CLOSE,
            "Expected Close",
            before.revenue_date.isoformat(),
            after.revenue_date.isoformat(),
        ),
    ]


def _partner_text(partner_id: ContactId | None, lookup: HistoryLookup) -> str:
    return NO_PARTNER if partner_id is None else lookup.contact_name(partner_id)


def _people_pairs(before: DealSnapshot, after: DealSnapshot, lookup: HistoryLookup) -> list[_Pair]:
    return [
        (
            HistoryCategory.OWNER,
            "Owner",
            lookup.user_label(before.details.owner_user_id),
            lookup.user_label(after.details.owner_user_id),
        ),
        (
            HistoryCategory.PARTNER,
            "파트너",
            _partner_text(before.active_partner_id, lookup),
            _partner_text(after.active_partner_id, lookup),
        ),
        (
            HistoryCategory.CONTACT,
            "고객 연락처",
            lookup.contact_name(before.customer_id),
            lookup.contact_name(after.customer_id),
        ),
    ]


def _bant_pairs(before: BantSelection, after: BantSelection, lookup: HistoryLookup) -> list[_Pair]:
    return [
        (
            HistoryCategory.BANT,
            f"BANT Label: {BANT_TARGET_NAMES[category]}",
            lookup.label_name(before.get(category)),
            lookup.label_name(after.get(category)),
        )
        for category in BantCategory
    ]


def _dated(value: str | None, day: object) -> str:
    return f"{value or '-'}{f' ({day})' if day else ''}"


def _quote_text(quote: Quote) -> str:
    submitted = quote.submitted.value if quote.submitted else None
    return _dated(submitted, quote.submitted_date)


def _poc_text(poc: Poc) -> str:
    return _dated(poc.state.value if poc.state else None, poc.completed_date)


def _detail_pairs(before: DealDetails, after: DealDetails) -> list[_Pair]:
    other = HistoryCategory.OTHER
    return [
        (other, "Deal Name", before.name, after.name),
        (other, "Vendor", before.vendor, after.vendor),
        (other, "Solution", before.solution, after.solution),
        (other, "Users", _number_text(before.users), _number_text(after.users)),
        (other, "견적", _quote_text(before.quote), _quote_text(after.quote)),
        (other, "POC", _poc_text(before.poc), _poc_text(after.poc)),
        (other, "구매절차", before.procurement or "-", after.procurement or "-"),
    ]


def _number_text(value: int | None) -> str:
    return "-" if value is None else str(value)

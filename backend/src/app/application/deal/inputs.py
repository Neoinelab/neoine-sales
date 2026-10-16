"""Deal 유스케이스 입력(원시 타입). 값의 형식 검증은 도메인 값 객체와 `validation.py`가 한다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.application.contact.inputs import ContactInput

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date
    from uuid import UUID

    from app.domain.auth.principal import Role
    from app.domain.bant.values import BantCategory
    from app.domain.contact.values import ContactKind
    from app.domain.deal.sync import SyncResolution
    from app.domain.deal.values import PocState, QuoteSubmitted
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class Actor:
    """요청자: 로그인한 사용자의 users.id와 역할."""

    user_id: UserId
    role: Role


@dataclass(frozen=True, slots=True)
class ContactDraftInput:
    """Deal 화면의 연락처 입력. contact_id가 있으면 그 연락처를 골라 입력값으로 갱신한다."""

    contact_id: UUID | None
    company: str
    name: str
    title: str | None
    email: str | None
    phone: str | None

    def to_contact_input(self, kind: ContactKind) -> ContactInput:
        """연락처 규칙 검증용 입력. 제목은 앞뒤 공백을 지우고 빈 이메일·전화는 없는 값이다."""
        return ContactInput(
            kind=kind,
            company=self.company,
            name=self.name,
            title=(self.title or "").strip() or None,
            email=self.email or None,
            phone=self.phone or None,
        )


@dataclass(frozen=True, slots=True)
class DealChangeInput:
    """단일 필드 변경. 함께 바뀌는 값은 resolution으로 받아 서버가 같은 규칙으로 다시 검증한다."""

    field: Literal["status_key", "forecast_key", "revenue_amount", "revenue_date"]
    value: str | int | date
    resolution: SyncResolution | None = None


@dataclass(frozen=True, slots=True)
class DealCreateInput:
    name: str
    owner_user_id: UUID
    vendor: str
    solution: str
    users: int | None
    status_key: str
    forecast_key: str
    revenue_amount: int
    revenue_date: date | None
    customer: ContactDraftInput
    partner: ContactDraftInput | None
    quote_submitted: QuoteSubmitted | None
    quote_submitted_date: date | None
    poc_state: PocState | None
    poc_completed_date: date | None
    procurement: str
    bant: Mapping[BantCategory, UUID | None]  # 빠진 구분은 선택 안 함


@dataclass(frozen=True, slots=True, kw_only=True)
class DealPatchInput:
    """수정 입력. `provided`에 든 필드만 반영한다(값이 None이어도 보낸 값이다).

    partner가 provided에 있고 None이면 활성 파트너를 제거한다.
    """

    provided: frozenset[str]
    name: str | None = None
    owner_user_id: UUID | None = None
    vendor: str | None = None
    solution: str | None = None
    users: int | None = None
    status_key: str | None = None
    forecast_key: str | None = None
    revenue_amount: int | None = None
    revenue_date: date | None = None
    customer: ContactDraftInput | None = None
    partner: ContactDraftInput | None = None
    quote_submitted: QuoteSubmitted | None = None
    quote_submitted_date: date | None = None
    poc_state: PocState | None = None
    poc_completed_date: date | None = None
    procurement: str | None = None
    bant: Mapping[BantCategory, UUID | None] | None = None

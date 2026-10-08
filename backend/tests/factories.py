"""테스트용 엔티티·값 객체 생성 도우미. 기본은 유효한 더미 값이고 overrides로 일부만 바꾼다."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.application.customer.inputs import CustomerInput
from app.application.deal.inputs import DealInput, StageChangeInput
from app.application.deal_action.inputs import DealActionInput
from app.application.partner.inputs import PartnerInput
from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.money import Money
from app.domain.customer.entities import Customer
from app.domain.customer.value_objects import CustomerDetails, CustomerId
from app.domain.deal.entities import Deal
from app.domain.deal.stage import DealStage, DealStageChange, DealStageChangeId, StageChanger
from app.domain.deal.value_objects import DealCode, DealDetails, DealId
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.value_objects import ActionType, DealActionDetails
from app.domain.partner.entities import Partner
from app.domain.partner.value_objects import PartnerDetails

NOW = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def later(seconds: int = 60) -> datetime:
    return NOW + timedelta(seconds=seconds)


def make_customer_details(**overrides: object) -> CustomerDetails:
    values: dict[str, Any] = {
        "company_name": "네오인",
        "contact_name": "김철수",
        "contact_title": "팀장",
        "email": Email("kim@neoine.example"),
        "phone": PhoneNumber("010-1234-5678"),
        "employee_count": 120,
        "notes": "초기 미팅 완료",
    }
    return CustomerDetails(**{**values, **overrides})


def make_customer(now: datetime = NOW, **overrides: object) -> Customer:
    return Customer.create(make_customer_details(**overrides), now)


def make_partner_details(**overrides: object) -> PartnerDetails:
    values: dict[str, Any] = {
        "company_name": "한빛파트너스",
        "contact_name": "이영희",
        "contact_title": "이사",
        "email": Email("lee@hanbit.example"),
        "phone": PhoneNumber("02-123-4567"),
    }
    return PartnerDetails(**{**values, **overrides})


def make_partner(now: datetime = NOW, **overrides: object) -> Partner:
    return Partner.create(make_partner_details(**overrides), now)


def make_deal_details(**overrides: object) -> DealDetails:
    code = overrides.get("code")
    if isinstance(code, str):  # 편의: 문자열 코드를 DealCode로 변환
        overrides["code"] = DealCode(code)
    values: dict[str, Any] = {
        "code": DealCode("DEAL-001"),
        "name": "ERP 구축",
        "owner": "박영업",
        "vendor": "SAP",
        "solution": "S/4HANA",
        "revenue": Money(Decimal("150000000")),
        "revenue_date": date(2026, 6, 30),
        "customer_id": CustomerId(uuid4()),
        "partner_id": None,
    }
    return DealDetails(**{**values, **overrides})


def make_deal(now: datetime = NOW, **overrides: object) -> Deal:
    """overrides는 DealDetails 값이고, owner_user_id(등록 사용자 subject)만 엔티티 속성이다."""
    owner_user_id = overrides.pop("owner_user_id", None)
    details = make_deal_details(**overrides)
    if owner_user_id is None:
        return Deal.create(details, now)
    assert isinstance(owner_user_id, str)
    return Deal.create(details, now, owner_user_id=owner_user_id)


def make_customer_input(**overrides: object) -> CustomerInput:
    values: dict[str, Any] = {
        "company_name": "네오인",
        "contact_name": "김철수",
        "contact_title": "팀장",
        "email": "Kim@Neoine.Example",
        "phone": "010-1234-5678",
        "employee_count": 120,
        "notes": "초기 미팅 완료",
    }
    return CustomerInput(**{**values, **overrides})


def make_partner_input(**overrides: object) -> PartnerInput:
    values: dict[str, Any] = {
        "company_name": "한빛파트너스",
        "contact_name": "이영희",
        "contact_title": "이사",
        "email": "lee@hanbit.example",
        "phone": "02-123-4567",
    }
    return PartnerInput(**{**values, **overrides})


def make_deal_input(customer_id: UUID, **overrides: object) -> DealInput:
    values: dict[str, Any] = {
        "code": "deal-001",
        "name": "ERP 구축",
        "owner": "박영업",
        "vendor": "SAP",
        "solution": "S/4HANA",
        "revenue_amount": Decimal("150000000"),
        "revenue_date": date(2026, 6, 30),
        "customer_id": customer_id,
    }
    return DealInput(**{**values, **overrides})


def make_deal_action_details(**overrides: object) -> DealActionDetails:
    values: dict[str, Any] = {
        "deal_id": DealId(uuid4()),
        "action_type": ActionType.MEETING,
        "title": "킥오프 미팅",
        "content": "요구사항 정리",
        "acted_at": NOW,
        "actor": "박영업",
    }
    return DealActionDetails(**{**values, **overrides})


def make_deal_action(now: datetime = NOW, **overrides: object) -> DealAction:
    return DealAction.create(make_deal_action_details(**overrides), now)


def make_deal_action_input(**overrides: object) -> DealActionInput:
    values: dict[str, Any] = {
        "action_type": ActionType.MEETING,
        "title": "킥오프 미팅",
        "content": "요구사항 정리",
        "acted_at": NOW,
        "actor": "박영업",
    }
    return DealActionInput(**{**values, **overrides})


def make_stage_changer(**overrides: object) -> StageChanger:
    values: dict[str, Any] = {"subject": "dev-user", "name": "개발 사용자(sales)"}
    return StageChanger(**{**values, **overrides})


def make_stage_change(**overrides: object) -> DealStageChange:
    """유효한 단계 이력 한 건(기본: 기회발굴 → 제품소개)."""
    values: dict[str, Any] = {
        "id": DealStageChangeId(uuid4()),
        "deal_id": DealId(uuid4()),
        "from_stage": DealStage.PROSPECTING,
        "to_stage": DealStage.INTRODUCTION,
        "reason": "제품 소개 완료",
        "changed_by": make_stage_changer(),
        "changed_at": NOW,
    }
    return DealStageChange(**{**values, **overrides})


def make_stage_change_input(**overrides: object) -> StageChangeInput:
    values: dict[str, Any] = {
        "stage": DealStage.INTRODUCTION,
        "reason": None,
        "changed_by_subject": "dev-user",
        "changed_by_name": "개발 사용자(sales)",
    }
    return StageChangeInput(**{**values, **overrides})

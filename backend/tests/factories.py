"""테스트용 엔티티·값 객체 생성 도우미. 기본은 유효한 더미 값이고 overrides로 일부만 바꾼다."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.money import Money
from app.domain.customer.entities import Customer
from app.domain.customer.value_objects import CustomerDetails, CustomerId
from app.domain.deal.entities import Deal
from app.domain.deal.value_objects import DealCode, DealDetails
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
    return Deal.create(make_deal_details(**overrides), now)

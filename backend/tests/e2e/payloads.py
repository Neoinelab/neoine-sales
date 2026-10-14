"""API 요청 본문 도우미. 기본은 유효한 값이고 overrides로 일부만 바꾼다."""

from typing import Any

from tests.support.user_ids import ACTOR_ID, OWNER_ID


def customer_payload(**overrides: object) -> dict[str, Any]:
    values: dict[str, Any] = {
        "company_name": "네오인",
        "contact_name": "김철수",
        "contact_title": "팀장",
        "email": "Kim@Neoine.Example",
        "phone": "010-1234-5678",
        "employee_count": 120,
        "notes": "초기 미팅 완료",
    }
    return {**values, **overrides}


def partner_payload(**overrides: object) -> dict[str, Any]:
    values: dict[str, Any] = {
        "company_name": "한빛파트너스",
        "contact_name": "이영희",
        "contact_title": "이사",
        "email": "lee@hanbit.example",
        "phone": "02-123-4567",
    }
    return {**values, **overrides}


def deal_payload(customer_id: str, **overrides: object) -> dict[str, Any]:
    values: dict[str, Any] = {
        "code": "deal-001",
        "name": "ERP 구축",
        "owner_user_id": str(OWNER_ID),  # deal_users fixture(또는 SQL stack)가 이 사용자를 둔다
        "vendor": "SAP",
        "solution": "S/4HANA",
        "revenue_amount": "150000000",
        "revenue_currency": "KRW",
        "revenue_date": "2026-06-30",
        "customer_id": customer_id,
    }
    return {**values, **overrides}


def action_payload(**overrides: object) -> dict[str, Any]:
    values: dict[str, Any] = {
        "action_type": "meeting",
        "action": "킥오프 미팅",
        "acted_at": "2026-03-02T10:00:00+09:00",
        "actor_user_id": str(ACTOR_ID),
        "next_action": "요구사항 문서 전달",
        "due_date": "2026-03-10",
        "memo": "요구사항 정리",
    }
    return {**values, **overrides}

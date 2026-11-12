"""Deal 등록 요청 본문 도우미(PL 단위 테스트용). 기본은 유효한 값이고 overrides로 일부만 바꾼다."""

from typing import Any

from tests.support.user_ids import OWNER_ID


def deal_payload(**overrides: object) -> dict[str, Any]:
    """Deal 등록 본문(P1 모델): 고객은 ContactDraft로 함께 만들고 Owner는 기본 Owner 사용자다."""
    values: dict[str, Any] = {
        "name": "ERP 구축",
        "owner_user_id": OWNER_ID,  # deal_users fixture(또는 SQL stack)가 이 사용자를 둔다
        "vendor_id": None,  # 등록된 Vendor의 id(없으면 선택 안 함)
        "solution": "S/4HANA",  # 자유 텍스트(필수, 앞뒤 공백 제거 후 1~200자)
        "users": 10,
        "status_key": "prospecting",
        "forecast_key": "pipeline",
        "revenue_amount": 150_000_000,
        "revenue_date": "2026-06-30",
        "customer": {
            "contact_id": None,
            "company": "네오인",
            "name": "김철수",
            "title": "팀장",
            "email": "kim@neoine.example",
            "phone": "010-1234-5678",
        },
        "partner": None,
        "quote": {"submitted": None, "submitted_date": None},
        "poc": {"state": None, "completed_date": None},
        "procurement": "",
        "bant": {"budget": None, "authority": None, "need": None, "timeline": None},
    }
    return {**values, **overrides}

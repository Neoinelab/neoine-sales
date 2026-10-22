"""API 요청 본문 도우미. 기본은 유효한 값이고 overrides로 일부만 바꾼다."""

from typing import TYPE_CHECKING, Any

from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from httpx import AsyncClient

DEALS = "/api/v1/deals"


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


async def create_deal(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    """Deal을 등록하고 응답 본문을 돌려준다. Owner는 기본적으로 로그인한 클라이언트 자신이다."""
    if "owner_user_id" not in overrides:
        me = await client.get("/api/v1/auth/me")
        overrides = {**overrides, "owner_user_id": me.json()["user_id"]}
    response = await client.post(DEALS, json=deal_payload(**overrides))
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body

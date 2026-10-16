"""e2e 구 층(P1·P2에서 폐지될 Deal·활동 테스트)이 연락처를 만들 때 쓰는 도우미.

구 `/customers`·`/partners` 생성 호출을 `/contacts`로 바꾸면 연락처 등록이 admin 전용이라
sales 클라이언트(`client`, `stack`, `stack_for`)로는 만들 수 없다. conftest의 fixture가 같은 앱에
admin 클라이언트를 따로 열어 `set_admin`으로 알려 두고, 이 모듈의 `post_customer`/`post_partner`가
그 admin으로 등록한다. 응답(Response)을 그대로 돌려주므로 호출부는 `.json()["id"]`를 이전과 같게
쓴다. 기본 담당자명은 호출마다 달라서(같은 사람 중복 거절을 피한다) 이전처럼 기본 값으로 여러 건을
만들 수 있다.
"""

import itertools
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from httpx import AsyncClient, Response

CONTACTS = "/api/v1/contacts"
CONTACT_ADMIN = "contact-admin"  # 연락처를 대신 등록하는 admin의 로그인 아이디
_COUNTER = itertools.count(1)
_state: dict[str, AsyncClient | None] = {"admin": None}


def set_admin(admin: AsyncClient | None) -> None:
    """지금 쓰는 앱의 admin 클라이언트(fixture가 열고 닫을 때 부른다)."""
    _state["admin"] = admin


def _admin() -> AsyncClient:
    admin = _state["admin"]
    assert admin is not None, "admin 클라이언트가 없다: client/stack fixture를 써야 한다"
    return admin


def _payload(kind: str, defaults: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    values = {"kind": kind, **defaults, **overrides}
    if "name" not in overrides:
        values["name"] = f"담당{next(_COUNTER)}"  # 호출마다 다른 사람
    return values


async def post_customer(**overrides: Any) -> Response:  # noqa: ANN401
    """고객 연락처를 등록한다(overrides: company, name, title, email, phone)."""
    defaults = {"company": "네오인", "title": "팀장", "email": None, "phone": "010-1234-5678"}
    return await _admin().post(CONTACTS, json=_payload("customer", defaults, overrides))


async def post_partner(**overrides: Any) -> Response:  # noqa: ANN401
    """파트너 연락처를 등록한다."""
    defaults = {"company": "한빛파트너스", "title": "이사", "email": None, "phone": "02-123-4567"}
    return await _admin().post(CONTACTS, json=_payload("partner", defaults, overrides))


async def delete_contact(contact_id: object) -> Response:
    """연락처를 삭제한다(admin)."""
    return await _admin().delete(f"{CONTACTS}/{contact_id}")


async def list_contacts(**params: Any) -> Response:  # noqa: ANN401
    """연락처 목록을 본다(admin 전용 API)."""
    return await _admin().get(CONTACTS, params=params)

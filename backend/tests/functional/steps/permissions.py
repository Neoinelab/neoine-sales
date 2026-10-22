"""권한 매트릭스(경로별로 어떤 역할이 쓸 수 있는가)를 한 곳에 둔 표와 권한 step.

새 /api/v1 엔드포인트는 이 표에 한 줄을 더해야 한다(안 하면 "모든 경로가 표에 있다" 시나리오가
실패한다). 값은 그 엔드포인트를 쓸 수 있는 역할 집합이고, None은 로그인 없이 쓰는 공개
엔드포인트다. 경로 형식은 OpenAPI의 경로 템플릿과 같다.
"""

from typing import TYPE_CHECKING, Final

from app.domain.auth.principal import Role
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

Route = tuple[str, str]  # (HTTP 메서드 대문자, 경로 템플릿)

EVERYONE: Final = frozenset({Role.ADMIN, Role.SALES, Role.USER})  # 로그인한 모든 역할
WRITERS: Final = frozenset({Role.ADMIN, Role.SALES})
ADMINS: Final = frozenset({Role.ADMIN})

BUSINESS_READS: Final = (
    ("GET", "/api/v1/contacts/companies"),  # Deal 화면의 연락처 선택: 로그인한 모든 역할
    ("GET", "/api/v1/contacts/by-company"),
    ("GET", "/api/v1/deals"),
    ("GET", "/api/v1/deals/{code}"),
    ("GET", "/api/v1/deals/{code}/deletion-impact"),
    ("GET", "/api/v1/deals/{code}/history"),
    ("GET", "/api/v1/deals/{code}/actions"),
    ("GET", "/api/v1/deal-actions/{action_id}"),  # 전역 검색 GET /deal-actions는 폐지(P2)
    ("GET", "/api/v1/deals/{code}/attachments"),  # P2b: 첨부 목록·단건·다운로드는 모든 역할(Q5)
    ("GET", "/api/v1/attachments/{attachment_id}"),
    ("GET", "/api/v1/attachments/{attachment_id}/download"),
    (
        "GET",
        "/api/v1/user-options",
    ),  # 사용자 선택 UI용: 로그인한 모든 역할(이메일·역할은 노출 안 함)
    ("GET", "/api/v1/codes"),
    ("GET", "/api/v1/bant-labels"),
    ("GET", "/api/v1/action-types"),  # Action 폼·검색의 유형 선택지: 모든 역할
    ("GET", "/api/v1/vendors"),  # Deal 폼·필터의 Vendor 선택지: 모든 역할
    ("GET", "/api/v1/alert-settings"),  # P3: 경고 기준 조회는 모든 역할(목록 범례에 숫자가 필요)
)
BUSINESS_WRITES: Final = (
    ("POST", "/api/v1/bant-labels"),  # 자기 Label을 만든다(user는 조회 전용)
    ("POST", "/api/v1/action-types"),  # 자기 Action 유형을 만든다(user는 조회 전용)
    ("POST", "/api/v1/deals"),
    ("PATCH", "/api/v1/deals/{code}"),
    ("POST", "/api/v1/deals/{code}/changes"),  # Status·Forecast·금액·Expected Close 단일 변경
    ("DELETE", "/api/v1/deals/{code}"),
    ("POST", "/api/v1/deals/{code}/actions"),
    ("PUT", "/api/v1/deal-actions/{action_id}"),
    ("DELETE", "/api/v1/deal-actions/{action_id}"),
    ("POST", "/api/v1/deals/{code}/attachments"),  # P2b: 업로드·삭제는 sales·admin
    ("DELETE", "/api/v1/attachments/{attachment_id}"),
)
ADMIN_ONLY: Final = (
    ("GET", "/api/v1/users"),
    ("GET", "/api/v1/contacts"),  # 연락처 관리(목록·등록·수정·삭제)는 admin 전용
    ("POST", "/api/v1/contacts"),
    ("PUT", "/api/v1/contacts/{contact_id}"),
    ("DELETE", "/api/v1/contacts/{contact_id}"),
    ("GET", "/api/v1/codes/usage"),
    ("POST", "/api/v1/codes"),
    ("PATCH", "/api/v1/codes/{code_id}"),
    ("PUT", "/api/v1/codes/order"),
    ("DELETE", "/api/v1/codes/{code_id}"),
    ("PATCH", "/api/v1/bant-labels/{label_id}"),
    ("DELETE", "/api/v1/bant-labels/{label_id}"),  # 자기가 만든 Label이라도 sales는 403
    ("PATCH", "/api/v1/action-types/{type_id}"),  # Action 유형 이름 변경·삭제는 admin만
    ("DELETE", "/api/v1/action-types/{type_id}"),
    ("POST", "/api/v1/users"),
    ("DELETE", "/api/v1/users/{user_id}"),
    ("GET", "/api/v1/settings/directory"),
    ("PUT", "/api/v1/settings/directory"),
    ("POST", "/api/v1/settings/directory/test"),
    ("GET", "/api/v1/settings/storage"),  # P2b: 파일 저장 위치 조회·변경·쓰기 확인
    ("PUT", "/api/v1/settings/storage"),
    ("POST", "/api/v1/settings/storage/test"),
    ("PUT", "/api/v1/alert-settings"),  # P3: 경고 기준 변경은 admin만
    ("POST", "/api/v1/vendors"),  # Vendor 관리는 생성도 admin만(D11)
    ("PATCH", "/api/v1/vendors/{vendor_id}"),
    ("DELETE", "/api/v1/vendors/{vendor_id}"),
)
PUBLIC: Final = (
    ("GET", "/healthz"),
    ("GET", "/readyz"),
    ("GET", "/api/v1/auth/config"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/dev-login"),
    ("POST", "/api/v1/auth/logout"),
    ("PUT", "/api/v1/auth/setup/directory"),
    ("PUT", "/api/v1/auth/setup/storage"),  # P2b 최초 설정 2단계
    ("POST", "/api/v1/auth/setup/storage/test"),
    ("POST", "/api/v1/auth/setup"),
)
LOGGED_IN_ANY: Final = (("GET", "/api/v1/auth/me"),)

EXPECTED: Final[dict[Route, frozenset[Role] | None]] = {
    **dict.fromkeys(PUBLIC),
    **dict.fromkeys(LOGGED_IN_ANY, EVERYONE),
    **dict.fromkeys(BUSINESS_READS, EVERYONE),
    **dict.fromkeys(BUSINESS_WRITES, WRITERS),
    **dict.fromkeys(ADMIN_ONLY, ADMINS),
}

PLACEHOLDER = str(MISSING_ID)
ABSENT_DEAL_CODE = (
    "20260101-ZZZZ"  # 형식은 맞지만 없는 Deal code(권한 검사는 조회보다 먼저여야 한다)
)
ROLES: Final = (Role.ADMIN, Role.SALES, Role.USER)


def concrete_path(template: str) -> str:
    """경로 템플릿의 `{...}`를 존재하지 않는 값으로 채운다(권한 검사는 조회보다 먼저여야 한다)."""
    out = template
    while "{" in out:
        start = out.index("{")
        end = out.index("}", start)
        out = (
            out[:start]
            + (ABSENT_DEAL_CODE if out[start + 1 : end] == "code" else PLACEHOLDER)
            + out[end + 1 :]
        )
    return out


def protected_routes() -> list[Route]:
    return [route for route, roles in EXPECTED.items() if roles is not None]


def route_id(route: Route) -> str:
    return f"{route[0]} {route[1]}"


def _body(method: str) -> dict[str, object] | None:
    return {} if method in {"POST", "PUT", "PATCH"} else None


async def when_call_route(api: Api, route: Route) -> Response:
    """경로를 비어 있는 본문(POST·PUT)으로 호출한다. 존재하지 않는 id를 쓴다."""
    method, path = route
    return await api.request(method, concrete_path(path), json=_body(method))


async def when_call_route_with_garbage_body(api: Api, route: Route) -> Response:
    """본문 검증에 걸릴 잘못된 본문으로 호출한다(권한 검사가 먼저인지 확인하려는 용도)."""
    method, path = route
    garbage = {"unexpected": ["garbage"]} if method != "DELETE" else None
    return await api.request(method, concrete_path(path), json=garbage)

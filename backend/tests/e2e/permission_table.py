"""권한 매트릭스(계획 4.10)를 한 곳에 둔 표. 새 /api/v1 엔드포인트는 여기에 한 줄을 더해야 한다.

값은 그 엔드포인트를 쓸 수 있는 역할 집합이고, None은 로그인 없이 쓰는 공개 엔드포인트다.
(경로 형식은 OpenAPI의 경로 템플릿과 같다.)
"""

from typing import Final

from app.domain.auth.principal import Role

Route = tuple[str, str]  # (HTTP 메서드 대문자, 경로 템플릿)

EVERYONE: Final = frozenset({Role.ADMIN, Role.SALES, Role.USER})  # 로그인한 모든 역할
WRITERS: Final = frozenset({Role.ADMIN, Role.SALES})
ADMINS: Final = frozenset({Role.ADMIN})

BUSINESS_READS: Final = (
    ("GET", "/api/v1/customers"),
    ("GET", "/api/v1/customers/{customer_id}"),
    ("GET", "/api/v1/partners"),
    ("GET", "/api/v1/partners/{partner_id}"),
    ("GET", "/api/v1/deals"),
    ("GET", "/api/v1/deals/pipeline"),
    ("GET", "/api/v1/deals/by-code/{code}"),
    ("GET", "/api/v1/deals/{deal_id}"),
    ("GET", "/api/v1/deals/{deal_id}/actions"),
    ("GET", "/api/v1/deals/{deal_id}/stage-changes"),
    ("GET", "/api/v1/deal-actions"),
    ("GET", "/api/v1/deal-actions/{action_id}"),
)
BUSINESS_WRITES: Final = (
    ("POST", "/api/v1/customers"),
    ("PUT", "/api/v1/customers/{customer_id}"),
    ("DELETE", "/api/v1/customers/{customer_id}"),
    ("POST", "/api/v1/partners"),
    ("PUT", "/api/v1/partners/{partner_id}"),
    ("DELETE", "/api/v1/partners/{partner_id}"),
    ("POST", "/api/v1/deals"),
    ("PUT", "/api/v1/deals/{deal_id}"),
    ("DELETE", "/api/v1/deals/{deal_id}"),
    ("POST", "/api/v1/deals/{deal_id}/stage"),
    ("POST", "/api/v1/deals/{deal_id}/actions"),
    ("PUT", "/api/v1/deal-actions/{action_id}"),
    ("DELETE", "/api/v1/deal-actions/{action_id}"),
)
ADMIN_ONLY: Final = (
    ("GET", "/api/v1/users"),
    ("POST", "/api/v1/users"),
    ("DELETE", "/api/v1/users/{user_id}"),
    ("GET", "/api/v1/settings/directory"),
    ("PUT", "/api/v1/settings/directory"),
    ("POST", "/api/v1/settings/directory/test"),
)
PUBLIC: Final = (
    ("GET", "/healthz"),
    ("GET", "/readyz"),
    ("GET", "/api/v1/auth/config"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/dev-login"),
    ("POST", "/api/v1/auth/logout"),
    ("PUT", "/api/v1/auth/setup/directory"),
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

PLACEHOLDER = "6f1c1b3a-0000-4000-8000-000000000001"


def concrete_path(template: str) -> str:
    """경로 템플릿의 `{...}`를 존재하지 않는 값으로 채운다(권한 검사는 조회보다 먼저여야 한다)."""
    out = template
    while "{" in out:
        start = out.index("{")
        end = out.index("}", start)
        out = (
            out[:start]
            + ("by-code-x" if out[start + 1 : end] == "code" else PLACEHOLDER)
            + out[end + 1 :]
        )
    return out


def protected_routes() -> list[Route]:
    return [route for route, roles in EXPECTED.items() if roles is not None]

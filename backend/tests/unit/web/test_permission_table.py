"""권한 표(functional 권한 시나리오의 기준 데이터) 자체의 일관성."""

from app.domain.auth.principal import Role
from tests.functional.steps.permissions import ADMIN_ONLY, BUSINESS_WRITES, EXPECTED


def test_the_matrix_lists_each_admin_only_route_for_admins_alone() -> None:
    assert all(EXPECTED[route] == frozenset({Role.ADMIN}) for route in ADMIN_ONLY)
    assert all(Role.USER not in (EXPECTED[route] or ()) for route in BUSINESS_WRITES)

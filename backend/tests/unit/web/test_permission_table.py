"""권한 표(테스트 데이터 `tests/support/permission_table.py`) 자체의 일관성."""

from app.domain.auth.principal import Role
from tests.support.permission_table import ADMIN_ONLY, BUSINESS_WRITES, EXPECTED, protected_routes


def test_the_table_lists_each_admin_only_route_for_admins_alone() -> None:
    """관리자 전용 행은 admin만 허용하고 업무 쓰기 행에는 user가 없다."""
    # when·then: 표의 관리자 전용 행과 업무 쓰기 행을 본다
    #   → 관리자 전용은 admin뿐, 업무 쓰기에는 user가 없다
    assert all(EXPECTED[route] == frozenset({Role.ADMIN}) for route in ADMIN_ONLY)
    assert all(Role.USER not in (EXPECTED[route] or ()) for route in BUSINESS_WRITES)


def test_public_routes_are_the_only_rows_without_roles() -> None:
    """역할 집합이 None인 행(공개 경로)을 뺀 나머지는 모두 보호 경로다."""
    # when: 보호 경로를 모은다
    protected = set(protected_routes())
    # then: 공개 경로는 보호 경로에 없고 나머지는 모두 들어 있다
    public = {route for route, roles in EXPECTED.items() if roles is None}
    assert public.isdisjoint(protected)
    assert public | protected == set(EXPECTED)

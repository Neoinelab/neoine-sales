from typing import TYPE_CHECKING

from app.domain.auth.principal import Role

if TYPE_CHECKING:
    from collections.abc import Iterable


class RoleMapper:
    """IdP 그룹 이름을 앱 역할로 바꾼다. AD 그룹은 대소문자를 구분하지 않고, admin이 우선한다."""

    def __init__(self, admin_groups: Iterable[str], sales_groups: Iterable[str]) -> None:
        self._admin = {g.casefold() for g in admin_groups}
        self._sales = {g.casefold() for g in sales_groups}

    def map(self, groups: frozenset[str]) -> Role | None:
        folded = {g.casefold() for g in groups}
        if folded & self._admin:
            return Role.ADMIN
        if folded & self._sales:
            return Role.SALES
        return None

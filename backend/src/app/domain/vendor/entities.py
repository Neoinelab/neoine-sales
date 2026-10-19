from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.common.entity import AuditedEntity
from app.domain.vendor.errors import (
    DuplicateSolutionNameError,
    SolutionInUseError,
    SolutionNotFoundError,
    VendorInUseError,
)
from app.domain.vendor.values import SolutionId, VendorId

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Solution(AuditedEntity[SolutionId]):
    """Vendor 안의 Solution. 변경은 Vendor 메서드를 통해서만 한다."""

    name: str

    def rename(self, name: str, now: datetime) -> None:
        self.name = name
        self._touch(now)


@dataclass(eq=False, kw_only=True)
class Vendor(AuditedEntity[VendorId]):
    """Aggregate Root. Solution 이름은 Vendor 안에서 대소문자 무시로 고유하다.

    Solution의 추가·변경·삭제는 Vendor의 수정 시각을 바꾸지 않는다.
    """

    name: str
    solutions: list[Solution]

    @classmethod
    def create(cls, *, name: str, now: datetime) -> Self:
        """이름은 이미 정규화된 값이다."""
        return cls(id=VendorId(uuid4()), name=name, solutions=[], created_at=now, updated_at=now)

    def rename(self, name: str, now: datetime) -> None:
        self.name = name
        self._touch(now)

    def has_solution(self, solution_id: SolutionId) -> bool:
        return any(s.id == solution_id for s in self.solutions)

    def solution(self, solution_id: SolutionId) -> Solution:
        found = next((s for s in self.solutions if s.id == solution_id), None)
        if found is None:
            raise SolutionNotFoundError(solution_id)
        return found

    def _ensure_unique_solution(self, name: str, self_id: SolutionId | None = None) -> None:
        lowered = name.lower()
        if any(s.id != self_id and s.name.lower() == lowered for s in self.solutions):
            raise DuplicateSolutionNameError(name)

    def add_solution(self, name: str, now: datetime) -> Solution:
        self._ensure_unique_solution(name)
        solution = Solution(id=SolutionId(uuid4()), name=name, created_at=now, updated_at=now)
        self.solutions.append(solution)
        return solution

    def rename_solution(self, solution_id: SolutionId, name: str, now: datetime) -> Solution:
        solution = self.solution(solution_id)
        self._ensure_unique_solution(name, solution_id)
        solution.rename(name, now)
        return solution

    def remove_solution(self, solution_id: SolutionId, usage: int) -> None:
        """usage는 그 Solution을 쓰는 Deal 수."""
        solution = self.solution(solution_id)
        if usage > 0:
            raise SolutionInUseError(usage)
        self.solutions.remove(solution)

    def ensure_deletable(self, usage: int) -> None:
        """usage는 이 Vendor를 쓰는 Deal 수(소속 Solution을 쓰는 Deal도 포함된다)."""
        if usage > 0:
            raise VendorInUseError(usage)

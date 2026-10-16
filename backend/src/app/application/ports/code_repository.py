from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.code.entities import Code
    from app.domain.code.values import CodeId, CodeKind


class CodeRepository(Protocol):
    """코드 저장소 계약. 이름은 종류 안에서 대소문자 무시로, key는 종류 안에서 고유하다."""

    async def lock_kind(self, kind: CodeKind) -> None:
        """종류 단위 배타 잠금을 얻는다(트랜잭션 범위, commit/rollback에서 풀린다).

        같은 종류의 쓰기 유스케이스(등록·이름 변경·순서 변경·삭제)를 직렬화한다.
        다른 종류는 막지 않고, 같은 트랜잭션이 다시 요청해도 자기 자신을 기다리지 않는다
        (재진입). 행 데이터는 바꾸지 않으며, 읽기는 이 호출 뒤에 해야 최신 값을 본다.
        """
        ...

    async def list(
        self, kind: CodeKind | None = None, *, for_update: bool = False
    ) -> Sequence[Code]:
        """종류 선언 순(Status → Forecast), 종류 안에서는 order, id 순.

        for_update=True면 조회된 행에 행 잠금을 건다. 행 잠금은 새로 추가되는 행(등록)을
        막지 못하므로 종류 단위 직렬화는 lock_kind가 맡는다.
        """
        ...

    async def get(self, code_id: CodeId) -> Code:
        """없으면 CodeNotFoundError."""
        ...

    async def add(self, code: Code) -> None:
        """같은 종류에 같은 이름(대소문자 무시)은 DuplicateCodeNameError.

        같은 종류에 같은 key는 AlreadyExistsError(이름 오류의 하위가 아님).
        """
        ...

    async def update(self, code: Code) -> None:
        """이름·순서(updated_at 포함)만 반영한다. outcome·probability_hint는 쓰지 않는다.

        없으면 CodeNotFoundError, 이름이 다른 코드와 겹치면 DuplicateCodeNameError.
        """
        ...

    async def delete(self, code_id: CodeId) -> None:
        """물리 삭제한다. 없으면 CodeNotFoundError."""
        ...

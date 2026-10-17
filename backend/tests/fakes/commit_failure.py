"""commit만 실패하는 Unit of Work 대역. 커밋 실패 때 디스크 파일이 어떻게 되는지 확인하는 용도.

FakeUnitOfWork를 감싼다. `async with`, repository 속성 읽기는 그대로 전달하고 `commit()`만
RuntimeError를 던진다(변경은 블록을 벗어나며 폐기된다).
"""

from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork

COMMIT_FAILED = "commit failed (test double)"


class CommitFailingUnitOfWork:
    def __init__(self, inner: FakeUnitOfWork) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401 - repository 속성을 그대로 전달
        return getattr(self._inner, name)

    async def __aenter__(self) -> Self:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._inner.__aexit__(*exc)

    async def commit(self) -> None:
        raise RuntimeError(COMMIT_FAILED)

    async def rollback(self) -> None:
        await self._inner.rollback()


def commit_failing_factory(inner: FakeUnitOfWork) -> UnitOfWorkFactory:
    wrapper = CommitFailingUnitOfWork(inner)
    return lambda: wrapper


EXIT_FAILED = "closing the transaction failed (test double)"


class ExitFailingAfterCommitUnitOfWork(CommitFailingUnitOfWork):
    """commit은 성공하고, commit한 블록을 닫을 때(연결 반환 등) 예외를 던지는 대역.

    commit하지 않은 블록은 정상적으로 닫힌다.
    """

    def __init__(self, inner: FakeUnitOfWork) -> None:
        super().__init__(inner)
        self._committed = False

    async def __aenter__(self) -> Self:
        self._committed = False
        return await super().__aenter__()

    async def __aexit__(self, *exc: object) -> None:
        await self._inner.__aexit__(*exc)
        if self._committed:
            raise RuntimeError(EXIT_FAILED)

    async def commit(self) -> None:
        await self._inner.commit()
        self._committed = True


def exit_failing_factory(inner: FakeUnitOfWork) -> UnitOfWorkFactory:
    wrapper = ExitFailingAfterCommitUnitOfWork(inner)
    return lambda: wrapper

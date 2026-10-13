"""통합 동시성 테스트용: 실제 UoW를 감싸 특정 메서드 호출 직전에 멈추는 도우미."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable

    from app.application.ports.unit_of_work import UnitOfWorkFactory


class GatedUow:
    """실제 UoW를 감싸, 진입 후 지정한 메서드의 호출 직전에 신호를 보내고 release까지 멈춘다."""

    def __init__(
        self,
        inner: Any,  # noqa: ANN401
        *,
        attribute: str,
        method: str,
        reached: asyncio.Event,
        release: asyncio.Event,
    ) -> None:
        self._inner = inner
        self._attribute = attribute
        self._method = method
        self._reached = reached
        self._release = release

    async def __aenter__(self) -> Any:  # noqa: ANN401
        await self._inner.__aenter__()
        owner = getattr(self._inner, self._attribute) if self._attribute else self._inner
        original: Callable[..., Awaitable[Any]] = getattr(owner, self._method)

        async def gated(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
            self._reached.set()
            await self._release.wait()
            return await original(*args, **kwargs)

        setattr(owner, self._method, gated)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._inner.__aexit__(*exc)

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        return getattr(self._inner, name)


def gated(
    factory: UnitOfWorkFactory,
    *,
    attribute: str,
    method: str,
    reached: asyncio.Event,
    release: asyncio.Event,
) -> UnitOfWorkFactory:
    def build() -> Any:  # noqa: ANN401
        return GatedUow(
            factory(), attribute=attribute, method=method, reached=reached, release=release
        )

    return build

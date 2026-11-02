"""앱 팩토리: 기본 조립(Container), 지연 생성되는 `app.main:app`, 스케줄러 시작·종료(AC16~21)."""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app import main
from app.container import Container
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import make_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


async def test_default_assembly_builds_a_container_and_disposes_it_on_shutdown() -> None:
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL))

    assert isinstance(app.state.use_cases, Container)
    async with app.router.lifespan_context(app):
        pass  # 종료 시 엔진이 정리돼도 예외가 없어야 한다


def test_module_level_app_is_created_lazily_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    main._default_app.cache_clear()
    monkeypatch.setattr(main, "get_settings", lambda: make_settings(UNUSED_DATABASE_URL))

    assert main.app is main.app  # 같은 인스턴스를 재사용
    main._default_app.cache_clear()


def test_unknown_module_attribute_is_an_attribute_error() -> None:
    with pytest.raises(AttributeError):
        main.nothing  # noqa: B018


class _Recorder:
    """Container.forecast_snapshot_scheduler / dispose를 대신해 시작·취소·정리 순서를 기록한다."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.events: list[str] = []
        events = self.events

        class _Scheduler:
            async def run_forever(self) -> None:
                events.append("started")
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    events.append("cancelled")
                    raise

        async def dispose(_self: Container) -> None:
            events.append("disposed")

        monkeypatch.setattr(Container, "forecast_snapshot_scheduler", lambda _self: _Scheduler())
        monkeypatch.setattr(Container, "dispose", dispose)


async def _run_lifespan(app: FastAPI) -> None:
    async with app.router.lifespan_context(app):
        for _ in range(3):  # 만들어진 태스크가 시작할 기회를 준다
            await asyncio.sleep(0)


async def test_scheduler_is_not_started_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder(monkeypatch)
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL, scheduler_enabled=False))

    await _run_lifespan(app)

    assert recorder.events == ["disposed"]


async def test_scheduler_is_started_and_cancelled_before_dispose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(monkeypatch)
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL, scheduler_enabled=True))

    await _run_lifespan(app)

    assert recorder.events == ["started", "cancelled", "disposed"]


async def test_scheduler_is_not_started_when_use_cases_are_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(monkeypatch)
    app = main.create_app(
        settings=make_settings(UNUSED_DATABASE_URL, scheduler_enabled=True),
        use_cases=FakeUseCases(),
    )

    await _run_lifespan(app)

    assert recorder.events == []


async def test_default_local_settings_do_not_start_the_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(monkeypatch)
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL))

    await _run_lifespan(app)

    assert recorder.events == ["disposed"]

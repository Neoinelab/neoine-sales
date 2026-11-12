"""앱 팩토리: 기본 조립(Container), 지연 생성되는 `app.main:app`, 스케줄러 시작·종료."""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app import main
from app.container import Container
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import make_settings

if TYPE_CHECKING:
    from fastapi import FastAPI

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


async def test_default_assembly_builds_a_container_and_disposes_it_on_shutdown() -> None:
    """기본 조립은 Container를 만들고 종료 때 정리한다."""
    # when: 기본 설정으로 앱을 만든다
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL))

    # then: 유스케이스 제공자가 Container다
    assert isinstance(app.state.use_cases, Container)
    # when: lifespan을 시작하고 종료한다 (정리 중 예외가 없어야 한다)
    async with app.router.lifespan_context(app):
        pass  # 종료 시 엔진이 정리돼도 예외가 없어야 한다


def test_module_level_app_is_created_lazily_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """모듈 수준 app은 설정으로 지연 생성된다."""
    # given: 캐시를 비우고 설정을 대체한 상태
    main._default_app.cache_clear()
    monkeypatch.setattr(main, "get_settings", lambda: make_settings(UNUSED_DATABASE_URL))

    # when·then: app을 두 번 읽으면 같은 인스턴스다
    assert main.app is main.app  # 같은 인스턴스를 재사용
    main._default_app.cache_clear()


def test_unknown_module_attribute_is_an_attribute_error() -> None:
    """없는 모듈 속성은 AttributeError다."""
    # when·then: 없는 속성을 읽으면 AttributeError다
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
    """스케줄러가 꺼져 있으면 기동하지 않고 정리만 한다

    테스트 코드: FC-045
    """
    # given: 스케줄러 사용 안 함 설정과 기록용 대역
    recorder = _Recorder(monkeypatch)
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL, scheduler_enabled=False))

    # when: 앱 lifespan을 시작·종료한다
    await _run_lifespan(app)

    # then: 정리만 기록된다
    assert recorder.events == ["disposed"]


async def test_scheduler_is_started_and_cancelled_before_dispose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """스케줄러는 기동하고 종료 때 취소한 뒤 정리한다

    테스트 코드: FC-045
    """
    # given: 스케줄러 사용 설정과 기록용 대역
    recorder = _Recorder(monkeypatch)
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL, scheduler_enabled=True))

    # when: 앱 lifespan을 시작·종료한다
    await _run_lifespan(app)

    # then: 시작, 취소, 정리 순서다
    assert recorder.events == ["started", "cancelled", "disposed"]


async def test_scheduler_is_not_started_when_use_cases_are_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """유스케이스를 주입한 앱은 스케줄러를 기동하지 않는다

    테스트 코드: FC-045
    """
    # given: 스케줄러 사용 설정이지만 유스케이스를 주입한 앱
    recorder = _Recorder(monkeypatch)
    app = main.create_app(
        settings=make_settings(UNUSED_DATABASE_URL, scheduler_enabled=True),
        use_cases=FakeUseCases(),
    )

    # when: 앱 lifespan을 시작·종료한다
    await _run_lifespan(app)

    # then: 아무것도 기록되지 않는다
    assert recorder.events == []


async def test_default_local_settings_do_not_start_the_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """local 기본 설정은 스케줄러를 기동하지 않는다

    테스트 코드: FC-045
    """
    # given: local 기본 설정과 기록용 대역
    recorder = _Recorder(monkeypatch)
    app = main.create_app(settings=make_settings(UNUSED_DATABASE_URL))

    # when: 앱 lifespan을 시작·종료한다
    await _run_lifespan(app)

    # then: 정리만 기록된다
    assert recorder.events == ["disposed"]

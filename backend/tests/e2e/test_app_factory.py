"""앱 팩토리: 기본 조립(Container)과 지연 생성되는 `app.main:app`."""

import pytest

from app import main
from app.container import Container
from tests.e2e.conftest import make_settings


async def test_default_assembly_builds_a_container_and_disposes_it_on_shutdown() -> None:
    app = main.create_app(settings=make_settings())

    assert isinstance(app.state.use_cases, Container)
    async with app.router.lifespan_context(app):
        pass  # 종료 시 엔진이 정리돼도 예외가 없어야 한다


def test_module_level_app_is_created_lazily_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    main._default_app.cache_clear()
    monkeypatch.setattr(main, "get_settings", make_settings)

    assert main.app is main.app  # 같은 인스턴스를 재사용
    main._default_app.cache_clear()


def test_unknown_module_attribute_is_an_attribute_error() -> None:
    with pytest.raises(AttributeError):
        main.nothing  # noqa: B018

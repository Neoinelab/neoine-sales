"""재발 방지: 응답 스키마에 맨 `datetime` 필드가 남지 않는다(시간 기준 서버 통일 AC2).

`app.web.schemas`의 모든 pydantic 모델에서 datetime 필드는 `ServerDateTime`이어야 한다.
그래야 모든 응답 시각이 서버 OS 로컬 오프셋으로 나간다.
"""

import importlib
import pkgutil
from datetime import datetime
from types import NoneType, UnionType
from typing import Annotated, Union, get_args, get_origin

import pytest
from app.web.schemas.server_datetime import ServerDateTime
from pydantic import BaseModel

import app.web.schemas as schemas_package

SERVER_METADATA = get_args(ServerDateTime)[1:]


def _models() -> list[type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for info in pkgutil.iter_modules(schemas_package.__path__, "app.web.schemas."):
        module = importlib.import_module(info.name)
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and issubclass(value, BaseModel)
                and value.__module__.startswith("app.web.schemas")
            ):
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return list(found.values())


def _bare_datetimes(annotation: object, metadata: tuple[object, ...]) -> int:
    """ServerDateTime이 아닌 datetime 사용 개수."""
    if annotation is datetime:
        return 0 if all(item in metadata for item in SERVER_METADATA) else 1
    if get_origin(annotation) is Annotated:
        base, *extra = get_args(annotation)
        return _bare_datetimes(base, (*metadata, *extra))
    origin = get_origin(annotation)
    if origin in (Union, UnionType, list, tuple, dict):
        return sum(
            _bare_datetimes(arg, metadata) for arg in get_args(annotation) if arg is not NoneType
        )
    return 0


def test_server_datetime_is_annotated_datetime() -> None:
    assert get_origin(ServerDateTime) is Annotated
    assert get_args(ServerDateTime)[0] is datetime
    assert SERVER_METADATA, "직렬화 규칙(메타데이터)이 있어야 한다"


def test_the_guard_detects_a_bare_datetime() -> None:
    class Bare(BaseModel):
        at: datetime

    field = Bare.model_fields["at"]

    assert _bare_datetimes(field.annotation, tuple(field.metadata)) == 1


def test_the_guard_accepts_server_datetime_and_optional() -> None:
    class Good(BaseModel):
        at: ServerDateTime
        maybe: ServerDateTime | None = None

    counts = [
        _bare_datetimes(field.annotation, tuple(field.metadata))
        for field in Good.model_fields.values()
    ]

    assert counts == [0, 0]


def test_response_models_are_discovered() -> None:
    names = {model.__name__ for model in _models()}

    assert {"DealRowResponse", "DealDetailResponse", "UserResponse"} <= names


@pytest.mark.parametrize("model", _models(), ids=lambda model: model.__name__)
def test_no_bare_datetime_field_in_web_schemas(model: type[BaseModel]) -> None:
    bare = [
        name
        for name, field in model.model_fields.items()
        if _bare_datetimes(field.annotation, tuple(field.metadata)) > 0
    ]

    assert bare == [], f"{model.__name__}: ServerDateTime을 써야 한다 {bare}"

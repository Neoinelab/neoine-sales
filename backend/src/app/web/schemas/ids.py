"""API id 타입. id는 JSON 정수이며 1 이상 2^53-1 이하(JavaScript 안전 정수 상한)다."""

from typing import Annotated

from fastapi import Path
from pydantic import Field, StrictInt

from app.domain.common.ids import MAX_ID

PathId = Annotated[int, Path(ge=1, le=MAX_ID)]
"""경로 매개변수 id. 문서에 minimum·maximum이 나간다."""

BodyId = Annotated[StrictInt, Field(ge=1, le=MAX_ID)]
"""본문 id. 문자열·불리언·실수는 거절한다."""

QueryId = Annotated[int, Field(ge=1, le=MAX_ID)]
"""쿼리 id. 쿼리는 문자열로 오므로 "7"을 7로 받는다."""

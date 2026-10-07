from typing import Annotated

from fastapi import Depends, Query, Request

from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.web.use_case_provider import UseCaseProvider


def get_provider(request: Request) -> UseCaseProvider:
    provider: UseCaseProvider = request.app.state.use_cases
    return provider


Provider = Annotated[UseCaseProvider, Depends(get_provider)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]

__all__ = ["DEFAULT_LIMIT", "Limit", "Offset", "Provider", "get_provider"]

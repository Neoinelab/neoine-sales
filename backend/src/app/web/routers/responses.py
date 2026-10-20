from typing import Any

from app.web.schemas.common import Problem

PROBLEM = {"model": Problem, "description": "problem+json"}
READ_ERRORS: dict[int | str, dict[str, Any]] = {404: PROBLEM, 422: PROBLEM}
WRITE_ERRORS: dict[int | str, dict[str, Any]] = {404: PROBLEM, 409: PROBLEM, 422: PROBLEM}
STATUS_ERRORS: dict[int | str, dict[str, Any]] = {403: PROBLEM, **WRITE_ERRORS}

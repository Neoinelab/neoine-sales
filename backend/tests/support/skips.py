"""통합 테스트를 건너뛸지 실패시킬지 정한다. CI는 REQUIRE_INTEGRATION_DB=1로 skip을 막는다."""

import os
from typing import NoReturn

import pytest


def skip_or_fail(reason: str) -> NoReturn:
    if os.environ.get("REQUIRE_INTEGRATION_DB") == "1":
        pytest.fail(reason, pytrace=False)
    pytest.skip(reason)

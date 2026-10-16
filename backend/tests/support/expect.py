"""예외 문구를 정확히 단언하는 도우미(`match=`는 정규식이라 마침표 등을 이스케이프해야 한다)."""

import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from contextlib import AbstractContextManager


def raises_with[ErrorT: BaseException](
    error_type: type[ErrorT], message: str
) -> AbstractContextManager[pytest.ExceptionInfo[ErrorT]]:
    """`error_type`이 올라오고 문구(str(error))가 `message`와 정확히 같다."""
    return pytest.raises(error_type, match=rf"\A{re.escape(message)}\Z")

"""테스트용 정수 id 규칙.

DB 테스트가 직접 넣는 id가 시퀀스(1부터)와 충돌하지 않도록 10억대 번호를 쓴다. 앱이 `IdAllocator`로
받는 id는 1부터이고, 테스트가 만드는 id(`new_id`)는 1_000_000_001부터다. HTTP 테스트에서
"형식은 맞지만 없는 id"는 `MISSING_ID`를 쓴다.
"""

import itertools
from typing import Final

MAX_ID: Final = 2**53 - 1  # API가 받는 id 상한(JSON 정수가 정확히 표현되는 최댓값)
MISSING_ID: Final = 999_999_999_999  # 어느 테이블에도 없는 id(유효 범위 안)
FIRST_TEST_ID: Final = 1_000_000_001

_counter = itertools.count(FIRST_TEST_ID)


def new_id() -> int:
    """프로세스 전역에서 증가하는 새 id(1_000_000_001부터). 호출마다 다른 값이다."""
    return next(_counter)

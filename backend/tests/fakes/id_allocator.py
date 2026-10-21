"""`IdAllocator` Port의 Fake: 종류별 카운터이고 1부터 시작한다.

실제 DB 시퀀스처럼 트랜잭션 밖에 있다. `FakeUnitOfWork`의 롤백 스냅숏에 넣지 않으므로 롤백해도
번호는 되돌아가지 않는다(번호가 비는 것은 허용). 종류(`IdKind`)는 키로만 쓴다.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Hashable


class FakeIdAllocator:
    def __init__(self) -> None:
        self._last: defaultdict[Hashable, int] = defaultdict(int)

    async def next_id(self, kind: Hashable) -> int:
        self._last[kind] += 1
        return self._last[kind]

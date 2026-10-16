"""functional 시나리오의 시계: 시작 시점의 실제 시각에 고정되고 테스트가 전진시킬 때만 움직인다.

`Container(clock=)`로 주입되어 앱이 기록하는 모든 시각(등록·로그인·퇴사·설정 저장)이 이 시계의
값이 된다. 그래서 Then이 응답의 시각을 "최근"이 아니라 **정확한 값**으로 비교할 수 있다.
실제 시각에서 시작하는 이유는 SQL의 `now()`를 쓰는 step(예: 만료 세션 준비)과
어긋나지 않게 하려는 것이다.

Then step은 `api`를 받지 않는 경우가 있어(`then_is_recent(timestamp)`), 현재 시나리오의 시계를
모듈 변수로 둔다. `Api`가 만들어질 때 `activate`로 등록한다(테스트는 한 번에 하나만 돈다).
"""

from datetime import UTC, datetime

from tests.fakes.unit_of_work import FixedClock

_active: FixedClock | None = None


def new_clock() -> FixedClock:
    """지금 시각에서 시작하는 시계."""
    return FixedClock(datetime.now(UTC))


def activate(clock: FixedClock) -> None:
    global _active  # noqa: PLW0603 - Then step이 api 없이 현재 시나리오의 시계를 찾는다
    _active = clock


def active_clock() -> FixedClock:
    assert _active is not None, "functional 시계가 없다(api fixture 밖에서 호출했다)"
    return _active

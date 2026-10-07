from datetime import UTC, datetime


class SystemClock:
    """Clock Port의 실제 구현: UTC 현재 시각."""

    def now(self) -> datetime:
        return datetime.now(UTC)

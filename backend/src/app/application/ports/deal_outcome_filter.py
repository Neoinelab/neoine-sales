from enum import StrEnum

from app.domain.code.values import ForecastOutcome


class ForecastOutcomeFilter(StrEnum):
    """Forecast 코드 outcome 필터. not_lost는 open과 won."""

    OPEN = "open"
    WON = "won"
    LOST = "lost"
    NOT_LOST = "not_lost"

    def outcomes(self) -> tuple[ForecastOutcome, ...]:
        if self is ForecastOutcomeFilter.NOT_LOST:
            return (ForecastOutcome.OPEN, ForecastOutcome.WON)
        return (ForecastOutcome(self.value),)

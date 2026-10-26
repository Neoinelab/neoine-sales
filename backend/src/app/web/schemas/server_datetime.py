"""응답 시각 타입: 같은 순간을 서버 OS 로컬 오프셋으로 직렬화한다(시간 기준 서버 통일).

순간은 바뀌지 않고 openapi 스키마(string/date-time)도 그대로다.
"""

from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from app.domain.common.business_date import business_time

ServerDateTime = Annotated[
    datetime,
    PlainSerializer(business_time, return_type=datetime, when_used="always"),
]

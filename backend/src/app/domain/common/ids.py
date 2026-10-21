"""대리 키(id) 공통 정의. id는 1 이상 MAX_ID 이하의 정수다."""

from typing import Final

# JSON 숫자(IEEE 754 double)로 손실 없이 표현되는 가장 큰 정수. BIGINT 시퀀스 상한이기도 하다.
MAX_ID: Final = 2**53 - 1

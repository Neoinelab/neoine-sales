"""테스트용 Fernet 키(더미). 운영 키가 아니며 어느 환경에서도 쓰이지 않는다.

Fernet 키는 URL-safe base64로 인코딩한 32바이트(44자)다. 키 형식 검증을 `cryptography`에 묶지 않도록
base64로만 만든다.
"""

import base64
from typing import Final

TEST_FERNET_KEY: Final = base64.urlsafe_b64encode(b"t" * 32).decode()
OTHER_FERNET_KEY: Final = base64.urlsafe_b64encode(b"o" * 32).decode()

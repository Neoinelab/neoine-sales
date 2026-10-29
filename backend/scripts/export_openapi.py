"""OpenAPI 스키마를 backend/openapi.json으로 내보낸다. API를 바꾼 뒤 실행해 커밋한다.

DB에 접속하지 않으며 실제 환경 파일도 읽지 않는다(Fake 유스케이스·더미 설정 사용).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from app.config.profiles import LocalSettings  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.fakes.use_cases import FakeUseCases  # noqa: E402
from tests.support.crypto_keys import TEST_FERNET_KEY  # noqa: E402

TARGET = ROOT / "openapi.json"


def main() -> None:
    settings = LocalSettings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pw@localhost:5432/none",
        jwt_secret="x" * 40,
        settings_encryption_key=TEST_FERNET_KEY,
        enable_docs=True,
    )
    schema = create_app(settings=settings, use_cases=FakeUseCases()).openapi()
    TARGET.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()

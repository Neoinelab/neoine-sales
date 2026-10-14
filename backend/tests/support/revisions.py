"""마이그레이션 리비전 상수. 과거 리비전 검증 테스트는 head 대신 이 상수로 target을 고정한다.

head는 계속 앞으로 간다. 과거 리비전의 스키마(예: deals.owner 문자열 컬럼)를 전제하는 테스트가
새 리비전 때문에 깨지거나 새 리비전의 변환에 걸리지 않도록 target을 고정해 보호한다.
"""

from typing import Final

STAGE_REVISION: Final = "2a49cc41cdff"  # deal_stage + deal_stage_changes
OWNER_REVISION: Final = "39d531ff2643"  # deals.owner_user_id(등록자 subject, 문자열)
AUTH_REVISION: Final = "dd7f21f7190e"  # users·login_failures·directory_settings
HISTORY_REVISION: Final = "e3a9c41b7d52"  # 활동 이력 필드
DROP_DELETED_AT_REVISION: Final = (
    "f4b8d2a6c9e1"  # 모든 테이블 deleted_at 제거(= 사용자 FK 이전 head)
)
LEGACY_HEAD: Final = DROP_DELETED_AT_REVISION

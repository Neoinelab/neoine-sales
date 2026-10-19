"""업무 테이블을 비우는 도우미(테스트 사이 격리용).

스키마 마이그레이션 테스트 중에는 `contacts`가 없을 수 있어, 지금 DB에 있는 테이블만 이름에 넣는다.
이름은 모두 이 모듈의 상수다.
`users`를 CASCADE로 비우면 users를 참조하는 테이블(deals, 활동, Label 등)까지 비워지지만,
연락처 테이블은 Deal이 참조하는 쪽이라 따로 비워야 한다.
"""

from typing import TYPE_CHECKING, Final

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

ALWAYS: Final = (
    "auth_sessions",
    "users",
    "login_failures",
    "directory_settings",
    "deal_actions",
    "deals",
)
CONTACT_TABLES: Final = ("contacts",)
# P1 새 Deal 모델의 소속 테이블. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다.
DEAL_TABLES: Final = ("deal_history", "deal_partners", "deal_bant_labels")
# P2b 파일 테이블. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다(users CASCADE로도 비워진다).
FILE_TABLES: Final = ("deal_attachments", "storage_settings")
# P3 경고 기준. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다(users CASCADE로도 비워진다).
ALERT_TABLES: Final = ("alert_settings",)
# Vendor·Solution 관리. 과거 리비전 DB에는 없을 수 있어 있는 것만 비운다(deals가 참조).
VENDOR_TABLES: Final = ("solutions", "vendors")


async def existing_tables(connection: AsyncConnection) -> set[str]:
    rows = await connection.execute(
        text("select tablename from pg_tables where schemaname = 'public'")
    )
    return {str(row[0]) for row in rows}


async def truncate_business_tables(connection: AsyncConnection) -> None:
    """사용자·Deal·활동·연락처 테이블을 비운다.

    `bant_labels.created_by_user_id`가 users를 참조해 CASCADE가 Label까지 비우므로, 마이그레이션이
    심은 기본 Label(created_by_user_id 없음)은 비운 뒤 되살린다. 이 DB는 세션 전체가 공유해서
    기본 Label이 사라지면 뒤에 도는 스키마 테스트가 시드를 못 찾는다.
    """
    present = await existing_tables(connection)
    optional = (*DEAL_TABLES, *FILE_TABLES, *ALERT_TABLES, *VENDOR_TABLES, *CONTACT_TABLES)
    names = [*ALWAYS, *(name for name in optional if name in present)]
    keep_labels = "bant_labels" in present
    if keep_labels:
        await connection.execute(
            text(
                "create temp table _seed_bant_labels on commit drop as"
                " select * from bant_labels where created_by_user_id is null"
            )
        )
    await connection.execute(text(f"truncate {', '.join(names)} cascade"))
    if keep_labels:
        await connection.execute(text("insert into bant_labels select * from _seed_bant_labels"))

"""저장 리포트 유스케이스 테스트 공용 도우미: 사용자 id, 요청자, 저장소 시드와 읽기.

준비용 commit은 커밋 횟수 단언에 섞이지 않도록 0으로 되돌린다. 도메인·애플리케이션 모듈은 사용
시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이 막히지 않게).
"""

from typing import TYPE_CHECKING, Any

from app.domain.auth.principal import Role
from tests.support.report_defs import col, raw
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.saved_report.entities import Report
    from app.domain.user.value_objects import UserId
    from tests.fakes.unit_of_work import FakeUnitOfWork

ALICE = uid("alice-rpt")
BOB = uid("bob-rpt")
ROOT = uid("root-rpt")
VALID_DEFINITION = raw([col("deal.code")])
INVALID_DEFINITION = raw([col("deal.password")])  # 카탈로그에 없는 필드(unknown-field)


def viewer(user_id: UserId, role: Role = Role.SALES) -> Any:  # noqa: ANN401 - ReportViewer
    from app.application.report.saved_inputs import ReportViewer  # noqa: PLC0415

    return ReportViewer(user_id=user_id, role=role)


def content_input(
    name: str = "분기 Pipeline",
    *,
    description: str = "",
    visibility: str = "public",
    definition: Any = VALID_DEFINITION,  # noqa: ANN401 - RawReportDefinition
) -> Any:  # noqa: ANN401 - ReportContentInput
    from app.application.report.saved_inputs import ReportContentInput  # noqa: PLC0415

    return ReportContentInput(
        name=name, description=description, visibility=visibility, definition=definition
    )


def meta_input(name: str = "복사본", *, description: str = "", visibility: str = "public") -> Any:  # noqa: ANN401 - ReportMetaInput
    from app.application.report.saved_inputs import ReportMetaInput  # noqa: PLC0415

    return ReportMetaInput(name=name, description=description, visibility=visibility)


async def seed(uow: FakeUnitOfWork, *reports: Report) -> None:
    """리포트를 저장소에 직접 넣는다(유스케이스를 거치지 않는다)."""
    async with uow:
        for report in reports:
            await uow.saved_reports.add(report)
        await uow.commit()
    uow.commits = 0


async def stored(uow: FakeUnitOfWork) -> list[Report]:
    """저장된 리포트 전부(최신 수정 순)."""
    from app.domain.saved_report.values import ReportListScope  # noqa: PLC0415

    return list(await uow.saved_reports.list(ReportListScope(viewer_id=ALICE, see_all=True)))

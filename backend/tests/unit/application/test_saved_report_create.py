"""CreateReport: 저장 리포트 만들기의 검증 순서, 서버가 만든 SQL, 이름 중복, 모든 역할."""

from typing import TYPE_CHECKING

import pytest

from app.application.report.create_report import CreateReport
from app.application.report.delete_report import DeleteReport
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.errors import DuplicateReportNameError
from app.domain.saved_report.values import ReportVisibility
from tests.factories import NOW
from tests.factories_report import make_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.support.chart_defs import chart_definition, raw_chart
from tests.support.layout_defs import raw_layout
from tests.support.report_defs import col, cond, raw
from tests.unit.application.saved_report_env import (
    ALICE,
    BOB,
    INVALID_DEFINITION,
    content_input,
    seed,
    stored,
    viewer,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


@pytest.fixture
def create(uow_factory: UnitOfWorkFactory, clock: FixedClock) -> CreateReport:
    return CreateReport(uow_factory, clock)


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_any_role_creates_a_report_with_server_rendered_sql(
    create: CreateReport, uow: FakeUnitOfWork, role: Role
) -> None:
    """모든 역할이 리포트를 만들고 만든 사람·최종 수정자는 요청자, revision 1이다.

    테스트 코드: RS-001
    """
    # given: Vendor 합계 정의
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    # when: 역할별 요청자가 비공개 리포트를 만든다
    report = await create.execute(
        content_input(
            "Vendor 합계", description="설명", visibility="private", definition=definition
        ),
        viewer(ALICE, role),
    )
    # then: 요청자가 만든 사람이자 최종 수정자이고 revision 1, 생성·수정 시각이 같다
    assert report.owner_user_id == ALICE
    assert report.updated_by_user_id == ALICE
    assert report.revision == 1
    assert (report.name, report.description) == ("Vendor 합계", "설명")
    assert report.visibility is ReportVisibility.PRIVATE
    assert (report.created_at, report.updated_at) == (NOW, NOW)
    assert [r.id for r in await stored(uow)] == [report.id]
    assert uow.commits == 1


async def test_two_creations_get_different_ids(create: CreateReport, uow: FakeUnitOfWork) -> None:
    """같은 요청자가 두 리포트를 만들면 id가 서로 다르고 먼저 만든 리포트는 그대로다.

    테스트 코드: RS-001
    """
    # given: 이미 만든 리포트 하나
    first = await create.execute(content_input("하나"), viewer(ALICE))
    # when: 다른 이름으로 하나 더 만든다
    second = await create.execute(content_input("둘"), viewer(ALICE))
    # then: id가 다르고 먼저 만든 리포트의 이름·revision은 그대로다
    assert first.id != second.id
    saved = {r.id: r for r in await stored(uow)}
    assert (saved[first.id].name, saved[first.id].revision) == ("하나", 1)


async def test_create_stores_sql_rendered_by_the_server_from_the_definition(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """저장하면 서버가 정의로 만든 SQL과 조건이 함께 저장된다.

    테스트 코드: RS-002
    """
    # given: 조건이 하나 있는 정의
    definition = raw(
        [col("deal.code")], [cond("deal.expected_close", "relative", {"period": "this_year"})]
    )
    # when: 리포트를 만든다
    report = await create.execute(content_input(definition=definition), viewer(ALICE))
    # then: 저장된 SQL은 서버가 만든 SQL, 정의의 컬럼·조건은 보낸 그대로, 실행은 하지 않는다
    (saved,) = await stored(uow)
    assert report.generated_sql == saved.generated_sql == RENDERED_SQL
    assert saved.definition == definition
    (rendered,) = uow.reports.rendered
    assert rendered.definition.columns[0].field.key == "deal.code"
    assert uow.reports.calls == []


async def test_create_normalizes_name_and_description(create: CreateReport) -> None:
    """이름·설명은 앞뒤 공백을 지워 저장한다.

    테스트 코드: RS-004
    """
    # when: 앞뒤에 공백이 있는 이름·설명으로 만든다
    report = await create.execute(
        content_input("  분기 Pipeline  ", description="  메모 "), viewer(ALICE)
    )
    # then: 공백을 지운 값으로 저장된다
    assert (report.name, report.description) == ("분기 Pipeline", "메모")


async def test_create_accepts_name_of_100_chars_and_description_of_1000_chars(
    create: CreateReport,
) -> None:
    """이름 100자와 설명 1,000자는 받고, 공백을 지운 뒤 100자인 이름도 받는다.

    테스트 코드: RS-004
    """
    # when: 경계 길이의 이름·설명으로 만든다
    exact = await create.execute(content_input("a" * 100, description="b" * 1000), viewer(ALICE))
    padded = await create.execute(content_input(" " + "c" * 100 + " "), viewer(ALICE))
    # then: 모두 저장된다
    assert (len(exact.name), len(exact.description)) == (100, 1000)
    assert padded.name == "c" * 100


@pytest.mark.parametrize(
    ("name", "description", "visibility", "message"),
    [
        ("  ", "", "public", "리포트 이름을 입력하세요."),
        ("a" * 101, "", "public", "리포트 이름은 100자 이내로 입력하세요."),
        ("ok", "a" * 1001, "public", "설명은 1,000자 이내로 입력하세요."),
        ("a\x00b", "", "public", "리포트 이름에는 NUL 문자를 쓸 수 없습니다"),
        ("ok", "a\x00b", "public", "설명에는 NUL 문자를 쓸 수 없습니다"),
        ("ok", "", "all", "공개 범위는 public 또는 private입니다."),
        ("ok", "", "Public", "공개 범위는 public 또는 private입니다."),
    ],
    ids=[
        "blank-name",
        "long-name",
        "long-description",
        "nul-name",
        "nul-description",
        "unknown-visibility",
        "visibility-case",
    ],
)
async def test_invalid_meta_is_rejected_with_message_and_not_saved(  # noqa: PLR0913, PLR0917
    create: CreateReport,
    uow: FakeUnitOfWork,
    name: str,
    description: str,
    visibility: str,
    message: str,
) -> None:
    """빈 이름·긴 이름·긴 설명·NUL·알 수 없는 공개 범위는 문구와 함께 거절되고 저장되지 않는다.

    테스트 코드: RS-005
    """
    # when·then: 잘못된 메타로 만들면 해당 문구의 값 오류다
    with pytest.raises(InvalidValueError) as caught:
        await create.execute(
            content_input(name, description=description, visibility=visibility), viewer(ALICE)
        )
    assert not isinstance(caught.value, ReportDefinitionError)
    assert str(caught.value) == message
    # then: 아무것도 저장되지 않는다
    assert await stored(uow) == []
    assert uow.commits == 0


async def test_invalid_definition_is_rejected_with_location_and_code_and_not_saved(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """규칙을 어긴 정의는 위치와 code가 있는 정의 오류로 거절되고 저장되지 않는다.

    테스트 코드: RS-006
    """
    # when·then: 카탈로그에 없는 컬럼 하나뿐인 정의로 만들면 정의 오류다
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(content_input(definition=INVALID_DEFINITION), viewer(ALICE))
    assert [(tuple(i.location), i.code) for i in caught.value.issues] == [
        (("columns", 0, "field"), "unknown-field")
    ]
    # then: 아무것도 저장되지 않는다
    assert await stored(uow) == []
    assert uow.commits == 0


async def test_meta_error_comes_before_chart_error(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """메타 오류가 있으면 차트 위반이 있어도 이름 오류만 알린다.

    테스트 코드: RS-007
    """
    # when·then: 빈 이름과 틀린 차트를 함께 보내면 이름 문구의 값 오류다
    with pytest.raises(InvalidValueError) as caught:
        await create.execute(
            content_input("", definition=chart_definition(2, 3), chart=raw_chart("bar", 9, [0])),
            viewer(ALICE),
        )
    assert not isinstance(caught.value, ReportDefinitionError)
    assert str(caught.value) == "리포트 이름을 입력하세요."
    # then: 저장되지 않는다
    assert await stored(uow) == []


async def test_definition_error_skips_chart_and_layout_checks(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """정의 위반이 있으면 차트·배치는 검사하지 않는다.

    테스트 코드: RS-007
    """
    # when·then: 틀린 정의 + 틀린 차트 + 틀린 배치로 만들면 정의 위치 위반만 있다
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(
            content_input(
                definition=INVALID_DEFINITION,
                chart=raw_chart("bar", 9, [0]),
                layout=raw_layout(view="x"),
            ),
            viewer(ALICE),
        )
    locations = [tuple(i.location) for i in caught.value.issues]
    assert locations
    assert all(loc[0] not in {"chart", "layout"} for loc in locations)
    # then: 저장되지 않는다
    assert await stored(uow) == []


async def test_chart_error_skips_layout_check(create: CreateReport, uow: FakeUnitOfWork) -> None:
    """맞는 정의에 차트 위반이 있으면 차트 위치 위반만 알리고 배치는 검사하지 않는다.

    테스트 코드: RS-007
    """
    # when·then: 맞는 정의 + 틀린 차트 + 틀린 배치로 만들면 chart 위치 위반만 있다
    with pytest.raises(ReportDefinitionError) as caught:
        await create.execute(
            content_input(
                definition=chart_definition(2, 3),
                chart=raw_chart("bar", 9, [0]),
                layout=raw_layout(view="x"),
            ),
            viewer(ALICE),
        )
    locations = [tuple(i.location) for i in caught.value.issues]
    assert locations
    assert all(loc[0] == "chart" for loc in locations)
    # then: 저장되지 않는다
    assert await stored(uow) == []


async def test_same_name_ignoring_case_conflicts_for_the_same_owner(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """자기 리포트와 대소문자만 다른 이름으로 만들면 409(이름 중복)이다.

    테스트 코드: RS-008
    """
    # given: ALICE의 "Sales Report"
    await create.execute(content_input("Sales Report"), viewer(ALICE))
    # when·then: 대소문자만 다른 이름으로 만들면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError) as caught:
        await create.execute(content_input("sales report"), viewer(ALICE))
    assert str(caught.value) == "같은 이름의 리포트가 이미 있습니다."
    # then: 리포트는 하나 그대로다
    assert len(await stored(uow)) == 1


async def test_same_name_ignoring_case_conflicts_for_another_owner(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """남의 공개 리포트와 대소문자만 다른 이름으로 만들면 409(이름 중복)이다.

    테스트 코드: RS-008
    """
    # given: ALICE의 공개 "Sales Report"
    await create.execute(content_input("Sales Report"), viewer(ALICE))
    # when·then: BOB이 "SALES REPORT"로 만들면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError):
        await create.execute(content_input("SALES REPORT"), viewer(BOB))
    # then: 리포트는 하나 그대로다
    assert len(await stored(uow)) == 1


async def test_a_name_used_by_someone_else_privately_conflicts(
    create: CreateReport, uow: FakeUnitOfWork
) -> None:
    """남의 비공개 리포트와 같은 이름으로 만들면 409이고 목록에는 그 이름이 보이지 않는다.

    테스트 코드: RS-008
    """
    # given: ALICE의 비공개 "공통 이름"
    await seed(uow, make_report("공통 이름", owner=ALICE, visibility="private"))
    # when·then: BOB이 같은 이름으로 만들면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError):
        await create.execute(content_input("공통 이름"), viewer(BOB))
    # then: 리포트는 하나 그대로다
    assert len(await stored(uow)) == 1


async def test_name_is_compared_after_trimming(create: CreateReport) -> None:
    """이름은 앞뒤 공백을 지운 뒤 비교한다.

    테스트 코드: RS-009
    """
    # given: "Pipeline" 리포트
    await create.execute(content_input("Pipeline"), viewer(ALICE))
    # when·then: " Pipeline "으로 만들면 이름 중복 오류다
    with pytest.raises(DuplicateReportNameError):
        await create.execute(content_input(" Pipeline "), viewer(ALICE))


async def test_a_deleted_reports_name_can_be_used_again(
    create: CreateReport, uow_factory: UnitOfWorkFactory
) -> None:
    """지운 리포트의 이름은 다시 쓸 수 있다.

    테스트 코드: RS-009
    """
    # given: 만든 뒤 지운 "Pipeline"
    first = await create.execute(content_input("Pipeline"), viewer(ALICE))
    await DeleteReport(uow_factory).execute(first.id, viewer(ALICE))
    # when: 같은 이름으로 다시 만든다
    again = await create.execute(content_input("Pipeline"), viewer(ALICE))
    # then: 새 리포트가 생긴다
    assert again.name == "Pipeline"
    assert again.id != first.id

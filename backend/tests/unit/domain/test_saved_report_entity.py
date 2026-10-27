"""Report 엔티티(AC1·7·8·9·10): 만들기, 덮어쓰기, 판정 순서(404 -> 403 -> 409), 복제.

판정 순서의 첫째는 항상 "볼 수 있는가"다. 볼 수 없는 리포트는 존재 자체를 숨긴다.
"""

import pytest

from app.domain.auth.errors import AccessDeniedError
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidStateError, NotFoundError
from app.domain.report.errors import ReportDefinitionError
from app.domain.saved_report.entities import Report
from app.domain.saved_report.errors import (
    DuplicateReportNameError,
    ReportDeleteForbiddenError,
    ReportEditConflictError,
    ReportEditForbiddenError,
    ReportNotFoundError,
    ReportVisibilityForbiddenError,
)
from app.domain.saved_report.values import ReportId, ReportVisibility
from tests.factories import NOW, later
from tests.factories_report import make_broken_report, make_content, make_report
from tests.support.expect import raises_with
from tests.support.ids import new_id
from tests.support.report_defs import col, cond, raw
from tests.support.user_ids import uid

OWNER = uid("rpt-owner")
OTHER = uid("rpt-other")
ADMIN = uid("rpt-admin")


def test_create_sets_owner_editor_revision_one_and_times() -> None:
    content = make_content("분기 현황", description="설명", visibility="private")

    report = Report.create(entity_id=ReportId(new_id()), content=content, owner=OWNER, now=NOW)

    assert (report.name, report.description, report.visibility) == (
        "분기 현황",
        "설명",
        ReportVisibility.PRIVATE,
    )
    assert report.owner_user_id == OWNER
    assert report.updated_by_user_id == OWNER
    assert report.revision == 1
    assert (report.created_at, report.updated_at) == (NOW, NOW)
    assert report.definition == content.definition
    assert report.generated_sql == content.generated_sql


def test_overwrite_replaces_content_and_bumps_revision() -> None:
    report = make_report("이전", owner=OWNER, visibility="public", description="옛 설명")
    definition = raw([col("deal.vendor", group=True), col("deal.amount")])
    content = make_content(
        "이후",
        description="새 설명",
        visibility="public",
        definition=definition,
        generated_sql="SELECT new",
    )

    report.overwrite(content, editor=OTHER, role=Role.SALES, expected_revision=1, now=later(5))

    assert (report.name, report.description) == ("이후", "새 설명")
    assert report.definition == definition
    assert report.generated_sql == "SELECT new"
    assert report.updated_by_user_id == OTHER
    assert report.revision == 2
    assert report.updated_at == later(5)


def test_overwrite_keeps_the_owner_and_created_at() -> None:
    report = make_report(owner=OWNER, visibility="public")

    report.overwrite(
        make_content(), editor=OTHER, role=Role.USER, expected_revision=1, now=later(5)
    )

    assert report.owner_user_id == OWNER
    assert report.created_at == NOW


def test_overwrite_with_old_revision_raises_conflict_and_changes_nothing() -> None:
    report = make_report("원본", owner=OWNER, revision=3)

    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content("바뀜"), editor=OWNER, role=Role.SALES, expected_revision=2, now=later(5)
        )

    assert (report.name, report.revision, report.updated_by_user_id) == ("원본", 3, OWNER)
    assert report.updated_at == NOW


def test_overwrite_with_a_future_revision_is_also_a_conflict() -> None:
    report = make_report(owner=OWNER, revision=1)

    with pytest.raises(ReportEditConflictError):
        report.overwrite(
            make_content(), editor=OWNER, role=Role.SALES, expected_revision=2, now=later(5)
        )


def test_non_owner_cannot_change_visibility_but_can_keep_it() -> None:
    report = make_report(owner=OWNER, visibility="public")

    with pytest.raises(ReportVisibilityForbiddenError):
        report.overwrite(
            make_content(visibility="private"),
            editor=OTHER,
            role=Role.SALES,
            expected_revision=1,
            now=later(5),
        )
    assert report.visibility is ReportVisibility.PUBLIC
    assert report.revision == 1

    report.overwrite(
        make_content(visibility="public"),
        editor=OTHER,
        role=Role.SALES,
        expected_revision=1,
        now=later(5),
    )
    assert report.revision == 2


@pytest.mark.parametrize(
    ("editor", "role"), [(OWNER, Role.USER), (ADMIN, Role.ADMIN)], ids=["owner", "admin"]
)
def test_owner_and_admin_can_change_visibility(editor: object, role: Role) -> None:
    report = make_report(owner=OWNER, visibility="public")

    report.overwrite(
        make_content(visibility="private"),
        editor=editor,  # type: ignore[arg-type]
        role=role,
        expected_revision=1,
        now=later(5),
    )

    assert report.visibility is ReportVisibility.PRIVATE


def test_hidden_report_check_comes_before_conflict_and_visibility() -> None:
    report = make_report(owner=OWNER, visibility="private", revision=4)

    with pytest.raises(ReportNotFoundError):
        report.overwrite(
            make_content(visibility="public"),
            editor=OTHER,
            role=Role.SALES,
            expected_revision=1,  # 틀린 revision이지만 404가 먼저다
            now=later(5),
        )
    assert report.revision == 4


def test_visibility_check_comes_before_the_conflict_check() -> None:
    report = make_report(owner=OWNER, visibility="public", revision=4)

    with pytest.raises(ReportVisibilityForbiddenError):
        report.overwrite(
            make_content(visibility="private"),
            editor=OTHER,
            role=Role.SALES,
            expected_revision=1,
            now=later(5),
        )


def test_admin_can_overwrite_others_private_report() -> None:
    report = make_report(owner=OWNER, visibility="private")

    report.overwrite(
        make_content(visibility="private"),
        editor=ADMIN,
        role=Role.ADMIN,
        expected_revision=1,
        now=later(5),
    )

    assert report.updated_by_user_id == ADMIN
    assert report.owner_user_id == OWNER


def test_ensure_visible_to_follows_the_view_rule() -> None:
    private = make_report(owner=OWNER, visibility="private")
    public = make_report(owner=OWNER, visibility="public")

    private.ensure_visible_to(OWNER, Role.USER)
    private.ensure_visible_to(ADMIN, Role.ADMIN)
    public.ensure_visible_to(OTHER, Role.USER)
    with pytest.raises(ReportNotFoundError):
        private.ensure_visible_to(OTHER, Role.SALES)


def test_owner_deletes_own_private_and_public_but_not_others_public() -> None:
    private = make_report(owner=OWNER, visibility="private")
    public = make_report(owner=OWNER, visibility="public")

    private.ensure_deletable_by(OWNER, Role.USER)
    public.ensure_deletable_by(OWNER, Role.USER)
    public.ensure_deletable_by(ADMIN, Role.ADMIN)
    private.ensure_deletable_by(ADMIN, Role.ADMIN)
    with pytest.raises(ReportDeleteForbiddenError):
        public.ensure_deletable_by(OTHER, Role.SALES)


def test_delete_of_others_private_report_is_not_found_not_forbidden() -> None:
    private = make_report(owner=OWNER, visibility="private")

    with pytest.raises(ReportNotFoundError):
        private.ensure_deletable_by(OTHER, Role.SALES)


def test_copy_as_makes_a_new_owner_with_revision_one_and_same_definition() -> None:
    definition = raw([col("deal.vendor", group=True)], [cond("deal.name", "contains", "a")])
    source = make_report(
        "원본", owner=OWNER, visibility="private", revision=7, definition=definition
    )
    new_id_value = ReportId(new_id())

    copy = source.copy_as(
        entity_id=new_id_value,
        meta_name="원본 복사본",
        meta_description="복사 설명",
        visibility=ReportVisibility.PUBLIC,
        generated_sql="SELECT copy",
        owner=OTHER,
        now=later(9),
    )

    assert copy.id == new_id_value
    assert (copy.name, copy.description, copy.visibility) == (
        "원본 복사본",
        "복사 설명",
        ReportVisibility.PUBLIC,
    )
    assert copy.owner_user_id == OTHER
    assert copy.updated_by_user_id == OTHER
    assert copy.revision == 1
    assert copy.definition == definition
    assert copy.generated_sql == "SELECT copy"
    assert (copy.created_at, copy.updated_at) == (later(9), later(9))
    assert (source.name, source.owner_user_id, source.revision) == ("원본", OWNER, 7)


def test_entities_follow_the_definition() -> None:
    report = make_report(definition=raw([col("deal.code"), col("action.type")]))

    assert [e.value for e in report.entities()] == ["deal", "action"]


def test_report_errors_have_the_expected_kinds_and_messages() -> None:
    missing = ReportNotFoundError(ReportId(5))
    assert isinstance(missing, NotFoundError)
    assert str(missing) == "리포트를 찾을 수 없습니다."

    duplicate = DuplicateReportNameError("x")
    assert isinstance(duplicate, AlreadyExistsError)
    assert str(duplicate) == "같은 이름의 리포트가 이미 있습니다."

    conflict = ReportEditConflictError()
    assert isinstance(conflict, InvalidStateError)
    assert str(conflict) == (
        "다른 사용자가 먼저 이 리포트를 저장했습니다."
        " 다시 불러온 뒤 수정하거나 다른 이름으로 저장하세요."
    )
    with raises_with(
        ReportDeleteForbiddenError, "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."
    ):
        raise ReportDeleteForbiddenError
    with raises_with(
        ReportVisibilityForbiddenError, "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."
    ):
        raise ReportVisibilityForbiddenError
    with raises_with(ReportEditForbiddenError, "이 리포트를 수정할 권한이 없습니다."):
        raise ReportEditForbiddenError
    for forbidden in (
        ReportDeleteForbiddenError(),
        ReportVisibilityForbiddenError(),
        ReportEditForbiddenError(),
    ):
        assert isinstance(forbidden, AccessDeniedError)


# ---- 깨진 저장 정의 (계획 11.2) ----


def test_broken_report_has_no_entities() -> None:
    assert make_broken_report().entities() == ()


def test_broken_report_refuses_to_give_its_definition_as_stored_invalid() -> None:
    with pytest.raises(ReportDefinitionError) as caught:
        make_broken_report().readable_definition()

    assert [(i.location, i.code) for i in caught.value.issues] == [
        (("definition",), "stored-invalid")
    ]


def test_readable_definition_returns_the_definition_of_a_healthy_report() -> None:
    definition = raw([col("deal.code")])

    assert make_report(definition=definition).readable_definition() == definition


def test_broken_report_is_still_hidden_from_users_who_cannot_see_it() -> None:
    report = make_broken_report(owner=OWNER, visibility="private")

    with pytest.raises(ReportNotFoundError):
        report.ensure_visible_to(OTHER, Role.SALES)


def test_overwrite_repairs_a_broken_report() -> None:
    report = make_broken_report(owner=OWNER, revision=3)
    definition = raw([col("deal.vendor", group=True)])

    report.overwrite(
        make_content("복구", definition=definition),
        editor=OWNER,
        role=Role.SALES,
        expected_revision=3,
        now=later(5),
    )

    assert report.readable_definition() == definition
    assert report.revision == 4


def test_copy_of_a_broken_report_is_refused_as_stored_invalid() -> None:
    source = make_broken_report(owner=OWNER)

    with pytest.raises(ReportDefinitionError):
        source.copy_as(
            entity_id=ReportId(new_id()),
            meta_name="복사",
            meta_description="",
            visibility=ReportVisibility.PUBLIC,
            generated_sql="SELECT 1",
            owner=OTHER,
            now=later(1),
        )

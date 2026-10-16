"""FakeUseCases에 섞어 쓰는 코드·BANT Label 유스케이스 조립(파일 길이를 나누기 위한 mixin)."""

from typing import TYPE_CHECKING

from app.application.bant.delete_label import DeleteBantLabel
from app.application.bant.list_labels import ListBantLabels
from app.application.bant.register_label import RegisterBantLabel
from app.application.bant.rename_label import RenameBantLabel
from app.application.code.delete_code import DeleteCode
from app.application.code.list_code_set import ListCodeSet
from app.application.code.list_codes_with_usage import ListCodesWithUsage
from app.application.code.register_code import RegisterCode
from app.application.code.rename_code import RenameCode
from app.application.code.reorder_codes import ReorderCodes

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class CatalogUseCases:
    """`_factory`(UnitOfWorkFactory)와 `clock`을 가진 클래스에 섞는다."""

    clock: Clock

    def _factory(self) -> object:  # 실제 구현은 FakeUseCases가 FakeUnitOfWork로 덮어쓴다
        raise NotImplementedError

    def _uow_factory(self) -> UnitOfWorkFactory:
        return self._factory  # type: ignore[return-value]

    def list_code_set(self) -> ListCodeSet:
        return ListCodeSet(self._uow_factory())

    def list_codes_with_usage(self) -> ListCodesWithUsage:
        return ListCodesWithUsage(self._uow_factory())

    def register_code(self) -> RegisterCode:
        return RegisterCode(self._uow_factory(), self.clock)

    def rename_code(self) -> RenameCode:
        return RenameCode(self._uow_factory(), self.clock)

    def reorder_codes(self) -> ReorderCodes:
        return ReorderCodes(self._uow_factory(), self.clock)

    def delete_code(self) -> DeleteCode:
        return DeleteCode(self._uow_factory())

    def list_bant_labels(self) -> ListBantLabels:
        return ListBantLabels(self._uow_factory())

    def register_bant_label(self) -> RegisterBantLabel:
        return RegisterBantLabel(self._uow_factory(), self.clock)

    def rename_bant_label(self) -> RenameBantLabel:
        return RenameBantLabel(self._uow_factory(), self.clock)

    def delete_bant_label(self) -> DeleteBantLabel:
        return DeleteBantLabel(self._uow_factory())

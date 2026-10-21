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
    from app.application.action_type.delete_action_type import DeleteActionType
    from app.application.action_type.list_action_types import ListActionTypes
    from app.application.action_type.register_action_type import RegisterActionType
    from app.application.action_type.rename_action_type import RenameActionType
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.vendor.delete_solution import DeleteSolution
    from app.application.vendor.delete_vendor import DeleteVendor
    from app.application.vendor.list_vendors import ListVendors
    from app.application.vendor.register_solution import RegisterSolution
    from app.application.vendor.register_vendor import RegisterVendor
    from app.application.vendor.rename_solution import RenameSolution
    from app.application.vendor.rename_vendor import RenameVendor


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

    # Action 유형 유스케이스도 사용 시점에 가져온다(구현 전에도 다른 테스트의 수집이 막히지 않게)

    def list_action_types(self) -> ListActionTypes:
        from app.application.action_type.list_action_types import (  # noqa: PLC0415
            ListActionTypes,
        )

        return ListActionTypes(self._uow_factory())

    def register_action_type(self) -> RegisterActionType:
        from app.application.action_type.register_action_type import (  # noqa: PLC0415
            RegisterActionType,
        )

        return RegisterActionType(self._uow_factory(), self.clock)

    def rename_action_type(self) -> RenameActionType:
        from app.application.action_type.rename_action_type import (  # noqa: PLC0415
            RenameActionType,
        )

        return RenameActionType(self._uow_factory(), self.clock)

    def delete_action_type(self) -> DeleteActionType:
        from app.application.action_type.delete_action_type import (  # noqa: PLC0415
            DeleteActionType,
        )

        return DeleteActionType(self._uow_factory())

    # Vendor 유스케이스는 사용 시점에 가져온다(구현 전에도 다른 테스트의 수집이 막히지 않게)

    def list_vendors(self) -> ListVendors:
        from app.application.vendor.list_vendors import ListVendors  # noqa: PLC0415

        return ListVendors(self._uow_factory())

    def register_vendor(self) -> RegisterVendor:
        from app.application.vendor.register_vendor import RegisterVendor  # noqa: PLC0415

        return RegisterVendor(self._uow_factory(), self.clock)

    def rename_vendor(self) -> RenameVendor:
        from app.application.vendor.rename_vendor import RenameVendor  # noqa: PLC0415

        return RenameVendor(self._uow_factory(), self.clock)

    def delete_vendor(self) -> DeleteVendor:
        from app.application.vendor.delete_vendor import DeleteVendor  # noqa: PLC0415

        return DeleteVendor(self._uow_factory())

    def register_solution(self) -> RegisterSolution:
        from app.application.vendor.register_solution import RegisterSolution  # noqa: PLC0415

        return RegisterSolution(self._uow_factory(), self.clock)

    def rename_solution(self) -> RenameSolution:
        from app.application.vendor.rename_solution import RenameSolution  # noqa: PLC0415

        return RenameSolution(self._uow_factory(), self.clock)

    def delete_solution(self) -> DeleteSolution:
        from app.application.vendor.delete_solution import DeleteSolution  # noqa: PLC0415

        return DeleteSolution(self._uow_factory())

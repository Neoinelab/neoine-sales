"""코드(Status·Forecast)와 BANT Label·Vendor 유스케이스 조립. Container가 위임한다."""

from typing import TYPE_CHECKING

from app.application.action_type.delete_action_type import DeleteActionType
from app.application.action_type.list_action_types import ListActionTypes
from app.application.action_type.register_action_type import RegisterActionType
from app.application.action_type.rename_action_type import RenameActionType
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
from app.application.vendor.delete_solution import DeleteSolution
from app.application.vendor.delete_vendor import DeleteVendor
from app.application.vendor.list_vendors import ListVendors
from app.application.vendor.register_solution import RegisterSolution
from app.application.vendor.register_vendor import RegisterVendor
from app.application.vendor.rename_solution import RenameSolution
from app.application.vendor.rename_vendor import RenameVendor

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class CatalogAssembly:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def list_code_set(self) -> ListCodeSet:
        return ListCodeSet(self._uow)

    def list_codes_with_usage(self) -> ListCodesWithUsage:
        return ListCodesWithUsage(self._uow)

    def register_code(self) -> RegisterCode:
        return RegisterCode(self._uow, self._clock)

    def rename_code(self) -> RenameCode:
        return RenameCode(self._uow, self._clock)

    def reorder_codes(self) -> ReorderCodes:
        return ReorderCodes(self._uow, self._clock)

    def delete_code(self) -> DeleteCode:
        return DeleteCode(self._uow)

    def list_bant_labels(self) -> ListBantLabels:
        return ListBantLabels(self._uow)

    def register_bant_label(self) -> RegisterBantLabel:
        return RegisterBantLabel(self._uow, self._clock)

    def rename_bant_label(self) -> RenameBantLabel:
        return RenameBantLabel(self._uow, self._clock)

    def delete_bant_label(self) -> DeleteBantLabel:
        return DeleteBantLabel(self._uow)

    def list_vendors(self) -> ListVendors:
        return ListVendors(self._uow)

    def register_vendor(self) -> RegisterVendor:
        return RegisterVendor(self._uow, self._clock)

    def rename_vendor(self) -> RenameVendor:
        return RenameVendor(self._uow, self._clock)

    def delete_vendor(self) -> DeleteVendor:
        return DeleteVendor(self._uow)

    def register_solution(self) -> RegisterSolution:
        return RegisterSolution(self._uow, self._clock)

    def rename_solution(self) -> RenameSolution:
        return RenameSolution(self._uow, self._clock)

    def delete_solution(self) -> DeleteSolution:
        return DeleteSolution(self._uow)

    def list_action_types(self) -> ListActionTypes:
        return ListActionTypes(self._uow)

    def register_action_type(self) -> RegisterActionType:
        return RegisterActionType(self._uow, self._clock)

    def rename_action_type(self) -> RenameActionType:
        return RenameActionType(self._uow, self._clock)

    def delete_action_type(self) -> DeleteActionType:
        return DeleteActionType(self._uow)

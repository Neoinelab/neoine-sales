"""Action 유형 유스케이스를 CatalogAssembly에 위임하는 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.action_type.delete_action_type import DeleteActionType
    from app.application.action_type.list_action_types import ListActionTypes
    from app.application.action_type.register_action_type import RegisterActionType
    from app.application.action_type.rename_action_type import RenameActionType
    from app.container_catalog import CatalogAssembly


class ActionTypeUseCases:
    _catalog: CatalogAssembly

    def list_action_types(self) -> ListActionTypes:
        return self._catalog.list_action_types()

    def register_action_type(self) -> RegisterActionType:
        return self._catalog.register_action_type()

    def rename_action_type(self) -> RenameActionType:
        return self._catalog.rename_action_type()

    def delete_action_type(self) -> DeleteActionType:
        return self._catalog.delete_action_type()

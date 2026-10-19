"""Vendor·Solution 유스케이스를 CatalogAssembly에 위임하는 Container 부분(길이 분리)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.vendor.delete_solution import DeleteSolution
    from app.application.vendor.delete_vendor import DeleteVendor
    from app.application.vendor.list_vendors import ListVendors
    from app.application.vendor.register_solution import RegisterSolution
    from app.application.vendor.register_vendor import RegisterVendor
    from app.application.vendor.rename_solution import RenameSolution
    from app.application.vendor.rename_vendor import RenameVendor
    from app.container_catalog import CatalogAssembly


class VendorUseCases:
    _catalog: CatalogAssembly

    def list_vendors(self) -> ListVendors:
        return self._catalog.list_vendors()

    def register_vendor(self) -> RegisterVendor:
        return self._catalog.register_vendor()

    def rename_vendor(self) -> RenameVendor:
        return self._catalog.rename_vendor()

    def delete_vendor(self) -> DeleteVendor:
        return self._catalog.delete_vendor()

    def register_solution(self) -> RegisterSolution:
        return self._catalog.register_solution()

    def rename_solution(self) -> RenameSolution:
        return self._catalog.rename_solution()

    def delete_solution(self) -> DeleteSolution:
        return self._catalog.delete_solution()

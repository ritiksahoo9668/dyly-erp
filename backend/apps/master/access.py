"""Master administration permissions and reference lookups.

Maintaining a Master (list page, create, edit, upload, activate/deactivate) needs
MASTER.<SUBMODULE>.<ACTION>. Transaction screens and other Masters' forms only need to *select*
Master records, so every Master exposes ``GET <resource>/lookup/``: reference data open to any
active ERP user, with slim fields for Masters holding personal or commercial data.
"""

from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.access_control.constants import Action, Module
from apps.common.access_control.permissions import OPEN, ModuleAccessPermission

from .models import Employee, Material, Vendor

MASTER_ACTION_MAP: dict[str, str] = {
    "lookup_records": OPEN,
    "stats": Action.VIEW,
    "locations": Action.VIEW,
    "template": Action.UPLOAD,
    "validate_excel": Action.UPLOAD,
    "import_excel": Action.UPLOAD,
    "destroy": Action.ACTIVATE_DEACTIVATE,
    "activate": Action.ACTIVATE_DEACTIVATE,
    "bulk_status": Action.ACTIVATE_DEACTIVATE,
    "image_upload": Action.EDIT,
    "image_url": Action.EDIT,
    "image_remove": Action.EDIT,
}


class MasterAccessMixin:
    """Mixin for Master viewsets. Subclasses set ``access_submodule`` (registry key)."""

    permission_classes = [IsAuthenticated, ModuleAccessPermission]
    access_module = Module.MASTER
    access_submodule: str = ""
    access_action_map = MASTER_ACTION_MAP
    lookup_serializer_class = None

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup_records(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        serializer_class = self.lookup_serializer_class or self.get_serializer_class()
        context = self.get_serializer_context()
        page = self.paginate_queryset(queryset)
        if page is not None:
            data = serializer_class(page, many=True, context=context).data
            return self.get_paginated_response(data)
        return Response(serializer_class(queryset, many=True, context=context).data)


class EmployeeLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ("id", "employee_code", "full_name", "is_active")
        read_only_fields = fields


class VendorLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ("id", "erp_vendor_id", "sap_vendor_id", "vendor_name", "location", "is_active")
        read_only_fields = fields


class MaterialLookupSerializer(serializers.ModelSerializer):
    uom = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = ("id", "sap_code", "item_name", "uom", "is_active")
        read_only_fields = fields

    def get_uom(self, obj: Material) -> dict:
        return {"id": obj.uom_id, "name": obj.uom.name, "symbol": obj.uom.symbol}

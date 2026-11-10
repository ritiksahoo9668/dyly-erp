from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.access_control.constants import Action, Module
from apps.common.access_control.registry import MODULES_BY_KEY
from apps.common.access_control.selectors import get_effective_access

from .models import (
    Company,
    Department,
    Designation,
    Division,
    Employee,
    Facility,
    ImportJob,
    Material,
    MaterialCategory,
    MaterialGroup,
    MaterialSubcategory,
    MaterialType,
    Plant,
    PurchasingGroup,
    QcParameter,
    StockYard,
    Unit,
    Uom,
    Vendor,
    Vertical,
    WeighBridge,
)

# Keys match the Master navigation stage ids in the frontend.
SUMMARY_MODELS = {
    "employee": Employee,
    "department": Department,
    "designation": Designation,
    "company": Company,
    "unit": Unit,
    "division": Division,
    "vertical": Vertical,
    "facility": Facility,
    "material-item": Material,
    "material-category": MaterialCategory,
    "material-sub-category": MaterialSubcategory,
    "material-group": MaterialGroup,
    "material-type": MaterialType,
    "purchasing-group": PurchasingGroup,
    "plant": Plant,
    "uom": Uom,
    "qc-parameter": QcParameter,
    "vendor": Vendor,
    "stock-yard": StockYard,
    "weighbridge": WeighBridge,
}

RECENT_IMPORT_LIMIT = 6


MASTER_SUBMODULE_BY_NAV_ID = {
    sub.nav_id: sub.key for sub in MODULES_BY_KEY[Module.MASTER].submodules
}


class MasterSummaryView(APIView):
    """Record counts for the masters the user can view and imports for those they can upload."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        access = get_effective_access(request.user)
        masters = {}
        for key, model in SUMMARY_MODELS.items():
            if not access.can(Module.MASTER, MASTER_SUBMODULE_BY_NAV_ID[key], Action.VIEW):
                continue
            counts = model.objects.aggregate(
                total=Count("pk"),
                active=Count("pk", filter=Q(is_active=True)),
            )
            masters[key] = {"total": counts["total"], "active": counts["active"]}

        uploadable = [
            master_type
            for master_type in ImportJob.MasterType.values
            if access.can(Module.MASTER, master_type.upper(), Action.UPLOAD)
        ]
        jobs = (
            ImportJob.objects.filter(master_type__in=uploadable)
            .select_related("uploaded_by")
            .order_by("-created_at")[:RECENT_IMPORT_LIMIT]
        )
        recent_imports = [
            {
                "id": job.pk,
                "master_type": job.master_type,
                "master_label": job.get_master_type_display(),
                "status": job.status,
                "original_filename": job.original_filename,
                "total_rows": job.total_rows,
                "created_rows": job.created_rows,
                "skipped_rows": job.skipped_rows,
                "failed_rows": job.failed_rows,
                "uploaded_by": job.uploaded_by.display_name if job.uploaded_by else None,
                "created_at": job.created_at,
            }
            for job in jobs
        ]
        return Response({"masters": masters, "recent_imports": recent_imports})

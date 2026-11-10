from django.db import IntegrityError, transaction
from django.db.models import F, Prefetch, ProtectedError
from django.http import FileResponse, HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.pagination import StandardPagination

from .access import (
    EmployeeLookupSerializer,
    MasterAccessMixin,
    MaterialLookupSerializer,
    VendorLookupSerializer,
)
from .company_serializers import CompanySerializer, CompanyWriteSerializer
from .employee_excel import (
    build_employee_template,
    preview_employees_from_excel,
    validate_employee_template,
)
from .employee_serializers import EmployeeListSerializer, EmployeeSerializer
from .excel import (
    build_material_group_template,
    build_material_subcategory_template,
    build_material_type_template,
    build_name_master_template,
    build_plant_template,
    build_purchasing_group_template,
    build_stock_yard_template,
    build_unit_template,
    build_uom_template,
    build_vertical_template,
    preview_name_master_from_excel,
    preview_verticals_from_excel,
    validate_material_group_template,
    validate_material_subcategory_template,
    validate_material_type_template,
    validate_name_master_template,
    validate_plant_template,
    validate_purchasing_group_template,
    validate_stock_yard_template,
    validate_unit_template,
    validate_uom_template,
    validate_vertical_template,
)
from .import_serializers import ImportJobSerializer
from .material_excel import (
    build_material_template,
    preview_materials_from_excel,
    validate_material_template,
)
from .material_group_serializers import MaterialGroupSerializer, MaterialGroupWriteSerializer
from .material_images import (
    MaterialImageError,
    remove_image,
    set_image_url,
    set_uploaded_image,
)
from .material_item_serializers import (
    MaterialListSerializer,
    MaterialSerializer,
    MaterialWriteSerializer,
)
from .material_serializers import (
    MaterialSubcategorySerializer,
    MaterialSubcategoryWriteSerializer,
)
from .material_type_serializers import MaterialTypeSerializer, MaterialTypeWriteSerializer
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
from .plant_serializers import PlantSerializer, PlantWriteSerializer
from .purchasing_group_serializers import (
    PurchasingGroupSerializer,
    PurchasingGroupWriteSerializer,
)
from .qc_parameter_excel import (
    build_qc_parameter_template,
    preview_qc_parameters_from_excel,
    validate_qc_parameter_template,
)
from .qc_parameter_serializers import QcParameterSerializer
from .serializers import make_name_master_serializers
from .stock_yard_serializers import StockYardSerializer, StockYardWriteSerializer
from .tasks import process_import_job_task
from .unit_serializers import UnitSerializer, UnitWriteSerializer
from .uom_serializers import UomSerializer, UomWriteSerializer
from .vendor_excel import (
    build_vendor_template,
    preview_vendors_from_excel,
    validate_vendor_template,
)
from .vendor_serializers import VendorSerializer
from .vertical_serializers import VerticalSerializer, VerticalWriteSerializer

MASTER_TYPE_BY_MODEL = {
    Division: ImportJob.MasterType.DIVISION,
    Department: ImportJob.MasterType.DEPARTMENT,
    Designation: ImportJob.MasterType.DESIGNATION,
    Facility: ImportJob.MasterType.FACILITY,
    Company: ImportJob.MasterType.COMPANY,
    MaterialCategory: ImportJob.MasterType.MATERIAL_CATEGORY,
    WeighBridge: ImportJob.MasterType.WEIGHBRIDGE,
}


def _read_upload(request):
    upload = request.FILES.get("file")
    if upload is None:
        return None, Response(
            {"detail": "Upload an Excel file using the 'file' field."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    filename = (upload.name or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        return None, Response(
            {"detail": "Only .xlsx Excel files are supported."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return upload, None


def _queue_import_job(*, request, upload, master_type: str) -> Response:
    job = ImportJob.objects.create(
        master_type=master_type,
        status=ImportJob.Status.PENDING,
        original_filename=upload.name or "",
        uploaded_by=request.user if request.user.is_authenticated else None,
        detail="Queued for background import.",
    )
    job.source_file.save(upload.name or "upload.xlsx", upload, save=True)

    async_result = process_import_job_task.delay(job.pk)
    job.celery_task_id = async_result.id or ""
    job.save(update_fields=["celery_task_id", "updated_at"])

    return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ImportJobViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ImportJobSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = ImportJob.objects.all()
        master_type = (self.request.query_params.get("master_type") or "").strip()
        if master_type:
            qs = qs.filter(master_type=master_type)
        if self.request.user.is_authenticated:
            qs = qs.filter(uploaded_by=self.request.user)
        return qs

    @action(detail=True, methods=["get"], url_path="errors")
    def download_errors(self, request, pk=None):
        job = self.get_object()
        if not job.error_file:
            return Response(
                {"detail": "No error file is available for this import job."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(
            job.error_file.open("rb"),
            as_attachment=True,
            filename=f"import_job_{job.pk}_errors.xlsx",
        )


class NameMasterViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    """Reusable CRUD + Excel import/template for simple name masters."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    model = None
    label = "Name"
    template_filename = "template.xlsx"
    template_sheet = "Sheet1"
    template_samples: list[str] = []
    serializer_class = None
    write_serializer_class = None

    def get_queryset(self):
        qs = self.model.objects.all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return self.write_serializer_class
        return self.serializer_class

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        f'"{instance.name}" is used by other records and cannot be deleted. '
                        "Deactivate it instead."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_name_master_template(
            sheet_title=self.template_sheet,
            header=self.label,
            sample_rows=self.template_samples,
        )
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{self.template_filename}"'
        return response

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            preview = preview_name_master_from_excel(
                upload,
                model=self.model,
                header=self.label,
                label=self.label,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(preview, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        master_type = MASTER_TYPE_BY_MODEL.get(self.model)
        if master_type is None:
            return Response(
                {"detail": "Unsupported master type for import."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            upload.seek(0)
            validate_name_master_template(upload, header=self.label)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(request=request, upload=upload, master_type=master_type)


def _build_viewset(
    *,
    model,
    label: str,
    route_slug: str,
    samples: list[str],
    access_submodule: str,
):
    read_serializer, write_serializer = make_name_master_serializers(model, label=label)

    attrs = {
        "access_submodule": access_submodule,
        "model": model,
        "label": label,
        "template_filename": f"{route_slug}_template.xlsx",
        "template_sheet": model.__name__ + "s",
        "template_samples": samples,
        "serializer_class": read_serializer,
        "write_serializer_class": write_serializer,
    }
    return type(f"{model.__name__}ViewSet", (NameMasterViewSet,), attrs)


DivisionViewSet = _build_viewset(
    model=Division,
    label="Division Name",
    route_slug="division",
    samples=["DRI", "CPP", "SMS", "Corporate"],
    access_submodule="DIVISION",
)

DepartmentViewSet = _build_viewset(
    model=Department,
    label="Department Name",
    route_slug="department",
    samples=["Mechanical", "Electrical", "Process", "HR & Admin", "Procurement"],
    access_submodule="DEPARTMENT",
)

DesignationViewSet = _build_viewset(
    model=Designation,
    label="Designation Name",
    route_slug="designation",
    samples=["Manager", "Assistant Manager", "Deputy Manager", "Executive", "Engineer"],
    access_submodule="DESIGNATION",
)

FacilityViewSet = _build_viewset(
    model=Facility,
    label="Facility Name",
    route_slug="facility",
    samples=["KILN 1", "KILN 2", "WHRB-1", "Furnace-1", "LRF"],
    access_submodule="FACILITY",
)

_CompanyNameMasterViewSet = _build_viewset(
    model=Company,
    label="Company Name",
    route_slug="company",
    samples=["De-Maithan Ispat Limited"],
    access_submodule="COMPANY",
)


class CompanyViewSet(_CompanyNameMasterViewSet):
    serializer_class = CompanySerializer
    write_serializer_class = CompanyWriteSerializer

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            Prefetch("units", queryset=Unit.objects.order_by("name", "id"))
        )


class UnitViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "UNIT"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Unit.objects.select_related("company").all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        company = (self.request.query_params.get("company") or "").strip()
        if company.isdigit():
            qs = qs.filter(company_id=int(company))
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return UnitWriteSerializer
        return UnitSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_unit_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="unit_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_unit_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.UNIT,
        )

MaterialCategoryViewSet = _build_viewset(
    model=MaterialCategory,
    label="Category Name",
    route_slug="material_category",
    samples=["Electrical", "Mechanical", "Instrumentation", "Civil"],
    access_submodule="MATERIAL_CATEGORY",
)

WeighBridgeViewSet = _build_viewset(
    model=WeighBridge,
    label="WeighBridge Name",
    route_slug="weighbridge",
    samples=["WB-1", "WB-2", "WB-3"],
    access_submodule="WEIGHBRIDGE",
)


class VerticalViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "VERTICAL"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Vertical.objects.select_related("department").all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        department = (self.request.query_params.get("department") or "").strip()
        if department.isdigit():
            qs = qs.filter(department_id=int(department))
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return VerticalWriteSerializer
        return VerticalSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_vertical_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="vertical_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            preview = preview_verticals_from_excel(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(preview, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_vertical_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.VERTICAL,
        )


class UomViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "UOM"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        qs = Uom.objects.all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(symbol__icontains=search))
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return UomWriteSerializer
        return UomSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_uom_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="uom_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_uom_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.UOM,
        )


class StockYardViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "STOCK_YARD"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        qs = StockYard.objects.all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(sap_storage_code__icontains=search))
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return StockYardWriteSerializer
        return StockYardSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_stock_yard_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="stock_yard_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_stock_yard_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.STOCK_YARD,
        )


class MaterialGroupViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "MATERIAL_GROUP"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        qs = MaterialGroup.objects.all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(sap_material_group_code__icontains=search)
            )
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return MaterialGroupWriteSerializer
        return MaterialGroupSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_material_group_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="material_group_template.xlsx"'
        )
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_material_group_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.MATERIAL_GROUP,
        )


class PurchasingGroupViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "PURCHASING_GROUP"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        qs = PurchasingGroup.objects.all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(sap_purchase_group_code__icontains=search)
                | Q(remarks__icontains=search)
            )
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PurchasingGroupWriteSerializer
        return PurchasingGroupSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_purchasing_group_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="purchasing_group_template.xlsx"'
        )
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_purchasing_group_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.PURCHASING_GROUP,
        )


class PlantViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "PLANT"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        qs = Plant.objects.all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(sap_plant_code__icontains=search))
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return PlantWriteSerializer
        return PlantSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_plant_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="plant_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_plant_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.PLANT,
        )


class MaterialTypeViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "MATERIAL_TYPE"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        qs = MaterialType.objects.all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(material_type_code__icontains=search)
                | Q(erp_category_desc__icontains=search)
            )
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return MaterialTypeWriteSerializer
        return MaterialTypeSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_material_type_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="material_type_template.xlsx"'
        )
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_material_type_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.MATERIAL_TYPE,
        )


class MaterialSubcategoryViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "MATERIAL_SUBCATEGORY"
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = MaterialSubcategory.objects.select_related("category").all()
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        category = (self.request.query_params.get("category") or "").strip()
        if category.isdigit():
            qs = qs.filter(category_id=int(category))
        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return MaterialSubcategoryWriteSerializer
        return MaterialSubcategorySerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_material_subcategory_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="material_subcategory_template.xlsx"'
        )
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_material_subcategory_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.MATERIAL_SUBCATEGORY,
        )


class MaterialPagination(StandardPagination):
    page_size = 50


class MaterialViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "MATERIAL"
    lookup_serializer_class = MaterialLookupSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    pagination_class = MaterialPagination

    def get_queryset(self):
        from django.db.models import Q

        qs = Material.objects.select_related(
            "division",
            "material_category",
            "material_subcategory",
            "uom",
            "stock_yard",
            "department",
            "plant",
            "material_group",
            "material_type",
            "purchasing_group",
            "created_by",
            "updated_by",
        ).all()

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(sap_code__icontains=search)
                | Q(item_name__icontains=search)
                | Q(item_description__icontains=search)
                | Q(descriptive_spec__icontains=search)
                | Q(technical_spec__icontains=search)
                | Q(hsn_sac_code__icontains=search)
            )

        status_filter = (self.request.query_params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)

        def _int_param(name: str):
            raw = (self.request.query_params.get(name) or "").strip()
            if not raw:
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        filters = {
            "material_category_id": _int_param("material_category"),
            "material_subcategory_id": _int_param("material_subcategory"),
            "uom_id": _int_param("uom"),
            "material_type_id": _int_param("material_type"),
            "material_group_id": _int_param("material_group"),
            "purchasing_group_id": _int_param("purchasing_group"),
            "plant_id": _int_param("plant"),
            "stock_yard_id": _int_param("stock_yard"),
            "department_id": _int_param("department"),
            "division_id": _int_param("division"),
        }
        for field, value in filters.items():
            if value is not None:
                qs = qs.filter(**{field: value})

        ordering = (self.request.query_params.get("ordering") or "sap_code").strip()
        allowed = {
            "sap_code",
            "-sap_code",
            "item_name",
            "-item_name",
            "price",
            "-price",
            "created_at",
            "-created_at",
            "updated_at",
            "-updated_at",
        }
        if ordering in allowed:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("sap_code")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return MaterialListSerializer
        if self.action in {"create", "update", "partial_update"}:
            return MaterialWriteSerializer
        return MaterialSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(updated_by=user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        user = request.user if request.user.is_authenticated else None
        instance.updated_by = user
        instance.save(update_fields=["is_active", "updated_by", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        instance = self.get_object()
        instance.is_active = True
        user = request.user if request.user.is_authenticated else None
        instance.updated_by = user
        instance.save(update_fields=["is_active", "updated_by", "updated_at"])
        return Response(MaterialSerializer(instance, context=self.get_serializer_context()).data)

    def _image_response(self, instance):
        return Response(MaterialSerializer(instance, context=self.get_serializer_context()).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="image/upload",
        parser_classes=[MultiPartParser, FormParser],
    )
    def image_upload(self, request, pk=None):
        instance = self.get_object()
        upload = request.FILES.get("file") or request.FILES.get("image")
        user = request.user if request.user.is_authenticated else None
        try:
            set_uploaded_image(instance, upload, user=user)
        except MaterialImageError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._image_response(instance)

    @action(detail=True, methods=["post"], url_path="image/url")
    def image_url(self, request, pk=None):
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        try:
            set_image_url(instance, request.data.get("image_url"), user=user)
        except MaterialImageError as exc:
            return Response({"image_url": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        return self._image_response(instance)

    @action(detail=True, methods=["delete"], url_path="image")
    def image_remove(self, request, pk=None):
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        remove_image(instance, user=user)
        return self._image_response(instance)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_material_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="material_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_material_template(upload)
            upload.seek(0)
            preview = preview_materials_from_excel(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "total": preview["total"],
                "valid": preview["valid"],
                "existing": preview["existing"],
                "duplicate": preview["duplicate"],
                "failed": preview["failed"],
                "warnings": preview.get("warnings", 0),
                "warning_rows": preview.get("warning_rows") or [],
                "rows": preview.get("rows") or [],
                "errors": preview.get("errors") or [],
                "missing_masters_summary": preview.get("missing_masters_summary") or [],
            }
        )

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_material_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.MATERIAL,
        )


class EmployeePagination(StandardPagination):
    page_size = 25
    max_page_size = 100


EMPLOYEE_ORDERING_FIELDS = {
    "employee_code": "employee_code",
    "full_name": "full_name",
    "department": "department__name",
    "designation": "designation__name",
    "company": "company__name",
    "division": "division__name",
    "status": "is_active",
    "date_of_joining": "date_of_joining",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


class EmployeeViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "EMPLOYEE"
    lookup_serializer_class = EmployeeLookupSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    pagination_class = EmployeePagination

    def get_queryset(self):
        from django.db.models import Q

        qs = Employee.objects.select_related(
            "department",
            "vertical",
            "designation",
            "company",
            "division",
            "facility",
            "created_by",
            "updated_by",
        )
        params = self.request.query_params

        search = (params.get("search") or "").strip()
        if search and self.action == "lookup_records":
            qs = qs.filter(Q(employee_code__icontains=search) | Q(full_name__icontains=search))
        elif search:
            condition = (
                Q(employee_code__icontains=search)
                | Q(full_name__icontains=search)
                | Q(mobile_number__icontains=search)
                | Q(personal_email__icontains=search)
                | Q(company_email__icontains=search)
            )
            compact_mobile = "".join(ch for ch in search if ch.isdigit() or ch == "+")
            if compact_mobile and compact_mobile != search:
                condition |= Q(mobile_number__icontains=compact_mobile)
            qs = qs.filter(condition)

        status_filter = (params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)

        for name in (
            "department",
            "vertical",
            "designation",
            "company",
            "division",
            "facility",
        ):
            raw = (params.get(name) or "").strip()
            if raw.isdigit():
                qs = qs.filter(**{f"{name}_id": int(raw)})

        gender = (params.get("gender") or "").strip()
        if gender in Employee.Gender.values:
            qs = qs.filter(gender=gender)

        ordering = (params.get("ordering") or "employee_code").strip()
        descending = ordering.startswith("-")
        field = EMPLOYEE_ORDERING_FIELDS.get(ordering.lstrip("-"), "employee_code")
        qs = qs.order_by(f"-{field}" if descending else field, "id")
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return EmployeeListSerializer
        return EmployeeSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user, updated_by=user)

    def perform_update(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(updated_by=user)

    def _set_active(self, request, active: bool) -> Employee:
        instance = self.get_object()
        instance.is_active = active
        instance.updated_by = request.user if request.user.is_authenticated else None
        instance.save(update_fields=["is_active", "updated_by", "updated_at"])
        return instance

    def destroy(self, request, *args, **kwargs):
        self._set_active(request, False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        instance = self._set_active(request, True)
        return Response(EmployeeSerializer(instance, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        from django.db.models import Count, Q

        totals = Employee.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            departments=Count("department", distinct=True),
        )
        return Response(totals)

    @action(detail=False, methods=["post"], url_path="bulk-status")
    def bulk_status(self, request):
        ids = request.data.get("ids")
        is_active = request.data.get("is_active")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            return Response(
                {"ids": ["Select at least one employee."]}, status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(is_active, bool):
            return Response(
                {"is_active": ["is_active must be true or false."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from django.utils import timezone

        user = request.user if request.user.is_authenticated else None
        updated = Employee.objects.filter(pk__in=ids).update(
            is_active=is_active, updated_by=user, updated_at=timezone.now()
        )
        return Response({"updated": updated})

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        response = HttpResponse(
            build_employee_template().getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="employee_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_employee_template(upload)
            upload.seek(0)
            preview = preview_employees_from_excel(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(preview)

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_employee_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": "Unable to read the Excel file. Please use the download template."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.EMPLOYEE,
        )


UNREADABLE_EXCEL_MESSAGE = "Unable to read the Excel file. Please use the download template."


class QcParameterViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "QC_PARAMETER"
    serializer_class = QcParameterSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        from django.db.models import Q

        qs = QcParameter.objects.select_related("created_by", "updated_by")
        params = self.request.query_params
        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(short_name__icontains=search))
        status_filter = (params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)
        return qs.order_by("name", "id")

    def _user(self):
        return self.request.user if self.request.user.is_authenticated else None

    def perform_create(self, serializer):
        serializer.save(created_by=self._user(), updated_by=self._user(), is_active=True)

    def perform_update(self, serializer):
        serializer.save(updated_by=self._user())

    def _set_active(self, active: bool) -> QcParameter:
        instance = self.get_object()
        instance.is_active = active
        instance.updated_by = self._user()
        instance.save(update_fields=["is_active", "updated_by", "updated_at"])
        return instance

    def destroy(self, request, *args, **kwargs):
        self._set_active(False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        instance = self._set_active(True)
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        buffer = build_qc_parameter_template()
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="qc_parameter_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_qc_parameter_template(upload)
            upload.seek(0)
            preview = preview_qc_parameters_from_excel(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": UNREADABLE_EXCEL_MESSAGE}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(preview)

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_qc_parameter_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": UNREADABLE_EXCEL_MESSAGE}, status=status.HTTP_400_BAD_REQUEST
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.QC_PARAMETER,
        )


class VendorPagination(StandardPagination):
    page_size = 25
    max_page_size = 100


VENDOR_ORDERING_FIELDS = {
    "erp_vendor_id": "erp_vendor_id",
    "sap_vendor_id": "sap_vendor_id",
    "vendor_name": "vendor_name",
    "gstin": "gstin",
    "location": "location",
    "status": "is_active",
    "created_at": "created_at",
    "updated_at": "updated_at",
}
VENDOR_DUPLICATE_RACE = {
    "detail": ["SAP Vendor ID or GSTIN was just saved on another Vendor. Please re-check."]
}


class VendorViewSet(MasterAccessMixin, viewsets.ModelViewSet):
    access_submodule = "VENDOR"
    lookup_serializer_class = VendorLookupSerializer
    serializer_class = VendorSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    pagination_class = VendorPagination

    def get_queryset(self):
        from django.db.models import Q, Value
        from django.db.models.functions import Lower, Replace

        qs = Vendor.objects.select_related("created_by", "updated_by")
        params = self.request.query_params

        search = (params.get("search") or "").strip()
        if search:
            condition = (
                Q(erp_vendor_id__icontains=search)
                | Q(sap_vendor_id__icontains=search)
                | Q(vendor_name__icontains=search)
                | Q(gstin__icontains=search.replace(" ", ""))
                | Q(email__icontains=search)
                | Q(contact_no__icontains=search)
            )
            digits = "".join(ch for ch in search if ch.isdigit())
            if len(digits) >= 4:
                contact_digits = F("contact_no")
                for separator in (" ", "-", "(", ")", ".", "+"):
                    contact_digits = Replace(contact_digits, Value(separator), Value(""))
                qs = qs.annotate(contact_digits=contact_digits)
                condition |= Q(contact_digits__contains=digits)
            qs = qs.filter(condition)

        status_filter = (params.get("is_active") or "").strip().lower()
        if status_filter in {"true", "1"}:
            qs = qs.filter(is_active=True)
        elif status_filter in {"false", "0"}:
            qs = qs.filter(is_active=False)

        location = (params.get("location") or "").strip()
        if location:
            qs = qs.filter(location__iexact=location)

        ordering = (params.get("ordering") or "vendor_name").strip()
        descending = ordering.startswith("-")
        field = VENDOR_ORDERING_FIELDS.get(ordering.lstrip("-"), "vendor_name")
        order_expr = Lower(field) if field in {"vendor_name", "location"} else F(field)
        order_expr = order_expr.desc() if descending else order_expr.asc()
        return qs.order_by(order_expr, "id")

    def _user(self):
        return self.request.user if self.request.user.is_authenticated else None

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(created_by=self._user(), updated_by=self._user(), is_active=True)
        except IntegrityError as exc:
            raise ValidationError(VENDOR_DUPLICATE_RACE) from exc

    def perform_update(self, serializer):
        try:
            with transaction.atomic():
                serializer.save(updated_by=self._user())
        except IntegrityError as exc:
            raise ValidationError(VENDOR_DUPLICATE_RACE) from exc

    def _set_active(self, active: bool) -> Vendor:
        instance = self.get_object()
        instance.is_active = active
        instance.updated_by = self._user()
        instance.save(update_fields=["is_active", "updated_by", "updated_at"])
        return instance

    def destroy(self, request, *args, **kwargs):
        self._set_active(False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        instance = self._set_active(True)
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["get"], url_path="locations")
    def locations(self, request):
        """Distinct Locations (case-insensitive), for the Location filter."""
        seen: dict[str, str] = {}
        for value in (
            Vendor.objects.exclude(location="")
            .order_by("location")
            .values_list("location", flat=True)
            .distinct()
        ):
            seen.setdefault(value.casefold(), value)
        return Response(sorted(seen.values(), key=str.casefold))

    @action(detail=False, methods=["get"], url_path="template")
    def template(self, request):
        response = HttpResponse(
            build_vendor_template().getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="vendor_template.xlsx"'
        return response

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_vendor_template(upload)
            upload.seek(0)
            preview = preview_vendors_from_excel(upload)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": UNREADABLE_EXCEL_MESSAGE}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(preview)

    @action(detail=False, methods=["post"], url_path="import")
    def import_excel(self, request):
        upload, error = _read_upload(request)
        if error:
            return error
        try:
            upload.seek(0)
            validate_vendor_template(upload)
            upload.seek(0)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {"detail": UNREADABLE_EXCEL_MESSAGE}, status=status.HTTP_400_BAD_REQUEST
            )
        return _queue_import_job(
            request=request,
            upload=upload,
            master_type=ImportJob.MasterType.VENDOR,
        )

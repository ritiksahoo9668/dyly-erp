from django.contrib import admin

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


class NameMasterAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Vertical)
class VerticalAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "department")
    search_fields = ("name", "department__name")
    ordering = ("name",)
    autocomplete_fields = ("department",)


@admin.register(MaterialSubcategory)
class MaterialSubcategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "category__name")
    ordering = ("name",)
    autocomplete_fields = ("category",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "company")
    search_fields = ("name", "company__name")
    ordering = ("name",)
    autocomplete_fields = ("company",)


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "master_type",
        "status",
        "total_rows",
        "created_rows",
        "skipped_rows",
        "failed_rows",
        "progress_percentage",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("master_type", "status")
    search_fields = ("original_filename", "detail")
    ordering = ("-created_at",)


@admin.register(Uom)
class UomAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "symbol")
    ordering = ("name",)


@admin.register(QcParameter)
class QcParameterAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "unit", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "short_name")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "erp_vendor_id",
        "sap_vendor_id",
        "vendor_name",
        "gstin",
        "location",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("erp_vendor_id", "sap_vendor_id", "vendor_name", "gstin", "email")
    ordering = ("vendor_name",)
    readonly_fields = ("erp_vendor_id", "created_at", "updated_at", "created_by", "updated_by")


@admin.register(StockYard)
class StockYardAdmin(admin.ModelAdmin):
    list_display = ("name", "sap_storage_code", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "sap_storage_code")
    ordering = ("name",)


@admin.register(MaterialGroup)
class MaterialGroupAdmin(admin.ModelAdmin):
    list_display = (
        "sap_material_group_code",
        "name",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("sap_material_group_code", "name")
    ordering = ("sap_material_group_code",)


@admin.register(PurchasingGroup)
class PurchasingGroupAdmin(admin.ModelAdmin):
    list_display = (
        "sap_purchase_group_code",
        "name",
        "remarks",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("sap_purchase_group_code", "name", "remarks")
    ordering = ("sap_purchase_group_code",)


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("sap_plant_code", "name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("sap_plant_code", "name")
    ordering = ("sap_plant_code",)


@admin.register(MaterialType)
class MaterialTypeAdmin(admin.ModelAdmin):
    list_display = (
        "material_type_code",
        "erp_category_desc",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("material_type_code", "erp_category_desc")
    ordering = ("material_type_code",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "sap_code",
        "item_name",
        "material_category",
        "material_subcategory",
        "uom",
        "plant",
        "price",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "is_active",
        "material_category",
        "material_type",
        "plant",
        "department",
    )
    search_fields = ("sap_code", "item_name", "item_description", "hsn_sac_code")
    ordering = ("sap_code",)
    autocomplete_fields = (
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
    )


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "full_name",
        "department",
        "designation",
        "company",
        "unit",
        "mobile_number",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "gender", "company", "department", "designation")
    search_fields = (
        "employee_code",
        "full_name",
        "mobile_number",
        "personal_email",
        "company_email",
    )
    ordering = ("employee_code",)
    readonly_fields = ("employee_code", "created_at", "updated_at", "created_by", "updated_by")
    autocomplete_fields = (
        "department",
        "vertical",
        "designation",
        "company",
        "unit",
        "division",
        "facility",
    )


admin.site.register(Division, NameMasterAdmin)
admin.site.register(Department, NameMasterAdmin)
admin.site.register(Designation, NameMasterAdmin)
admin.site.register(Facility, NameMasterAdmin)
admin.site.register(Company, NameMasterAdmin)
admin.site.register(MaterialCategory, NameMasterAdmin)
admin.site.register(WeighBridge, NameMasterAdmin)

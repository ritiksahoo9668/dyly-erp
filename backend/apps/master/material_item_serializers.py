from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .material_images import resolve_display_image, resolve_display_thumb
from .models import (
    Department,
    Division,
    Material,
    MaterialCategory,
    MaterialGroup,
    MaterialSubcategory,
    MaterialType,
    Plant,
    PurchasingGroup,
    StockYard,
    Uom,
)


def _ref(obj, *, code_attr: str | None = None, name_attr: str = "name") -> dict | None:
    if obj is None:
        return None
    data = {"id": obj.pk, "name": getattr(obj, name_attr, "")}
    if code_attr:
        data["code"] = getattr(obj, code_attr, "")
    return data


class MaterialImageFieldsMixin(serializers.Serializer):
    display_image = serializers.SerializerMethodField()
    display_thumb = serializers.SerializerMethodField()
    item_image = serializers.CharField(source="image_url", read_only=True)

    def get_display_image(self, obj: Material) -> str | None:
        return resolve_display_image(obj, self.context.get("request"))

    def get_display_thumb(self, obj: Material) -> str | None:
        return resolve_display_thumb(obj, self.context.get("request"))


class MaterialListSerializer(MaterialImageFieldsMixin, serializers.ModelSerializer):
    material_category = serializers.SerializerMethodField()
    material_subcategory = serializers.SerializerMethodField()
    uom = serializers.SerializerMethodField()
    material_type = serializers.SerializerMethodField()
    material_group = serializers.SerializerMethodField()
    plant = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = (
            "id",
            "sap_code",
            "item_name",
            "item_image",
            "image_source",
            "display_image",
            "display_thumb",
            "material_category",
            "material_subcategory",
            "uom",
            "material_type",
            "material_group",
            "plant",
            "department",
            "price",
            "is_active",
            "created_at",
            "updated_at",
        )

    def get_material_category(self, obj: Material) -> dict | None:
        return _ref(obj.material_category)

    def get_material_subcategory(self, obj: Material) -> dict | None:
        return _ref(obj.material_subcategory)

    def get_uom(self, obj: Material) -> dict | None:
        if obj.uom_id is None:
            return None
        return {"id": obj.uom_id, "name": obj.uom.name, "symbol": obj.uom.symbol}

    def get_material_type(self, obj: Material) -> dict | None:
        return _ref(obj.material_type, code_attr="material_type_code", name_attr="erp_category_desc")

    def get_material_group(self, obj: Material) -> dict | None:
        return _ref(obj.material_group, code_attr="sap_material_group_code")

    def get_plant(self, obj: Material) -> dict | None:
        return _ref(obj.plant, code_attr="sap_plant_code")

    def get_department(self, obj: Material) -> dict | None:
        return _ref(obj.department)


class MaterialSerializer(MaterialImageFieldsMixin, serializers.ModelSerializer):
    division = serializers.SerializerMethodField()
    material_category = serializers.SerializerMethodField()
    material_subcategory = serializers.SerializerMethodField()
    uom = serializers.SerializerMethodField()
    stock_yard = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    plant = serializers.SerializerMethodField()
    material_group = serializers.SerializerMethodField()
    material_type = serializers.SerializerMethodField()
    purchasing_group = serializers.SerializerMethodField()
    division_id = serializers.PrimaryKeyRelatedField(
        source="division",
        queryset=Division.objects.all(),
        allow_null=True,
        required=False,
        write_only=True,
    )
    material_category_id = serializers.PrimaryKeyRelatedField(
        source="material_category",
        queryset=MaterialCategory.objects.all(),
        write_only=True,
    )
    material_subcategory_id = serializers.PrimaryKeyRelatedField(
        source="material_subcategory",
        queryset=MaterialSubcategory.objects.all(),
        write_only=True,
    )
    uom_id = serializers.PrimaryKeyRelatedField(
        source="uom",
        queryset=Uom.objects.all(),
        write_only=True,
    )
    stock_yard_id = serializers.PrimaryKeyRelatedField(
        source="stock_yard",
        queryset=StockYard.objects.all(),
        write_only=True,
    )
    department_id = serializers.PrimaryKeyRelatedField(
        source="department",
        queryset=Department.objects.all(),
        write_only=True,
    )
    plant_id = serializers.PrimaryKeyRelatedField(
        source="plant",
        queryset=Plant.objects.all(),
        write_only=True,
    )
    material_group_id = serializers.PrimaryKeyRelatedField(
        source="material_group",
        queryset=MaterialGroup.objects.all(),
        write_only=True,
    )
    material_type_id = serializers.PrimaryKeyRelatedField(
        source="material_type",
        queryset=MaterialType.objects.all(),
        write_only=True,
    )
    purchasing_group_id = serializers.PrimaryKeyRelatedField(
        source="purchasing_group",
        queryset=PurchasingGroup.objects.all(),
        write_only=True,
    )

    class Meta:
        model = Material
        fields = (
            "id",
            "item_name",
            "item_description",
            "descriptive_spec",
            "technical_spec",
            "document_type",
            "store_code",
            "division",
            "division_id",
            "material_category",
            "material_category_id",
            "material_subcategory",
            "material_subcategory_id",
            "uom",
            "uom_id",
            "stock_yard",
            "stock_yard_id",
            "department",
            "department_id",
            "hsn_sac_code",
            "gst_percent",
            "price",
            "sap_code",
            "plant",
            "plant_id",
            "material_group",
            "material_group_id",
            "material_type",
            "material_type_id",
            "purchasing_group",
            "purchasing_group_id",
            "item_image",
            "image_source",
            "image_url",
            "display_image",
            "display_thumb",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )
        read_only_fields = (
            "id",
            "image_source",
            "image_url",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
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

    def get_division(self, obj: Material) -> dict | None:
        return _ref(obj.division)

    def get_material_category(self, obj: Material) -> dict | None:
        return _ref(obj.material_category)

    def get_material_subcategory(self, obj: Material) -> dict | None:
        return _ref(obj.material_subcategory)

    def get_uom(self, obj: Material) -> dict | None:
        if obj.uom_id is None:
            return None
        return {"id": obj.uom_id, "name": obj.uom.name, "symbol": obj.uom.symbol}

    def get_stock_yard(self, obj: Material) -> dict | None:
        if obj.stock_yard_id is None:
            return None
        return {
            "id": obj.stock_yard_id,
            "name": obj.stock_yard.name,
            "code": obj.stock_yard.sap_storage_code,
        }

    def get_department(self, obj: Material) -> dict | None:
        return _ref(obj.department)

    def get_plant(self, obj: Material) -> dict | None:
        return _ref(obj.plant, code_attr="sap_plant_code")

    def get_material_group(self, obj: Material) -> dict | None:
        return _ref(obj.material_group, code_attr="sap_material_group_code")

    def get_material_type(self, obj: Material) -> dict | None:
        return _ref(obj.material_type, code_attr="material_type_code", name_attr="erp_category_desc")

    def get_purchasing_group(self, obj: Material) -> dict | None:
        return _ref(obj.purchasing_group, code_attr="sap_purchase_group_code")

    def validate_item_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Item name is required.")
        if len(cleaned) > 255:
            raise serializers.ValidationError("Item name must be 255 characters or fewer.")
        return cleaned

    def validate_item_description(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Item Description is required.")
        return cleaned

    def validate_descriptive_spec(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Descriptive Spec is required.")
        return cleaned

    def validate_technical_spec(self, value: str) -> str:
        return (value or "").strip()

    def validate_document_type(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Document Type is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError("Document Type must be 50 characters or fewer.")
        return cleaned

    def validate_store_code(self, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Store Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError("Store Code must be 50 characters or fewer.")
        return cleaned

    def validate_hsn_sac_code(self, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("HSN/SAC Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError("HSN/SAC Code must be 50 characters or fewer.")
        return cleaned

    def validate_sap_code(self, value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("SAP Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError("SAP Code must be 50 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if Material.sap_code_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A Material with this SAP Code already exists.")
        return cleaned

    def validate_gst_percent(self, value) -> Decimal:
        try:
            amount = Decimal(str(value).strip())
        except (InvalidOperation, AttributeError, TypeError) as exc:
            raise serializers.ValidationError("GST % must be a valid number.") from exc
        if amount < 0:
            raise serializers.ValidationError("GST % cannot be negative.")
        return amount

    def validate_price(self, value) -> Decimal:
        try:
            amount = Decimal(str(value).strip())
        except (InvalidOperation, AttributeError, TypeError) as exc:
            raise serializers.ValidationError("Price must be a valid number.") from exc
        if amount < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return amount

    def validate(self, attrs):
        category = attrs.get("material_category")
        subcategory = attrs.get("material_subcategory")
        if category is None and self.instance is not None:
            category = self.instance.material_category
        if subcategory is None and self.instance is not None:
            subcategory = self.instance.material_subcategory
        if category is not None and subcategory is not None:
            if subcategory.category_id != category.pk:
                raise serializers.ValidationError(
                    {
                        "material_subcategory_id": (
                            "Material Sub Category must belong to the selected Material Category."
                        )
                    }
                )

        stock_yard = attrs.get("stock_yard")
        store_code = attrs.get("store_code")
        if store_code is None and self.instance is not None:
            store_code = self.instance.store_code
        if stock_yard is None and self.instance is not None:
            stock_yard = self.instance.stock_yard
        if stock_yard is not None and store_code:
            if stock_yard.sap_storage_code.casefold() != str(store_code).strip().casefold():
                raise serializers.ValidationError(
                    {
                        "store_code": (
                            "Store Code must match the selected Stock Yard storage code."
                        )
                    }
                )
        return attrs


class MaterialWriteSerializer(MaterialSerializer):
    class Meta(MaterialSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "technical_spec": {"required": False, "allow_blank": True},
            "division_id": {"required": False, "allow_null": True},
            "material_category_id": {"required": True},
            "material_subcategory_id": {"required": True},
            "uom_id": {"required": True},
            "stock_yard_id": {"required": True},
            "department_id": {"required": True},
            "plant_id": {"required": True},
            "material_group_id": {"required": True},
            "material_type_id": {"required": True},
            "purchasing_group_id": {"required": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            for key in (
                "material_category_id",
                "material_subcategory_id",
                "uom_id",
                "stock_yard_id",
                "department_id",
                "plant_id",
                "material_group_id",
                "material_type_id",
                "purchasing_group_id",
            ):
                self.fields[key].required = False

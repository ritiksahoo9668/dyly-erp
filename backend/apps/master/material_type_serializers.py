from rest_framework import serializers

from .models import MaterialType


class MaterialTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialType
        fields = (
            "id",
            "material_type_code",
            "erp_category_desc",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_material_type_code(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Material Type Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError(
                "Material Type Code must be 50 characters or fewer."
            )
        exclude_pk = self.instance.pk if self.instance else None
        if MaterialType.code_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError(
                "A Material Type with this code already exists."
            )
        return cleaned

    def validate_erp_category_desc(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("ERP Category Desc is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError(
                "ERP Category Desc must be 150 characters or fewer."
            )
        return cleaned


class MaterialTypeWriteSerializer(MaterialTypeSerializer):
    class Meta(MaterialTypeSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "material_type_code": {"required": True},
            "erp_category_desc": {"required": True},
        }

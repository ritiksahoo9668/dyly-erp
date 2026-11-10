from rest_framework import serializers

from .models import MaterialGroup


class MaterialGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialGroup
        fields = (
            "id",
            "sap_material_group_code",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_sap_material_group_code(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("SAP Material Group Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError(
                "SAP Material Group Code must be 50 characters or fewer."
            )
        exclude_pk = self.instance.pk if self.instance else None
        if MaterialGroup.sap_code_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError(
                "A Material Group with this SAP Material Group Code already exists."
            )
        return cleaned

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Group Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Group Name must be 150 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if MaterialGroup.name_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A Material Group with this name already exists.")
        return cleaned


class MaterialGroupWriteSerializer(MaterialGroupSerializer):
    class Meta(MaterialGroupSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "sap_material_group_code": {"required": True},
            "name": {"required": True},
        }

from rest_framework import serializers

from .models import Plant


class PlantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plant
        fields = (
            "id",
            "sap_plant_code",
            "name",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_sap_plant_code(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("SAP Plant Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError("SAP Plant Code must be 50 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if Plant.sap_code_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError(
                "A Plant with this SAP Plant Code already exists."
            )
        return cleaned

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Plant Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Plant Name must be 150 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if Plant.name_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A Plant with this name already exists.")
        return cleaned


class PlantWriteSerializer(PlantSerializer):
    class Meta(PlantSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "sap_plant_code": {"required": True},
            "name": {"required": True},
        }

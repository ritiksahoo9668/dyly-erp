from rest_framework import serializers

from .models import Uom


class UomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Uom
        fields = (
            "id",
            "name",
            "symbol",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("UOM Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("UOM Name must be 150 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if Uom.name_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A UOM with this name already exists.")
        return cleaned

    def validate_symbol(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("UOM Symbol is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError("UOM Symbol must be 50 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if Uom.symbol_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A UOM with this symbol already exists.")
        return cleaned


class UomWriteSerializer(UomSerializer):
    class Meta(UomSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "name": {"required": True},
            "symbol": {"required": True},
        }

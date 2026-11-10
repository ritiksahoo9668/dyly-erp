from rest_framework import serializers

from .models import StockYard


class StockYardSerializer(serializers.ModelSerializer):
    # Keep API key `storage_code` for the frontend; maps to model `sap_storage_code`.
    storage_code = serializers.CharField(source="sap_storage_code", max_length=50)

    class Meta:
        model = StockYard
        fields = (
            "id",
            "name",
            "storage_code",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Stock Yard Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Stock Yard Name must be 150 characters or fewer.")
        # Name may repeat across storage locations; Storage Code is the unique key.
        return cleaned

    def validate_storage_code(self, value: str) -> str:
        cleaned = (value or "").strip().upper()
        if not cleaned:
            raise serializers.ValidationError("Storage Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError("Storage Code must be 50 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if StockYard.sap_storage_code_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A Stock Yard with this Storage Code already exists.")
        return cleaned


class StockYardWriteSerializer(StockYardSerializer):
    class Meta(StockYardSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "name": {"required": True},
            "storage_code": {"required": True},
        }

from rest_framework import serializers

from .models import PurchasingGroup


class PurchasingGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchasingGroup
        fields = (
            "id",
            "sap_purchase_group_code",
            "name",
            "remarks",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_sap_purchase_group_code(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("SAP Purchase Group Code is required.")
        if len(cleaned) > 50:
            raise serializers.ValidationError(
                "SAP Purchase Group Code must be 50 characters or fewer."
            )
        exclude_pk = self.instance.pk if self.instance else None
        if PurchasingGroup.sap_code_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError(
                "A Purchasing Group with this SAP Purchase Group Code already exists."
            )
        return cleaned

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Purchase Group Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError(
                "Purchase Group Name must be 150 characters or fewer."
            )
        exclude_pk = self.instance.pk if self.instance else None
        if PurchasingGroup.name_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError(
                "A Purchasing Group with this name already exists."
            )
        return cleaned

    def validate_remarks(self, value: str) -> str:
        cleaned = (value or "").strip()
        if len(cleaned) > 255:
            raise serializers.ValidationError("Remarks must be 255 characters or fewer.")
        return cleaned


class PurchasingGroupWriteSerializer(PurchasingGroupSerializer):
    class Meta(PurchasingGroupSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "sap_purchase_group_code": {"required": True},
            "name": {"required": True},
            "remarks": {"required": False, "allow_blank": True},
        }

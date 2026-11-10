from rest_framework import serializers


def make_name_master_serializers(model_cls, *, label: str):
    """Build read/write serializers for a simple name-based master model."""

    class NameMasterSerializer(serializers.ModelSerializer):
        class Meta:
            fields = ("id", "name", "is_active", "created_at", "updated_at")
            read_only_fields = ("id", "created_at", "updated_at")

        def validate_name(self, value: str) -> str:
            cleaned = (value or "").strip()
            if not cleaned:
                raise serializers.ValidationError(f"{label} is required.")
            if len(cleaned) > 150:
                raise serializers.ValidationError(f"{label} must be 150 characters or fewer.")

            exclude_pk = self.instance.pk if self.instance else None
            if model_cls.name_exists(cleaned, exclude_pk=exclude_pk):
                raise serializers.ValidationError(
                    f"A record with this {label.lower()} already exists."
                )
            return cleaned

    NameMasterSerializer.Meta.model = model_cls

    class NameMasterWriteSerializer(NameMasterSerializer):
        class Meta(NameMasterSerializer.Meta):
            extra_kwargs = {
                "is_active": {"required": False},
            }

    NameMasterWriteSerializer.Meta.model = model_cls
    NameMasterSerializer.__name__ = f"{model_cls.__name__}Serializer"
    NameMasterWriteSerializer.__name__ = f"{model_cls.__name__}WriteSerializer"
    return NameMasterSerializer, NameMasterWriteSerializer

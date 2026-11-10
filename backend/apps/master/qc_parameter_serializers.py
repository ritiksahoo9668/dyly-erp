from rest_framework import serializers

from .models import QcParameter
from .qc_parameter_rules import (
    NAME_EXISTS,
    NAME_REQUIRED,
    SHORT_NAME_EXISTS,
    SHORT_NAME_REQUIRED,
    clean_qc_text,
    length_error,
    name_taken,
    normalize_short_name,
    short_name_taken,
)


def _user_ref(user) -> dict | None:
    if user is None:
        return None
    return {"id": user.pk, "name": user.display_name, "email": user.email}


class QcParameterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        trim_whitespace=False,
        error_messages={"required": NAME_REQUIRED, "blank": NAME_REQUIRED, "null": NAME_REQUIRED},
    )
    short_name = serializers.CharField(
        trim_whitespace=False,
        error_messages={
            "required": SHORT_NAME_REQUIRED,
            "blank": SHORT_NAME_REQUIRED,
            "null": SHORT_NAME_REQUIRED,
        },
    )
    unit = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, trim_whitespace=False, default=""
    )
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    class Meta:
        model = QcParameter
        fields = (
            "id",
            "name",
            "short_name",
            "unit",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )
        read_only_fields = ("id", "is_active", "created_at", "updated_at")

    def get_created_by(self, obj):
        return _user_ref(obj.created_by)

    def get_updated_by(self, obj):
        return _user_ref(obj.updated_by)

    def _exclude_pk(self):
        return self.instance.pk if self.instance is not None else None

    def validate_name(self, value) -> str:
        name = clean_qc_text(value)
        if not name:
            raise serializers.ValidationError(NAME_REQUIRED)
        error = length_error("QC Parameter Name", name, QcParameter.NAME_MAX_LENGTH)
        if error:
            raise serializers.ValidationError(error)
        if name_taken(name, exclude_pk=self._exclude_pk()):
            raise serializers.ValidationError(NAME_EXISTS)
        return name

    def validate_short_name(self, value) -> str:
        short_name = normalize_short_name(value)
        if not short_name:
            raise serializers.ValidationError(SHORT_NAME_REQUIRED)
        error = length_error("Short Name", short_name, QcParameter.SHORT_NAME_MAX_LENGTH)
        if error:
            raise serializers.ValidationError(error)
        if short_name_taken(short_name, exclude_pk=self._exclude_pk()):
            raise serializers.ValidationError(SHORT_NAME_EXISTS)
        return short_name

    def validate_unit(self, value) -> str:
        unit = clean_qc_text(value)
        error = length_error("Unit", unit, QcParameter.UNIT_MAX_LENGTH)
        if error:
            raise serializers.ValidationError(error)
        return unit

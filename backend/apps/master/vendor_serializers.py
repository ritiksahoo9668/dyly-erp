from rest_framework import serializers

from .models import Vendor
from .vendor_rules import (
    VENDOR_NAME_REQUIRED,
    clean_vendor_text,
    gstin_owner,
    gstin_taken_message,
    length_error,
    normalize_contact,
    normalize_email,
    normalize_gstin,
    normalize_sap_vendor_id,
    sap_id_exists_message,
    sap_id_owner,
)


def _user_ref(user) -> dict | None:
    if user is None:
        return None
    return {"id": user.pk, "name": user.display_name, "email": user.email}


def _optional_text():
    return serializers.CharField(
        required=False, allow_blank=True, allow_null=True, trim_whitespace=False, default=""
    )


class VendorSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(
        trim_whitespace=False,
        error_messages={
            "required": VENDOR_NAME_REQUIRED,
            "blank": VENDOR_NAME_REQUIRED,
            "null": VENDOR_NAME_REQUIRED,
        },
    )
    sap_vendor_id = _optional_text()
    email = _optional_text()
    contact_no = _optional_text()
    gstin = _optional_text()
    location = _optional_text()
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    class Meta:
        model = Vendor
        fields = (
            "id",
            "erp_vendor_id",
            "sap_vendor_id",
            "vendor_name",
            "email",
            "contact_no",
            "gstin",
            "location",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )
        read_only_fields = ("id", "erp_vendor_id", "is_active", "created_at", "updated_at")

    def get_created_by(self, obj):
        return _user_ref(obj.created_by)

    def get_updated_by(self, obj):
        return _user_ref(obj.updated_by)

    def _exclude_pk(self):
        return self.instance.pk if self.instance is not None else None

    @staticmethod
    def _check_length(label: str, value: str, limit: int) -> str:
        error = length_error(label, value, limit)
        if error:
            raise serializers.ValidationError(error)
        return value

    def validate_vendor_name(self, value) -> str:
        name = clean_vendor_text(value)
        if not name:
            raise serializers.ValidationError(VENDOR_NAME_REQUIRED)
        return self._check_length("Vendor Name", name, Vendor.VENDOR_NAME_MAX_LENGTH)

    def validate_sap_vendor_id(self, value) -> str:
        sap_id = normalize_sap_vendor_id(value)
        if not sap_id:
            return ""
        self._check_length("SAP Vendor ID", sap_id, Vendor.SAP_VENDOR_ID_MAX_LENGTH)
        owner = sap_id_owner(sap_id, exclude_pk=self._exclude_pk())
        if owner is not None:
            raise serializers.ValidationError(sap_id_exists_message(sap_id, owner))
        return sap_id

    def validate_email(self, value) -> str:
        email, error = normalize_email(value)
        if error:
            raise serializers.ValidationError(error)
        return email

    def validate_contact_no(self, value) -> str:
        contact, error = normalize_contact(value)
        if error:
            raise serializers.ValidationError(error)
        return contact

    def validate_gstin(self, value) -> str:
        gstin, error = normalize_gstin(value)
        if error:
            raise serializers.ValidationError(error)
        if gstin:
            owner = gstin_owner(gstin, exclude_pk=self._exclude_pk())
            if owner is not None:
                raise serializers.ValidationError(gstin_taken_message(owner))
        return gstin

    def validate_location(self, value) -> str:
        location = clean_vendor_text(value)
        return self._check_length("Location", location, Vendor.LOCATION_MAX_LENGTH)

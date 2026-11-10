from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.common.access_control.selectors import access_payload

from .permissions import assignable_roles, can_manage_users

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password(attrs["password"])
        return attrs


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    can_manage_users = serializers.SerializerMethodField()
    assignable_roles = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "initials",
            "role",
            "role_label",
            "is_staff",
            "is_superuser",
            "can_manage_users",
            "assignable_roles",
            "access",
        )
        read_only_fields = fields

    def get_can_manage_users(self, obj) -> bool:
        return can_manage_users(obj)

    def get_assignable_roles(self, obj) -> list[str]:
        return assignable_roles(obj)

    def get_access(self, obj) -> dict:
        return access_payload(obj)

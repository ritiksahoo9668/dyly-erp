from rest_framework import serializers

from apps.common.access_control.services import onboarding_access
from apps.master.models import Employee

from .models import User, UserAccessEvent, UserOnboarding
from .onboarding import onboarding_actions, user_actions

EVENTS_IN_DETAIL = 100


def _ref(obj) -> dict | None:
    if obj is None:
        return None
    return {"id": obj.pk, "name": obj.name, "is_active": obj.is_active}


def _person(user) -> dict | None:
    if user is None:
        return None
    return {"id": user.pk, "name": user.display_name, "email": user.email}


def _request_user(serializer):
    request = serializer.context.get("request")
    return getattr(request, "user", None)


def linked_onboarding(user: User) -> UserOnboarding | None:
    try:
        return user.onboarding
    except UserOnboarding.DoesNotExist:
        return None


class OnboardingEmployeeSerializer(serializers.ModelSerializer):
    """Read-only Employee Master snapshot; Employee data stays owned by Employee Master."""

    department = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "employee_code",
            "full_name",
            "department",
            "designation",
            "company",
            "unit",
            "company_email",
            "personal_email",
            "is_active",
        )
        read_only_fields = fields

    def get_department(self, obj):
        return _ref(obj.department)

    def get_designation(self, obj):
        return _ref(obj.designation)

    def get_company(self, obj):
        return _ref(obj.company)

    def get_unit(self, obj):
        return _ref(obj.unit)


class UserOnboardingSerializer(serializers.ModelSerializer):
    employee = OnboardingEmployeeSerializer(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    user = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    class Meta:
        model = UserOnboarding
        fields = (
            "id",
            "onboarding_code",
            "employee",
            "login_email",
            "role",
            "role_label",
            "status",
            "status_label",
            "last_mail_status",
            "user",
            "invite_sent_at",
            "last_invite_sent_at",
            "invite_expires_at",
            "activated_at",
            "revoked_at",
            "invite_send_count",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "allowed_actions",
        )
        read_only_fields = fields

    def get_user(self, obj):
        user = obj.user
        if user is None:
            return None
        return {"id": user.pk, "is_active": user.is_active, "last_login": user.last_login}

    def get_created_by(self, obj):
        return _person(obj.created_by)

    def get_updated_by(self, obj):
        return _person(obj.updated_by)

    def get_allowed_actions(self, obj):
        return onboarding_actions(obj, _request_user(self))


class UserAccessEventSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="get_event_display", read_only=True)
    actor = serializers.SerializerMethodField()

    class Meta:
        model = UserAccessEvent
        fields = (
            "id",
            "event",
            "event_label",
            "actor",
            "permission",
            "from_value",
            "to_value",
            "created_at",
        )
        read_only_fields = fields

    def get_actor(self, obj):
        return _person(obj.actor)


class UserOnboardingDetailSerializer(UserOnboardingSerializer):
    events = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()

    class Meta(UserOnboardingSerializer.Meta):
        fields = (*UserOnboardingSerializer.Meta.fields, "access", "events")
        read_only_fields = fields

    def get_events(self, obj):
        events = obj.events.select_related("actor")[:EVENTS_IN_DETAIL]
        return UserAccessEventSerializer(events, many=True).data

    def get_access(self, obj):
        return onboarding_access(obj)


class UserOnboardingWriteSerializer(serializers.Serializer):
    """Accepted input for create / draft edit. Status is never writable."""

    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.select_related("department", "designation", "company", "unit"),
        source="employee",
    )
    login_email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=User.Role.choices)
    # Module access in the canonical shape; validated against the registry by the service layer.
    access = serializers.JSONField(required=False)
    send_invite = serializers.BooleanField(required=False, default=False)

    def validate_login_email(self, value: str) -> str:
        return value.strip().lower()


class ErpUserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    employee = serializers.SerializerMethodField()
    onboarding = serializers.SerializerMethodField()
    allowed_actions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "display_name",
            "role",
            "role_label",
            "is_active",
            "last_login",
            "date_joined",
            "employee",
            "onboarding",
            "allowed_actions",
        )
        read_only_fields = fields

    def get_employee(self, obj):
        onboarding = linked_onboarding(obj)
        if onboarding is None:
            return None
        employee = onboarding.employee
        return {
            "id": employee.pk,
            "employee_code": employee.employee_code,
            "full_name": employee.full_name,
            "department": _ref(employee.department),
        }

    def get_onboarding(self, obj):
        onboarding = linked_onboarding(obj)
        if onboarding is None:
            return None
        return {
            "id": onboarding.pk,
            "onboarding_code": onboarding.onboarding_code,
            "status": onboarding.status,
            "status_label": onboarding.get_status_display(),
        }

    def get_allowed_actions(self, obj):
        return user_actions(obj, _request_user(self), linked_onboarding(obj))


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices)


class UserAccessWriteSerializer(serializers.Serializer):
    access = serializers.JSONField()


class ActivationTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=256, trim_whitespace=True)


class ActivateAccountSerializer(ActivationTokenSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

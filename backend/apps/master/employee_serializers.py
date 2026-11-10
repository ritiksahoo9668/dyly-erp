from rest_framework import serializers

from .employee_rules import (
    GENDER_CHOICES_TEXT,
    describe_employee,
    find_mobile_owner,
    find_personal_email_matches,
    normalize_email,
    normalize_gender,
    normalize_mobile,
)
from .models import (
    Company,
    Department,
    Designation,
    Division,
    Employee,
    Facility,
    Vertical,
)


def _ref(obj) -> dict | None:
    if obj is None:
        return None
    return {"id": obj.pk, "name": obj.name, "is_active": obj.is_active}


def _user_ref(user) -> dict | None:
    if user is None:
        return None
    return {"id": user.pk, "name": user.display_name, "email": user.email}


class EmployeeListSerializer(serializers.ModelSerializer):
    department = serializers.SerializerMethodField()
    designation = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()
    division = serializers.SerializerMethodField()
    facility = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "employee_code",
            "full_name",
            "department",
            "designation",
            "company",
            "division",
            "facility",
            "mobile_number",
            "personal_email",
            "company_email",
            "date_of_joining",
            "gender",
            "is_active",
            "updated_at",
        )

    def get_department(self, obj):
        return _ref(obj.department)

    def get_designation(self, obj):
        return _ref(obj.designation)

    def get_company(self, obj):
        return _ref(obj.company)

    def get_division(self, obj):
        return _ref(obj.division)

    def get_facility(self, obj):
        return _ref(obj.facility)


class EmployeeSerializer(EmployeeListSerializer):
    vertical = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    department_id = serializers.PrimaryKeyRelatedField(
        source="department",
        queryset=Department.objects.all(),
        write_only=True,
        error_messages={
            "required": "Department is required.",
            "null": "Department is required.",
            "does_not_exist": "Selected Department does not exist.",
        },
    )
    vertical_id = serializers.PrimaryKeyRelatedField(
        source="vertical",
        queryset=Vertical.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "Selected Vertical does not exist."},
    )
    designation_id = serializers.PrimaryKeyRelatedField(
        source="designation",
        queryset=Designation.objects.all(),
        write_only=True,
        error_messages={
            "required": "Designation is required.",
            "null": "Designation is required.",
            "does_not_exist": "Selected Designation does not exist.",
        },
    )
    company_id = serializers.PrimaryKeyRelatedField(
        source="company",
        queryset=Company.objects.all(),
        write_only=True,
        error_messages={
            "required": "Company is required.",
            "null": "Company is required.",
            "does_not_exist": "Selected Company does not exist.",
        },
    )
    division_id = serializers.PrimaryKeyRelatedField(
        source="division",
        queryset=Division.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "Selected Division does not exist."},
    )
    facility_id = serializers.PrimaryKeyRelatedField(
        source="facility",
        queryset=Facility.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "Selected Facility does not exist."},
    )

    full_name = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        error_messages={"required": "Full Name is required.", "blank": "Full Name is required."},
    )
    location = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
        error_messages={"required": "Location is required.", "blank": "Location is required."},
    )
    gender = serializers.CharField(
        error_messages={"required": "Gender is required.", "blank": "Gender is required."},
    )
    mobile_number = serializers.CharField(
        trim_whitespace=True,
        error_messages={
            "required": "Mobile Number is required.",
            "blank": "Mobile Number is required.",
        },
    )
    personal_email = serializers.CharField(required=False, allow_blank=True, default="")
    company_email = serializers.CharField(required=False, allow_blank=True, default="")
    date_of_joining = serializers.DateField(
        error_messages={
            "required": "Date Of Joining is required.",
            "null": "Date Of Joining is required.",
            "invalid": "Invalid Date Of Joining.",
        },
    )
    confirm_possible_duplicate = serializers.BooleanField(
        write_only=True, required=False, default=False
    )

    class Meta(EmployeeListSerializer.Meta):
        fields = (
            "id",
            "employee_code",
            "full_name",
            "gender",
            "mobile_number",
            "personal_email",
            "date_of_joining",
            "location",
            "department",
            "department_id",
            "vertical",
            "vertical_id",
            "designation",
            "designation_id",
            "company",
            "company_id",
            "division",
            "division_id",
            "facility",
            "facility_id",
            "company_email",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "confirm_possible_duplicate",
        )
        read_only_fields = ("id", "employee_code", "created_at", "updated_at")
        extra_kwargs = {"is_active": {"required": False}}

    def get_vertical(self, obj):
        return _ref(obj.vertical)

    def get_created_by(self, obj):
        return _user_ref(obj.created_by)

    def get_updated_by(self, obj):
        return _user_ref(obj.updated_by)

    def validate_gender(self, value: str) -> str:
        gender = normalize_gender(value)
        if gender is None:
            raise serializers.ValidationError(f"Gender must be one of: {GENDER_CHOICES_TEXT}.")
        return gender

    def validate_mobile_number(self, value: str) -> str:
        mobile, error = normalize_mobile(value)
        if error:
            raise serializers.ValidationError(error)
        owner = find_mobile_owner(mobile, exclude_pk=self.instance.pk if self.instance else None)
        if owner is not None:
            raise serializers.ValidationError(
                f"Mobile Number already belongs to {describe_employee(owner)}."
            )
        return mobile

    def validate_personal_email(self, value: str) -> str:
        email, error = normalize_email(value, label="Personal Email")
        if error:
            raise serializers.ValidationError(error)
        return email

    def validate_company_email(self, value: str) -> str:
        email, error = normalize_email(value, label="Company Email")
        if error:
            raise serializers.ValidationError(error)
        return email

    def _current(self, attrs: dict, field: str):
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None) if self.instance is not None else None

    def validate(self, attrs):
        errors: dict[str, str] = {}

        for field, label in (
            ("department", "Department"),
            ("vertical", "Vertical"),
            ("designation", "Designation"),
            ("company", "Company"),
            ("division", "Division"),
            ("facility", "Facility"),
        ):
            selected = attrs.get(field)
            unchanged = (
                self.instance is not None
                and selected is not None
                and getattr(self.instance, f"{field}_id") == selected.pk
            )
            if selected is not None and not selected.is_active and not unchanged:
                errors[f"{field}_id"] = f"Selected {label} is inactive."

        company = attrs.get("company")
        stored_unit = self.instance.unit if self.instance is not None else None
        if company is not None and stored_unit is not None and stored_unit.company_id != company.pk:
            attrs["unit"] = None

        department = self._current(attrs, "department")
        vertical = self._current(attrs, "vertical")
        if department is not None and vertical is not None:
            if vertical.department_id != department.pk:
                errors["vertical_id"] = (
                    f'Vertical "{vertical.name}" does not belong to Department '
                    f'"{department.name}".'
                )

        if errors:
            raise serializers.ValidationError(errors)

        confirmed = attrs.pop("confirm_possible_duplicate", False)
        email = attrs.get("personal_email")
        email_changed = self.instance is None or email != self.instance.personal_email
        if email and email_changed and not confirmed:
            matches = find_personal_email_matches(
                email, exclude_pk=self.instance.pk if self.instance else None
            )
            if matches:
                names = ", ".join(describe_employee(match) for match in matches)
                raise serializers.ValidationError(
                    {
                        "personal_email": (
                            f"Possible duplicate: Personal Email is already used by {names}."
                        ),
                        "possible_duplicate": [match.employee_code for match in matches],
                    }
                )
        return attrs

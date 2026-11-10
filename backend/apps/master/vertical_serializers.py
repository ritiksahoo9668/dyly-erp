from rest_framework import serializers

from .models import Department, Vertical


class VerticalSerializer(serializers.ModelSerializer):
    department_id = serializers.PrimaryKeyRelatedField(
        source="department",
        queryset=Department.objects.all(),
        write_only=True,
    )
    department = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vertical
        fields = (
            "id",
            "name",
            "department",
            "department_id",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "department")

    def get_department(self, obj: Vertical) -> dict:
        return {
            "id": obj.department_id,
            "name": obj.department.name,
            "is_active": obj.department.is_active,
        }

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Vertical Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Vertical Name must be 150 characters or fewer.")
        exclude_pk = self.instance.pk if self.instance else None
        if Vertical.name_exists(cleaned, exclude_pk=exclude_pk):
            raise serializers.ValidationError("A vertical with this name already exists.")
        return cleaned

    def validate_department_id(self, department: Department) -> Department:
        if department is None:
            raise serializers.ValidationError("Department is required.")
        return department

    def validate(self, attrs):
        if self.instance is None and "department" not in attrs:
            raise serializers.ValidationError({"department_id": "Department is required."})
        return attrs


class VerticalWriteSerializer(VerticalSerializer):
    class Meta(VerticalSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "department_id": {"required": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["department_id"].required = False

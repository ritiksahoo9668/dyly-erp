from rest_framework import serializers

from .models import Company, Unit


class UnitSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        source="company",
        queryset=Company.objects.all(),
        write_only=True,
        error_messages={
            "required": "Company is required.",
            "null": "Company is required.",
            "does_not_exist": "Selected company does not exist.",
        },
    )
    company = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Unit
        fields = (
            "id",
            "name",
            "company",
            "company_id",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "company")

    def get_company(self, obj: Unit) -> dict:
        return {
            "id": obj.company_id,
            "name": obj.company.name,
            "is_active": obj.company.is_active,
        }

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Unit Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Unit Name must be 150 characters or fewer.")
        return cleaned

    def validate(self, attrs):
        name = attrs.get("name")
        if name is None and self.instance is not None:
            name = self.instance.name
        company = attrs.get("company")
        if company is None and self.instance is not None:
            company = self.instance.company
        if company is None:
            raise serializers.ValidationError({"company_id": "Company is required."})
        if name:
            exclude_pk = self.instance.pk if self.instance else None
            if Unit.name_exists_in_company(name, company.pk, exclude_pk=exclude_pk):
                raise serializers.ValidationError(
                    {"name": "A unit with this name already exists in this company."}
                )
        return attrs


class UnitWriteSerializer(UnitSerializer):
    class Meta(UnitSerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["company_id"].required = False

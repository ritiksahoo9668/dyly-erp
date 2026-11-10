from rest_framework import serializers

from .models import Company
from .serializers import make_name_master_serializers

_CompanyBaseSerializer, CompanyWriteSerializer = make_name_master_serializers(
    Company, label="Company Name"
)


class CompanySerializer(_CompanyBaseSerializer):
    """Company with its Units, derived from Unit.company_id (never stored on Company)."""

    units = serializers.SerializerMethodField()

    class Meta(_CompanyBaseSerializer.Meta):
        fields = (*_CompanyBaseSerializer.Meta.fields, "units")

    def get_units(self, obj: Company) -> list[dict]:
        return [
            {"id": unit.id, "name": unit.name, "is_active": unit.is_active}
            for unit in obj.units.all()
        ]

from rest_framework import serializers

from .models import MaterialCategory, MaterialSubcategory


class MaterialSubcategorySerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=MaterialCategory.objects.all(),
        write_only=True,
    )
    category = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MaterialSubcategory
        fields = (
            "id",
            "name",
            "category",
            "category_id",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "category")

    def get_category(self, obj: MaterialSubcategory) -> dict:
        return {
            "id": obj.category_id,
            "name": obj.category.name,
            "is_active": obj.category.is_active,
        }

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Subcategory Name is required.")
        if len(cleaned) > 150:
            raise serializers.ValidationError("Subcategory Name must be 150 characters or fewer.")
        return cleaned

    def validate(self, attrs):
        name = attrs.get("name")
        if name is None and self.instance is not None:
            name = self.instance.name
        category = attrs.get("category")
        if category is None and self.instance is not None:
            category = self.instance.category
        if self.instance is None and category is None:
            raise serializers.ValidationError({"category_id": "Material Category is required."})
        if name and category is not None:
            exclude_pk = self.instance.pk if self.instance else None
            if MaterialSubcategory.name_exists_in_category(
                name,
                category.pk,
                exclude_pk=exclude_pk,
            ):
                raise serializers.ValidationError(
                    {"name": "A subcategory with this name already exists in this category."}
                )
        return attrs


class MaterialSubcategoryWriteSerializer(MaterialSubcategorySerializer):
    class Meta(MaterialSubcategorySerializer.Meta):
        extra_kwargs = {
            "is_active": {"required": False},
            "category_id": {"required": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["category_id"].required = False

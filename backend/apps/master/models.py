import uuid
from pathlib import Path

from django.conf import settings
from django.db import connection, models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


def material_image_upload_to(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower() or ".jpg"
    return f"materials/images/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


def material_thumb_upload_to(instance, filename: str) -> str:
    return f"materials/thumbs/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.webp"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class NameMasterModel(TimeStampedModel):
    """Shared base for simple name-based masters (Division, Department, etc.)."""

    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    @classmethod
    def name_exists(cls, name: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class Division(NameMasterModel):
    class Meta(NameMasterModel.Meta):
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_division_name_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_division_name_ci_idx"),
        ]


class Department(NameMasterModel):
    class Meta(NameMasterModel.Meta):
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_department_name_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_department_name_ci_idx"),
        ]


class Designation(NameMasterModel):
    class Meta(NameMasterModel.Meta):
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_designation_name_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_designation_name_ci_idx"),
        ]


class Facility(NameMasterModel):
    class Meta(NameMasterModel.Meta):
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_facility_name_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_facility_name_ci_idx"),
        ]


class Company(NameMasterModel):
    class Meta(NameMasterModel.Meta):
        verbose_name_plural = "companies"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_company_name_ci_uq"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_company_name_ci_idx"),
        ]


class Unit(TimeStampedModel):
    name = models.CharField(max_length=150)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="units",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "company",
                name="master_unit_name_company_ci_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["company"]),
            models.Index(Lower("name"), name="master_unit_name_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.company})"

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    @classmethod
    def name_exists_in_company(
        cls,
        name: str,
        company_id: int,
        *,
        exclude_pk: int | None = None,
    ) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned, company_id=company_id)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class MaterialCategory(NameMasterModel):
    class Meta(NameMasterModel.Meta):
        verbose_name_plural = "material categories"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_matcat_name_ci_uq"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_matcat_name_ci_idx"),
        ]


class WeighBridge(NameMasterModel):
    class Meta(NameMasterModel.Meta):
        verbose_name_plural = "weighbridges"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_weighbridge_name_ci_uq"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_weighbridge_name_ci_idx"),
        ]


class MaterialSubcategory(TimeStampedModel):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        related_name="subcategories",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "material subcategories"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "category",
                name="master_matsub_name_cat_ci_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["category"]),
            models.Index(Lower("name"), name="master_matsub_name_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.category})"

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    @classmethod
    def name_exists_in_category(
        cls,
        name: str,
        category_id: int,
        *,
        exclude_pk: int | None = None,
    ) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned, category_id=category_id)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class Vertical(TimeStampedModel):
    name = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="verticals",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_vertical_name_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["department"]),
            models.Index(Lower("name"), name="master_vertical_name_ci_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    @classmethod
    def name_exists(cls, name: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class Uom(TimeStampedModel):
    name = models.CharField(max_length=150)
    symbol = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_uom_name_ci_unique"),
            models.UniqueConstraint(Lower("symbol"), name="master_uom_symbol_ci_unique"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_uom_name_ci_idx"),
            models.Index(Lower("symbol"), name="master_uom_symbol_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.symbol})"

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        if self.symbol is not None:
            self.symbol = self.symbol.strip()
        super().save(*args, **kwargs)

    @classmethod
    def name_exists(cls, name: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    @classmethod
    def symbol_exists(cls, symbol: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = symbol.strip()
        qs = cls.objects.filter(symbol__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class QcParameter(TimeStampedModel):
    """Quality check parameter (e.g. Moisture / MC / %). Unit is free text, not a UOM link."""

    NAME_MAX_LENGTH = 150
    SHORT_NAME_MAX_LENGTH = 30
    UNIT_MAX_LENGTH = 50

    name = models.CharField(max_length=NAME_MAX_LENGTH)
    short_name = models.CharField(max_length=SHORT_NAME_MAX_LENGTH)
    unit = models.CharField(max_length=UNIT_MAX_LENGTH, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qc_parameters_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qc_parameters_updated",
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(Lower("name"), name="master_qcparam_name_ci_unique"),
            models.UniqueConstraint(
                Lower("short_name"), name="master_qcparam_short_name_ci_unique"
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_qcparam_name_ci_idx"),
            models.Index(Lower("short_name"), name="master_qcparam_short_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.short_name})"

    def save(self, *args, **kwargs):
        from .qc_parameter_rules import clean_qc_text

        self.name = clean_qc_text(self.name)
        self.short_name = clean_qc_text(self.short_name).upper()
        self.unit = clean_qc_text(self.unit)
        super().save(*args, **kwargs)


VENDOR_ID_SEQUENCE = "master_vendor_id_seq"
VENDOR_ID_PREFIX = "VEN-"


def format_vendor_id(number: int) -> str:
    return f"{VENDOR_ID_PREFIX}{number:06d}"


def next_vendor_ids(count: int) -> list[str]:
    """Reserve ``count`` ERP Vendor IDs from the PostgreSQL sequence (safe under concurrency)."""
    if count <= 0:
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nextval(%s) FROM generate_series(1, %s)",
            [VENDOR_ID_SEQUENCE, count],
        )
        return [format_vendor_id(row[0]) for row in cursor.fetchall()]


class Vendor(TimeStampedModel):
    """Procurement vendor. ERP Vendor ID is the internal key; SAP Vendor ID is optional."""

    SAP_VENDOR_ID_MAX_LENGTH = 30
    VENDOR_NAME_MAX_LENGTH = 255
    CONTACT_NO_MAX_LENGTH = 20
    GSTIN_LENGTH = 15
    LOCATION_MAX_LENGTH = 150

    erp_vendor_id = models.CharField(max_length=20, unique=True, editable=False)
    sap_vendor_id = models.CharField(max_length=SAP_VENDOR_ID_MAX_LENGTH, blank=True, default="")
    vendor_name = models.CharField(max_length=VENDOR_NAME_MAX_LENGTH)
    email = models.EmailField(max_length=254, blank=True, default="")
    # Text, never numeric: keeps leading zeros and "+" country codes.
    contact_no = models.CharField(max_length=CONTACT_NO_MAX_LENGTH, blank=True, default="")
    gstin = models.CharField(max_length=GSTIN_LENGTH, blank=True, default="")
    location = models.CharField(max_length=LOCATION_MAX_LENGTH, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendors_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendors_updated",
    )

    class Meta:
        ordering = ("vendor_name", "id")
        constraints = [
            models.UniqueConstraint(
                Lower("sap_vendor_id"),
                condition=~Q(sap_vendor_id=""),
                name="master_vendor_sap_id_ci_uq",
            ),
            models.UniqueConstraint(
                fields=["gstin"], condition=~Q(gstin=""), name="master_vendor_gstin_uq"
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("vendor_name"), name="master_vendor_name_ci_idx"),
            models.Index(Lower("location"), name="master_vendor_location_ci_idx"),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.erp_vendor_id} — {self.vendor_name}"

    def save(self, *args, **kwargs):
        from .vendor_rules import clean_vendor_text

        self.sap_vendor_id = clean_vendor_text(self.sap_vendor_id)
        self.vendor_name = clean_vendor_text(self.vendor_name)
        self.email = clean_vendor_text(self.email).lower()
        self.contact_no = clean_vendor_text(self.contact_no)
        self.gstin = clean_vendor_text(self.gstin).replace(" ", "").upper()
        self.location = clean_vendor_text(self.location)
        if not self.erp_vendor_id:
            self.erp_vendor_id = next_vendor_ids(1)[0]
        super().save(*args, **kwargs)


class StockYard(TimeStampedModel):
    """SAP storage location. Name may repeat; storage code is the unique key."""

    name = models.CharField(max_length=150)
    sap_storage_code = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name", "sap_storage_code")
        verbose_name_plural = "stock yards"
        constraints = [
            models.UniqueConstraint(
                Lower("sap_storage_code"),
                name="master_stockyard_code_ci_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("name"), name="master_stockyard_name_ci_idx"),
            models.Index(Lower("sap_storage_code"), name="master_stockyard_code_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sap_storage_code})"

    def save(self, *args, **kwargs):
        if self.name is not None:
            self.name = self.name.strip()
        if self.sap_storage_code is not None:
            self.sap_storage_code = self.sap_storage_code.strip().upper()
        super().save(*args, **kwargs)

    @classmethod
    def sap_storage_code_exists(
        cls,
        sap_storage_code: str,
        *,
        exclude_pk: int | None = None,
    ) -> bool:
        cleaned = sap_storage_code.strip().upper()
        qs = cls.objects.filter(sap_storage_code__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class MaterialGroup(TimeStampedModel):
    """SAP Material Group mapping (independent of Category/Subcategory)."""

    sap_material_group_code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sap_material_group_code",)
        verbose_name_plural = "material groups"
        constraints = [
            models.UniqueConstraint(
                Lower("sap_material_group_code"),
                name="master_matgroup_code_ci_uq",
            ),
            models.UniqueConstraint(Lower("name"), name="master_matgroup_name_ci_uq"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(
                Lower("sap_material_group_code"),
                name="master_matgroup_code_ci_idx",
            ),
            models.Index(Lower("name"), name="master_matgroup_name_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.sap_material_group_code} — {self.name}"

    def save(self, *args, **kwargs):
        if self.sap_material_group_code is not None:
            self.sap_material_group_code = self.sap_material_group_code.strip()
        if self.name is not None:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    @classmethod
    def sap_code_exists(cls, sap_code: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = sap_code.strip()
        qs = cls.objects.filter(sap_material_group_code__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    @classmethod
    def name_exists(cls, name: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class PurchasingGroup(TimeStampedModel):
    """SAP Purchase Group mapping."""

    sap_purchase_group_code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    remarks = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sap_purchase_group_code",)
        verbose_name_plural = "purchasing groups"
        constraints = [
            models.UniqueConstraint(
                Lower("sap_purchase_group_code"),
                name="master_purchgroup_code_ci_uq",
            ),
            models.UniqueConstraint(Lower("name"), name="master_purchgroup_name_ci_uq"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(
                Lower("sap_purchase_group_code"),
                name="master_purchgroup_code_ci_idx",
            ),
            models.Index(Lower("name"), name="master_purchgroup_name_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.sap_purchase_group_code} — {self.name}"

    def save(self, *args, **kwargs):
        if self.sap_purchase_group_code is not None:
            self.sap_purchase_group_code = self.sap_purchase_group_code.strip()
        if self.name is not None:
            self.name = self.name.strip()
        if self.remarks is not None:
            self.remarks = self.remarks.strip()
        super().save(*args, **kwargs)

    @classmethod
    def sap_code_exists(cls, sap_code: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = sap_code.strip()
        qs = cls.objects.filter(sap_purchase_group_code__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    @classmethod
    def name_exists(cls, name: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class Plant(TimeStampedModel):
    """SAP Plant mapping (independent of Facility name master)."""

    sap_plant_code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sap_plant_code",)
        verbose_name_plural = "plants"
        constraints = [
            models.UniqueConstraint(
                Lower("sap_plant_code"),
                name="master_plant_code_ci_uq",
            ),
            models.UniqueConstraint(Lower("name"), name="master_plant_name_ci_uq"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("sap_plant_code"), name="master_plant_code_ci_idx"),
            models.Index(Lower("name"), name="master_plant_name_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.sap_plant_code} — {self.name}"

    def save(self, *args, **kwargs):
        if self.sap_plant_code is not None:
            self.sap_plant_code = self.sap_plant_code.strip()
        if self.name is not None:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    @classmethod
    def sap_code_exists(cls, sap_code: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = sap_code.strip()
        qs = cls.objects.filter(sap_plant_code__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    @classmethod
    def name_exists(cls, name: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = name.strip()
        qs = cls.objects.filter(name__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class MaterialType(TimeStampedModel):
    """SAP Material Type mapping (e.g. ROH, HALB, FERT)."""

    material_type_code = models.CharField(max_length=50)
    erp_category_desc = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("material_type_code",)
        verbose_name_plural = "material types"
        constraints = [
            models.UniqueConstraint(
                Lower("material_type_code"),
                name="master_mattype_code_ci_uq",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("material_type_code"), name="master_mattype_code_ci_idx"),
            models.Index(Lower("erp_category_desc"), name="master_mattype_desc_ci_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.material_type_code} — {self.erp_category_desc}"

    def save(self, *args, **kwargs):
        if self.material_type_code is not None:
            self.material_type_code = self.material_type_code.strip()
        if self.erp_category_desc is not None:
            self.erp_category_desc = self.erp_category_desc.strip()
        super().save(*args, **kwargs)

    @classmethod
    def code_exists(cls, code: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = code.strip()
        qs = cls.objects.filter(material_type_code__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()


class Material(TimeStampedModel):
    """Central Material / Item master (21 Excel business columns + technical fields)."""

    item_name = models.CharField(max_length=255)
    item_description = models.TextField()
    descriptive_spec = models.TextField()
    technical_spec = models.TextField(blank=True, default="")
    document_type = models.CharField(max_length=50)
    store_code = models.CharField(max_length=50)

    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="materials",
    )
    material_category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    material_subcategory = models.ForeignKey(
        MaterialSubcategory,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    uom = models.ForeignKey(
        Uom,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    stock_yard = models.ForeignKey(
        StockYard,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="materials",
    )

    hsn_sac_code = models.CharField(max_length=50)
    gst_percent = models.DecimalField(max_digits=6, decimal_places=2)
    price = models.DecimalField(max_digits=18, decimal_places=2)
    sap_code = models.CharField(max_length=50)

    plant = models.ForeignKey(
        Plant,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    material_group = models.ForeignKey(
        MaterialGroup,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    material_type = models.ForeignKey(
        MaterialType,
        on_delete=models.PROTECT,
        related_name="materials",
    )
    purchasing_group = models.ForeignKey(
        PurchasingGroup,
        on_delete=models.PROTECT,
        related_name="materials",
    )

    class ImageSource(models.TextChoices):
        NONE = "NONE", "None"
        UPLOAD = "UPLOAD", "Upload"
        URL = "URL", "URL"

    image_source = models.CharField(
        max_length=10,
        choices=ImageSource.choices,
        default=ImageSource.NONE,
    )
    image_url = models.TextField(blank=True, default="")
    image_file = models.ImageField(
        upload_to=material_image_upload_to,
        blank=True,
        default="",
        max_length=255,
    )
    image_thumb = models.ImageField(
        upload_to=material_thumb_upload_to,
        blank=True,
        default="",
        max_length=255,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials_updated",
    )

    class Meta:
        ordering = ("sap_code",)
        verbose_name_plural = "materials"
        constraints = [
            models.UniqueConstraint(Lower("sap_code"), name="master_material_sap_ci_uq"),
            models.CheckConstraint(
                condition=(
                    Q(image_source="NONE", image_url="", image_file="", image_thumb="")
                    | (Q(image_source="UPLOAD", image_url="") & ~Q(image_file=""))
                    | (
                        Q(image_source="URL", image_file="", image_thumb="")
                        & ~Q(image_url="")
                    )
                ),
                name="master_material_image_source_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("sap_code"), name="master_material_sap_ci_idx"),
            models.Index(Lower("item_name"), name="master_material_name_ci_idx"),
            models.Index(Lower("hsn_sac_code"), name="master_material_hsn_ci_idx"),
            models.Index(Lower("store_code"), name="master_material_store_ci_idx"),
            models.Index(fields=["material_category"]),
            models.Index(fields=["material_subcategory"]),
            models.Index(fields=["uom"]),
            models.Index(fields=["material_type"]),
            models.Index(fields=["material_group"]),
            models.Index(fields=["purchasing_group"]),
            models.Index(fields=["plant"]),
            models.Index(fields=["stock_yard"]),
            models.Index(fields=["department"]),
            models.Index(fields=["division"]),
            models.Index(fields=["price"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.sap_code} — {self.item_name}"

    def save(self, *args, **kwargs):
        if self.item_name is not None:
            self.item_name = self.item_name.strip()
        if self.document_type is not None:
            self.document_type = self.document_type.strip()
        if self.store_code is not None:
            self.store_code = str(self.store_code).strip()
        if self.hsn_sac_code is not None:
            self.hsn_sac_code = str(self.hsn_sac_code).strip()
        if self.sap_code is not None:
            self.sap_code = str(self.sap_code).strip()
        if self.image_url is not None:
            self.image_url = self.image_url.strip()
        if self.technical_spec is None:
            self.technical_spec = ""
        super().save(*args, **kwargs)

    @classmethod
    def sap_code_exists(cls, sap_code: str, *, exclude_pk: int | None = None) -> bool:
        cleaned = str(sap_code).strip()
        qs = cls.objects.filter(sap_code__iexact=cleaned)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    @property
    def has_image(self) -> bool:
        return self.image_source != self.ImageSource.NONE


EMPLOYEE_CODE_SEQUENCE = "master_employee_code_seq"
EMPLOYEE_CODE_PREFIX = "EMP-"


def format_employee_code(number: int) -> str:
    return f"{EMPLOYEE_CODE_PREFIX}{number:06d}"


def next_employee_codes(count: int) -> list[str]:
    """Reserve ``count`` Employee Codes from the PostgreSQL sequence (safe under concurrency)."""
    if count <= 0:
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nextval(%s) FROM generate_series(1, %s)",
            [EMPLOYEE_CODE_SEQUENCE, count],
        )
        return [format_employee_code(row[0]) for row in cursor.fetchall()]


class Employee(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"
        OTHER = "Other", "Other"
        PREFER_NOT_TO_SAY = "Prefer Not to Say", "Prefer Not to Say"

    employee_code = models.CharField(max_length=20, unique=True, editable=False)
    full_name = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="employees"
    )
    vertical = models.ForeignKey(
        Vertical,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    personal_email = models.EmailField(max_length=254, blank=True, default="")
    company_email = models.EmailField(max_length=254, blank=True, default="")
    designation = models.ForeignKey(
        Designation, on_delete=models.PROTECT, related_name="employees"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="employees")
    unit = models.ForeignKey(
        Unit,
        on_delete=models.SET_NULL,
        related_name="employees",
        null=True,
        blank=True,
    )
    division = models.ForeignKey(
        Division,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    date_of_joining = models.DateField()
    location = models.CharField(max_length=150)
    gender = models.CharField(max_length=20, choices=Gender.choices)
    # Normalized text (digits with optional leading "+"); never stored as a number.
    mobile_number = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees_updated",
    )

    class Meta:
        ordering = ("employee_code",)
        constraints = [
            models.UniqueConstraint(fields=["mobile_number"], name="master_employee_mobile_uq"),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(Lower("full_name"), name="master_employee_name_ci_idx"),
            models.Index(fields=["personal_email"]),
            models.Index(fields=["company_email"]),
            models.Index(fields=["department"]),
            models.Index(fields=["vertical"]),
            models.Index(fields=["designation"]),
            models.Index(fields=["company"]),
            models.Index(fields=["unit"]),
            models.Index(fields=["division"]),
            models.Index(fields=["facility"]),
            models.Index(fields=["gender"]),
            models.Index(fields=["date_of_joining"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee_code} — {self.full_name}"

    def save(self, *args, **kwargs):
        if self.full_name is not None:
            self.full_name = self.full_name.strip()
        if self.location is not None:
            self.location = self.location.strip()
        self.personal_email = (self.personal_email or "").strip().lower()
        self.company_email = (self.company_email or "").strip().lower()
        if not self.employee_code:
            self.employee_code = next_employee_codes(1)[0]
        super().save(*args, **kwargs)


class ImportJob(models.Model):
    class MasterType(models.TextChoices):
        DIVISION = "division", "Division"
        DEPARTMENT = "department", "Department"
        DESIGNATION = "designation", "Designation"
        FACILITY = "facility", "Facility"
        UNIT = "unit", "Unit"
        COMPANY = "company", "Company"
        VERTICAL = "vertical", "Vertical"
        UOM = "uom", "UOM"
        MATERIAL_CATEGORY = "material_category", "Material Category"
        MATERIAL_SUBCATEGORY = "material_subcategory", "Material Subcategory"
        STOCK_YARD = "stock_yard", "Stock Yard"
        MATERIAL_GROUP = "material_group", "Material Group"
        PURCHASING_GROUP = "purchasing_group", "Purchasing Group"
        PLANT = "plant", "Plant"
        WEIGHBRIDGE = "weighbridge", "WeighBridge"
        MATERIAL_TYPE = "material_type", "Material Type"
        MATERIAL = "material", "Material"
        EMPLOYEE = "employee", "Employee"
        QC_PARAMETER = "qc_parameter", "QC Parameter"
        VENDOR = "vendor", "Vendor"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VALIDATING = "VALIDATING", "Validating"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS", "Completed with errors"
        FAILED = "FAILED", "Failed"

    master_type = models.CharField(max_length=32, choices=MasterType.choices)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    source_file = models.FileField(upload_to="master_imports/source/%Y/%m/%d/")
    error_file = models.FileField(upload_to="master_imports/errors/%Y/%m/%d/", blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    processed_rows = models.PositiveIntegerField(default=0)
    created_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    failed_rows = models.PositiveIntegerField(default=0)
    warning_rows = models.PositiveIntegerField(default=0)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    detail = models.TextField(blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="master_import_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.master_type} import #{self.pk} ({self.status})"

    def refresh_progress(self) -> None:
        if self.total_rows > 0:
            self.progress_percentage = min(
                100,
                int((self.processed_rows * 100) / self.total_rows),
            )
        elif self.status in {
            self.Status.COMPLETED,
            self.Status.COMPLETED_WITH_ERRORS,
            self.Status.FAILED,
        }:
            self.progress_percentage = 100
        else:
            self.progress_percentage = 0


class ImportJobError(models.Model):
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="errors")
    row_number = models.PositiveIntegerField()
    input_data = models.TextField(blank=True)
    reason = models.TextField()
    is_warning = models.BooleanField(default=False)

    class Meta:
        ordering = ("row_number", "id")

    def __str__(self) -> str:
        return f"Job {self.job_id} row {self.row_number}"

import shutil
import tempfile
from io import BytesIO, StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings
from openpyxl import Workbook
from PIL import Image
from rest_framework.test import APIClient

from apps.common.access_control.constants import Module
from apps.common.access_control.testing import grant_access

from .import_engine import process_import_job
from .material_excel import EXCEL_IMAGE_WARNING, MATERIAL_EXCEL_HEADERS, resolve_excel_image
from .material_image_rules import (
    LEGACY_BLANK,
    LEGACY_INVALID,
    LEGACY_UPLOAD,
    LEGACY_URL,
    classify_legacy_image_value,
    matching_thumb_path,
    normalize_relative_media_path,
)
from .material_images import resolve_display_image, resolve_display_thumb
from .models import (
    Department,
    ImportJob,
    Material,
    MaterialCategory,
    MaterialGroup,
    MaterialSubcategory,
    MaterialType,
    Plant,
    PurchasingGroup,
    StockYard,
    Uom,
)

MEDIA_ROOT = tempfile.mkdtemp(prefix="material-images-test-")
VALID_URL = "https://cdn.example.com/images/bolt.jpg"


def _image_bytes(fmt: str = "PNG", size=(64, 48)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "red").save(buffer, format=fmt)
    return buffer.getvalue()


def _png_upload(name: str = "My Photo (1).png") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _image_bytes("PNG"), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_ROOT, MATERIAL_IMAGE_MAX_BYTES=5 * 1024 * 1024)
class MaterialImageTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="images@example.com", password="pass12345!"
        )
        grant_access(cls.user, Module.MASTER)
        cls.category = MaterialCategory.objects.create(name="RAW MATERIAL")
        cls.subcategory = MaterialSubcategory.objects.create(name="STEEL", category=cls.category)
        cls.uom = Uom.objects.create(name="Numbers", symbol="NOS")
        cls.stock_yard = StockYard.objects.create(name="CENTRAL STORE", sap_storage_code="1201")
        cls.department = Department.objects.create(name="STORES")
        cls.plant = Plant.objects.create(sap_plant_code="1201", name="MIL")
        cls.material_group = MaterialGroup.objects.create(
            sap_material_group_code="420171", name="Bolts"
        )
        cls.material_type = MaterialType.objects.create(
            material_type_code="ROH", erp_category_desc="Raw"
        )
        cls.purchasing_group = PurchasingGroup.objects.create(
            sap_purchase_group_code="P01", name="Purchase"
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.material = self.make_material("000000000000000001")

    def make_material(self, sap_code: str, **extra) -> Material:
        return Material.objects.create(
            item_name="Hex Bolt",
            item_description="Hex bolt M10",
            descriptive_spec="M10 x 50",
            document_type="ZNB",
            store_code="1201",
            material_category=self.category,
            material_subcategory=self.subcategory,
            uom=self.uom,
            stock_yard=self.stock_yard,
            department=self.department,
            hsn_sac_code="73181500",
            gst_percent="18",
            price="12.50",
            sap_code=sap_code,
            plant=self.plant,
            material_group=self.material_group,
            material_type=self.material_type,
            purchasing_group=self.purchasing_group,
            **extra,
        )

    def url(self, suffix: str) -> str:
        return f"/api/v1/master/materials/{self.material.pk}/{suffix}"

    def upload(self, upload=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                self.url("image/upload/"),
                {"file": upload or _png_upload()},
                format="multipart",
            )

    def set_url(self, value):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url("image/url/"), {"image_url": value}, format="json")

    def remove(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.delete(self.url("image/"))


class MaterialImageApiTests(MaterialImageTestBase):
    def test_material_with_no_image(self):
        response = self.client.get("/api/v1/master/materials/")
        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertEqual(row["image_source"], "NONE")
        self.assertIsNone(row["display_image"])
        self.assertIsNone(row["display_thumb"])

    def test_upload_image(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["image_source"], "UPLOAD")
        media = "http://testserver/media/materials"
        self.assertTrue(data["display_image"].startswith(f"{media}/images/"))
        self.assertTrue(data["display_thumb"].startswith(f"{media}/thumbs/"))
        self.assertTrue(data["display_thumb"].endswith(".webp"))
        self.assertEqual(data["image_url"], "")

        self.material.refresh_from_db()
        stored = Path(self.material.image_file.name).name
        self.assertNotIn("Photo", stored)
        self.assertTrue(stored.endswith(".png"))
        self.assertTrue(Path(self.material.image_file.path).exists())
        self.assertTrue(Path(self.material.image_thumb.path).exists())

        with Image.open(self.material.image_thumb.path) as thumb:
            self.assertEqual(thumb.format, "WEBP")

    def test_upload_detects_format_not_filename(self):
        upload = SimpleUploadedFile("photo.png", _image_bytes("JPEG"), content_type="image/png")
        response = self.upload(upload)
        self.assertEqual(response.status_code, 200, response.content)
        self.material.refresh_from_db()
        self.assertTrue(self.material.image_file.name.endswith(".jpg"))

    def test_url_image(self):
        response = self.set_url(f"  {VALID_URL}  ")
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["image_source"], "URL")
        self.assertEqual(data["display_image"], VALID_URL)
        self.assertEqual(data["display_thumb"], VALID_URL)
        self.assertEqual(data["item_image"], VALID_URL)

    def test_replace_upload_with_url_deletes_old_file(self):
        self.upload()
        self.material.refresh_from_db()
        old_file = Path(self.material.image_file.path)
        old_thumb = Path(self.material.image_thumb.path)

        response = self.set_url(VALID_URL)
        self.assertEqual(response.status_code, 200)
        self.material.refresh_from_db()
        self.assertEqual(self.material.image_source, Material.ImageSource.URL)
        self.assertFalse(self.material.image_file)
        self.assertFalse(self.material.image_thumb)
        self.assertFalse(old_file.exists())
        self.assertFalse(old_thumb.exists())

    def test_replace_url_with_upload(self):
        self.set_url(VALID_URL)
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.material.refresh_from_db()
        self.assertEqual(self.material.image_source, Material.ImageSource.UPLOAD)
        self.assertEqual(self.material.image_url, "")
        self.assertTrue(self.material.image_file)

    def test_remove_image_keeps_material(self):
        self.upload()
        self.material.refresh_from_db()
        old_file = Path(self.material.image_file.path)

        response = self.remove()
        self.assertEqual(response.status_code, 200)
        self.material.refresh_from_db()
        self.assertEqual(self.material.image_source, Material.ImageSource.NONE)
        self.assertFalse(self.material.image_file)
        self.assertEqual(self.material.image_url, "")
        self.assertTrue(self.material.is_active)
        self.assertEqual(self.material.item_name, "Hex Bolt")
        self.assertEqual(self.material.sap_code, "000000000000000001")
        self.assertFalse(old_file.exists())

    def test_image_actions_do_not_touch_other_fields(self):
        before = Material.objects.values().get(pk=self.material.pk)
        self.set_url(VALID_URL)
        after = Material.objects.values().get(pk=self.material.pk)
        changed = {k for k in before if before[k] != after[k]}
        self.assertEqual(changed, {"image_url", "image_source", "updated_at", "updated_by_id"})

    def test_invalid_urls_rejected(self):
        for value in [
            "javascript:alert(1)",
            "data:image/png;base64,AAAA",
            "vbscript:msgbox",
            "ftp://example.com/a.jpg",
            "not a url",
            "",
            "https://" + "a" * 600 + ".com/x.jpg",
        ]:
            with self.subTest(value=value[:40]):
                response = self.set_url(value)
                self.assertEqual(response.status_code, 400)
        self.material.refresh_from_db()
        self.assertEqual(self.material.image_source, Material.ImageSource.NONE)

    def test_invalid_file_types_rejected(self):
        cases = [
            SimpleUploadedFile("fake.jpg", b"not an image at all", content_type="image/jpeg"),
            SimpleUploadedFile("anim.gif", _image_bytes("GIF"), content_type="image/gif"),
            SimpleUploadedFile("doc.pdf", b"%PDF-1.4", content_type="application/pdf"),
            SimpleUploadedFile(
                "script.png", b"<script>alert(1)</script>", content_type="image/png"
            ),
        ]
        for upload in cases:
            with self.subTest(name=upload.name):
                response = self.upload(upload)
                self.assertEqual(response.status_code, 400)
        self.material.refresh_from_db()
        self.assertEqual(self.material.image_source, Material.ImageSource.NONE)

    def test_missing_file_rejected(self):
        response = self.client.post(self.url("image/upload/"), {}, format="multipart")
        self.assertEqual(response.status_code, 400)

    @override_settings(MATERIAL_IMAGE_MAX_BYTES=1024)
    def test_oversized_file_rejected(self):
        upload = SimpleUploadedFile(
            "big.png", _image_bytes("PNG", size=(800, 800)) + b"\0" * 2048, content_type="image/png"
        )
        response = self.upload(upload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("or smaller", response.content.decode())
        self.material.refresh_from_db()
        self.assertEqual(self.material.image_source, Material.ImageSource.NONE)

    def test_general_edit_cannot_change_image(self):
        self.set_url(VALID_URL)
        response = self.client.patch(
            self.url(""),
            {
                "item_name": "Hex Bolt Renamed",
                "image_url": "https://evil.example.com/x.jpg",
                "image_source": "NONE",
                "item_image": "",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.material.refresh_from_db()
        self.assertEqual(self.material.item_name, "Hex Bolt Renamed")
        self.assertEqual(self.material.image_url, VALID_URL)
        self.assertEqual(self.material.image_source, Material.ImageSource.URL)

    def test_constraint_blocks_inconsistent_source(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Material.objects.filter(pk=self.material.pk).update(image_source="UPLOAD")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Material.objects.filter(pk=self.material.pk).update(
                image_source="NONE", image_url=VALID_URL
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Material.objects.filter(pk=self.material.pk).update(
                image_source="URL", image_url=VALID_URL, image_file="materials/images/x.png"
            )


class MaterialImageExcelTests(MaterialImageTestBase):
    def test_resolve_excel_image(self):
        self.assertEqual(resolve_excel_image(""), ("", "NONE", None))
        self.assertEqual(resolve_excel_image(f" {VALID_URL} "), (VALID_URL, "URL", None))
        url, source, warning = resolve_excel_image("images/bolt.jpg")
        self.assertEqual((url, source), ("", "NONE"))
        self.assertEqual(warning, EXCEL_IMAGE_WARNING)
        self.assertIn("image skipped because Item image URL is invalid", warning)
        url, source, warning = resolve_excel_image("javascript:alert(1)")
        self.assertEqual((url, source), ("", "NONE"))
        self.assertIsNotNone(warning)

    def _row(self, sap_code: str, image: str) -> list[str]:
        return [
            "Hex Bolt", "Hex bolt M10", "M10 x 50", "", "ZNB", "1201", "",
            "RAW MATERIAL", "STEEL", "NOS", "CENTRAL STORE", "STORES", "73181500",
            "18", "12.50", sap_code, "1201", "420171", "ROH", "P01", image,
        ]

    def test_excel_import_with_url_blank_and_invalid_images(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(MATERIAL_EXCEL_HEADERS)
        sheet.append(self._row("100000000000000001", VALID_URL))
        sheet.append(self._row("100000000000000002", ""))
        sheet.append(self._row("100000000000000003", "not-a-url"))
        buffer = BytesIO()
        workbook.save(buffer)

        job = ImportJob(master_type=ImportJob.MasterType.MATERIAL, original_filename="m.xlsx")
        job.source_file.save("materials.xlsx", ContentFile(buffer.getvalue()), save=False)
        job.save()

        process_import_job(job.pk)
        job.refresh_from_db()

        self.assertEqual(job.status, ImportJob.Status.COMPLETED, job.detail)
        self.assertEqual(job.created_rows, 3)
        self.assertEqual(job.failed_rows, 0)
        self.assertEqual(job.warning_rows, 1)
        self.assertTrue(job.error_file)
        self.assertEqual(job.errors.filter(is_warning=True).count(), 1)

        by_sap = {m.sap_code: m for m in Material.objects.filter(sap_code__startswith="1000")}
        self.assertEqual(by_sap["100000000000000001"].image_source, "URL")
        self.assertEqual(by_sap["100000000000000001"].image_url, VALID_URL)
        self.assertEqual(by_sap["100000000000000002"].image_source, "NONE")
        self.assertEqual(by_sap["100000000000000003"].image_source, "NONE")
        self.assertEqual(by_sap["100000000000000003"].image_url, "")
        self.assertEqual(by_sap["100000000000000003"].item_name, "Hex Bolt")

    def test_excel_relative_path_is_not_treated_as_upload(self):
        name = default_storage.save(
            "materials/images/2026/09/excel.png", ContentFile(_image_bytes())
        )
        url, source, warning = resolve_excel_image(name)
        self.assertEqual((url, source), ("", "NONE"))
        self.assertEqual(warning, EXCEL_IMAGE_WARNING)


@override_settings(ALLOWED_HOSTS=["*"])
class MaterialImageResolutionTests(MaterialImageTestBase):
    def request(self, host="erp.example.com"):
        return RequestFactory().get("/api/v1/master/materials/", HTTP_HOST=host)

    def test_display_thumb_with_file_but_no_thumb_is_none(self):
        material = Material(image_file="materials/images/2026/09/a.png", image_source="UPLOAD")
        self.assertEqual(
            resolve_display_image(material, self.request()),
            "http://erp.example.com/media/materials/images/2026/09/a.png",
        )
        self.assertIsNone(resolve_display_thumb(material, self.request()))

    def test_display_urls_follow_request_host(self):
        material = Material(
            image_file="materials/images/2026/09/a.png",
            image_thumb="materials/thumbs/2026/09/a.webp",
            image_source="UPLOAD",
        )
        self.assertEqual(
            resolve_display_thumb(material, self.request("erp.prod.local")),
            "http://erp.prod.local/media/materials/thumbs/2026/09/a.webp",
        )
        self.assertEqual(
            resolve_display_image(material, self.request("10.0.0.5:8000")),
            "http://10.0.0.5:8000/media/materials/images/2026/09/a.png",
        )

    @override_settings(BACKEND_URL="https://api.dyly.example")
    def test_display_urls_without_request_use_backend_url(self):
        material = Material(image_file="materials/images/2026/09/a.png", image_source="UPLOAD")
        self.assertEqual(
            resolve_display_image(material),
            "https://api.dyly.example/media/materials/images/2026/09/a.png",
        )

    def test_url_only_material(self):
        material = Material(image_url=VALID_URL, image_source="URL")
        self.assertEqual(resolve_display_image(material, self.request()), VALID_URL)
        self.assertEqual(resolve_display_thumb(material, self.request()), VALID_URL)

    def test_resolution_ignores_inconsistent_source(self):
        material = Material(image_file="materials/images/2026/09/a.png", image_source="NONE")
        self.assertTrue(resolve_display_image(material, self.request()).endswith("/a.png"))
        material = Material(image_url=VALID_URL, image_source="UPLOAD")
        self.assertEqual(resolve_display_image(material, self.request()), VALID_URL)
        self.assertIsNone(resolve_display_image(Material(image_source="URL")))

    def test_uploaded_record_stores_relative_path_only(self):
        self.upload()
        self.material.refresh_from_db()
        for name in (self.material.image_file.name, self.material.image_thumb.name):
            self.assertFalse(name.startswith(("http://", "https://", "/")))
            self.assertTrue(name.startswith("materials/"))
        self.assertEqual(self.material.image_url, "")


class MaterialImageLegacyTests(MaterialImageTestBase):
    def test_normalize_relative_media_path(self):
        self.assertEqual(
            normalize_relative_media_path(" materials\\images\\a.png "), "materials/images/a.png"
        )
        for bad in ["", "../etc/passwd.png", "/abs/a.png", "C:/pics/a.png", "a//b.png",
                    "materials/images/a.gif", "https://x.com/a.png", "materials/./a.png"]:
            with self.subTest(bad=bad):
                self.assertIsNone(normalize_relative_media_path(bad))

    def test_classify_legacy_values(self):
        existing = default_storage.save("materials/images/2026/09/legacy.png",
                                        ContentFile(_image_bytes()))
        cases = {
            VALID_URL: (LEGACY_URL, VALID_URL),
            existing: (LEGACY_UPLOAD, existing),
            f"media/{existing}": (LEGACY_UPLOAD, existing),
            "materials/images/2026/09/missing.png": (LEGACY_INVALID, None),
            "  ": (LEGACY_BLANK, ""),
            "C:\\photos\\bolt.jpg": (LEGACY_INVALID, None),
            "javascript:alert(1)": (LEGACY_INVALID, None),
        }
        for raw, (kind, value) in cases.items():
            with self.subTest(raw=raw):
                got_kind, got_value = classify_legacy_image_value(raw, default_storage)
                self.assertEqual(got_kind, kind)
                if value is not None:
                    self.assertEqual(got_value, value)

    def test_matching_thumb_path(self):
        image = "materials/images/2026/09/pair.png"
        self.assertIsNone(matching_thumb_path(image, default_storage))
        thumb = default_storage.save("materials/thumbs/2026/09/pair.webp",
                                     ContentFile(_image_bytes("WEBP")))
        self.assertEqual(matching_thumb_path(image, default_storage), thumb)


class AuditMaterialImagesCommandTests(MaterialImageTestBase):
    def setUp(self):
        super().setUp()
        self.url_row = self.make_material("200000000000000001", image_url=VALID_URL,
                                          image_source="URL")
        self.blank_row = self.make_material("200000000000000002")
        file_name = default_storage.save("materials/images/2026/09/nothumb.png",
                                         ContentFile(_image_bytes()))
        self.upload_row = self.make_material("200000000000000003", image_file=file_name,
                                             image_source="UPLOAD")
        self.missing_row = self.make_material(
            "200000000000000004", image_file="materials/images/2026/09/gone.png",
            image_source="UPLOAD",
        )
        legacy = default_storage.save("materials/images/2026/09/legacy2.png",
                                      ContentFile(_image_bytes()))
        self.legacy_row = self.make_material("200000000000000005", image_url=legacy,
                                             image_source="URL")
        self.legacy_path = legacy
        self.invalid_row = self.make_material("200000000000000006",
                                              image_url="C:\\pics\\bolt.jpg", image_source="URL")

    def run_audit(self, *args) -> str:
        out = StringIO()
        call_command("audit_material_images", *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        before = list(Material.objects.order_by("pk").values())
        output = self.run_audit()
        self.assertEqual(before, list(Material.objects.order_by("pk").values()))
        self.assertIn("DRY RUN", output)
        self.assertIn("Total checked:         7", output)
        self.assertIn("Cleared invalid:       2", output)
        self.assertIn("200000000000000006", output)

    def test_apply_repairs_rows(self):
        output = self.run_audit("--apply")
        self.assertIn("APPLY", output)
        for row in (self.url_row, self.blank_row, self.upload_row, self.missing_row,
                    self.legacy_row, self.invalid_row):
            row.refresh_from_db()

        self.assertEqual((self.url_row.image_source, self.url_row.image_url), ("URL", VALID_URL))
        self.assertEqual(self.blank_row.image_source, "NONE")

        self.assertEqual(self.upload_row.image_source, "UPLOAD")
        self.assertTrue(self.upload_row.image_thumb.name.startswith("materials/thumbs/"))
        self.assertTrue(default_storage.exists(self.upload_row.image_thumb.name))

        self.assertEqual(self.missing_row.image_source, "NONE")
        self.assertFalse(self.missing_row.image_file)

        self.assertEqual(self.legacy_row.image_source, "UPLOAD")
        self.assertEqual(self.legacy_row.image_file.name, self.legacy_path)
        self.assertEqual(self.legacy_row.image_url, "")
        self.assertTrue(self.legacy_row.image_thumb)

        self.assertEqual(self.invalid_row.image_source, "NONE")
        self.assertEqual(self.invalid_row.image_url, "")
        self.assertTrue(self.invalid_row.is_active)
        self.assertEqual(Material.objects.count(), 7)

        second = self.run_audit()
        self.assertIn("Rows needing changes:  0", second)

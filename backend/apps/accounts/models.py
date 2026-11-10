from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import connection, models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.SUPERADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", _("Superadmin")
        ADMIN = "ADMIN", _("Admin")
        USER = "USER", _("User")

    username = None
    email = models.EmailField(_("email address"), unique=True)
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.USER,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self) -> str:
        return self.email

    @property
    def display_name(self) -> str:
        full = self.get_full_name().strip()
        return full or self.email

    @property
    def initials(self) -> str:
        first = (self.first_name or "").strip()
        last = (self.last_name or "").strip()
        if first and last:
            return f"{first[0]}{last[0]}".upper()
        if first:
            return first[:2].upper()
        return self.email[:2].upper()


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_tokens")
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


ONBOARDING_CODE_SEQUENCE = "accounts_onboarding_code_seq"
ONBOARDING_CODE_PREFIX = "ONB-"


def format_onboarding_code(number: int) -> str:
    return f"{ONBOARDING_CODE_PREFIX}{number:06d}"


def next_onboarding_code() -> str:
    """Reserve the next Onboarding Code from the PostgreSQL sequence (safe under concurrency)."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [ONBOARDING_CODE_SEQUENCE])
        return format_onboarding_code(cursor.fetchone()[0])


class UserOnboarding(models.Model):
    """Invitation workflow linking an Employee Master record to an ERP login account."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        INVITE_PENDING = "INVITE_PENDING", _("Invite Pending")
        INVITED = "INVITED", _("Invited")
        ACTIVATED = "ACTIVATED", _("Activated")
        EXPIRED = "EXPIRED", _("Expired")
        REVOKED = "REVOKED", _("Revoked")

    class MailStatus(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        SENT = "SENT", _("Sent")
        FAILED = "FAILED", _("Failed")

    onboarding_code = models.CharField(max_length=20, unique=True, editable=False)
    employee = models.ForeignKey(
        "master.Employee", on_delete=models.PROTECT, related_name="user_onboardings"
    )
    login_email = models.EmailField(max_length=254)
    role = models.CharField(max_length=32, choices=User.Role.choices, default=User.Role.USER)
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="onboarding",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    # SHA-256 of the current activation token; the raw token is never stored.
    invite_token_hash = models.CharField(max_length=64, blank=True, default="", editable=False)
    # Bumped whenever a new invitation is queued or revoked so stale mail tasks become no-ops.
    invite_version = models.PositiveIntegerField(default=0, editable=False)
    last_mail_status = models.CharField(
        max_length=10, choices=MailStatus.choices, blank=True, default=""
    )
    invite_sent_at = models.DateTimeField(null=True, blank=True)
    last_invite_sent_at = models.DateTimeField(null=True, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    invite_send_count = models.PositiveIntegerField(default=0)
    # Module access chosen while the onboarding has no ERP user yet, in the registry-validated
    # shape produced by access_control.services.normalize_access. Copied into
    # UserModuleAccess / UserSubmoduleAccess when the account is created; never used for checks.
    pending_access = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onboardings_created",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="onboardings_updated",
    )

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=Q(is_active=True),
                name="accounts_onboarding_employee_active_uq",
            ),
            models.UniqueConstraint(
                Lower("login_email"),
                condition=Q(is_active=True),
                name="accounts_onboarding_login_email_ci_uq",
            ),
            models.UniqueConstraint(
                fields=["invite_token_hash"],
                condition=~Q(invite_token_hash=""),
                name="accounts_onboarding_token_hash_uq",
            ),
            models.CheckConstraint(
                condition=Q(
                    status__in=[
                        "DRAFT",
                        "INVITE_PENDING",
                        "INVITED",
                        "ACTIVATED",
                        "EXPIRED",
                        "REVOKED",
                    ]
                ),
                name="accounts_onboarding_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(role__in=["SUPERADMIN", "ADMIN", "USER"]),
                name="accounts_onboarding_role_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["invite_expires_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.onboarding_code} — {self.login_email}"

    def save(self, *args, **kwargs):
        self.login_email = (self.login_email or "").strip().lower()
        if not self.onboarding_code:
            self.onboarding_code = next_onboarding_code()
        super().save(*args, **kwargs)


class UserAccessEvent(models.Model):
    """Append-only audit trail for onboarding and ERP account access changes."""

    class Event(models.TextChoices):
        ONBOARDING_CREATED = "ONBOARDING_CREATED", _("Onboarding created")
        DRAFT_UPDATED = "DRAFT_UPDATED", _("Draft updated")
        DRAFT_DISCARDED = "DRAFT_DISCARDED", _("Draft discarded")
        INVITE_QUEUED = "INVITE_QUEUED", _("Invitation queued")
        INVITE_RESENT = "INVITE_RESENT", _("Invitation resent")
        INVITE_SENT = "INVITE_SENT", _("Invitation email sent")
        INVITE_FAILED = "INVITE_FAILED", _("Invitation email failed")
        INVITE_REVOKED = "INVITE_REVOKED", _("Invitation revoked")
        INVITE_EXPIRED = "INVITE_EXPIRED", _("Invitation expired")
        ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED", _("Account activated")
        USER_DEACTIVATED = "USER_DEACTIVATED", _("User deactivated")
        USER_REACTIVATED = "USER_REACTIVATED", _("User reactivated")
        ROLE_CHANGED = "ROLE_CHANGED", _("Role changed")
        MODULE_ACCESS_CHANGED = "MODULE_ACCESS_CHANGED", _("Module access changed")
        SUBMODULE_ACCESS_CHANGED = "SUBMODULE_ACCESS_CHANGED", _("Submodule access changed")
        ACTION_PERMISSION_CHANGED = "ACTION_PERMISSION_CHANGED", _("Action permission changed")
        ACCESS_MIGRATED = "ACCESS_MIGRATED", _("Access migrated")

    event = models.CharField(max_length=40, choices=Event.choices)
    # Access key affected by permission events, e.g. "PROCUREMENT", "PROCUREMENT.RFQ" or
    # "PROCUREMENT.RFQ.CREATE".
    permission = models.CharField(max_length=120, blank=True, default="")
    onboarding = models.ForeignKey(
        UserOnboarding,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_events",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_actions",
    )
    from_value = models.CharField(max_length=64, blank=True, default="")
    to_value = models.CharField(max_length=64, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event} @ {self.created_at:%Y-%m-%d %H:%M}"


class AccessAuditFields(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        abstract = True


class UserModuleAccess(AccessAuditFields):
    """Whether a module is switched on for a user. Superadmins need no rows (full override)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="module_access")
    module_key = models.CharField(max_length=40)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ("module_key",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "module_key"], name="accounts_user_module_access_uq"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.module_key}"


class UserSubmoduleAccess(AccessAuditFields):
    """Action permissions for one submodule. Effective only while its module is enabled."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submodule_access")
    module_key = models.CharField(max_length=40)
    submodule_key = models.CharField(max_length=40)
    is_enabled = models.BooleanField(default=True)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    can_cancel = models.BooleanField(default=False)
    can_upload = models.BooleanField(default=False)
    can_activate_deactivate = models.BooleanField(default=False)

    class Meta:
        ordering = ("module_key", "submodule_key")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "module_key", "submodule_key"],
                name="accounts_user_submodule_access_uq",
            ),
        ]
        indexes = [models.Index(fields=["user", "module_key"])]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.module_key}.{self.submodule_key}"

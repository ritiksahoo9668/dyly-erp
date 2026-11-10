"""User Onboarding business rules: state transitions, invitation tokens and account access.

Every status change happens through a function in this module; views never set status.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from apps.common.access_control.services import apply_pending_access, set_pending_access
from apps.common.mail.constants import SUBJECTS, MailType
from apps.common.mail.context import frontend_url
from apps.common.mail.services import create_mail_log, enqueue_on_commit
from apps.master.models import Employee

from .models import User, UserAccessEvent, UserOnboarding
from .permissions import can_manage_role
from .tokens import generate_raw_token, hash_token

Status = UserOnboarding.Status
MailStatus = UserOnboarding.MailStatus
Event = UserAccessEvent.Event
Role = User.Role

SEND_FROM = frozenset({Status.DRAFT})
RESEND_FROM = frozenset({Status.INVITE_PENDING, Status.INVITED, Status.EXPIRED, Status.REVOKED})
REVOKE_FROM = frozenset({Status.INVITE_PENDING, Status.INVITED, Status.EXPIRED})
TOKEN_USABLE = frozenset({Status.INVITE_PENDING, Status.INVITED})

MAX_TOKEN_LENGTH = 256
EMAIL_IN_ONBOARDING = "This login email is already used by another onboarding."
EMAIL_IN_USE = "This login email already belongs to an ERP user."


class OnboardingConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This action is not allowed in the current state."
    default_code = "conflict"


class ActivationTokenInvalid(Exception):
    pass


class ActivationTokenExpired(Exception):
    pass


@dataclass(frozen=True)
class TokenCheck:
    state: str  # "valid" | "expired" | "invalid"
    onboarding: UserOnboarding | None = None


# --- Helpers ---------------------------------------------------------------------------


def invite_ttl() -> timedelta:
    return timedelta(hours=settings.USER_INVITE_EXPIRY_HOURS)


def build_activation_url(raw_token: str) -> str:
    return frontend_url(f"activate-account/{raw_token}")


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").split()
    if not parts:
        return "", ""
    return parts[0][:150], " ".join(parts[1:])[:150]


def _actor(user):
    return user if user is not None and user.is_authenticated else None


def record_event(
    event: str,
    *,
    onboarding: UserOnboarding | None = None,
    user: User | None = None,
    actor=None,
    from_value: str = "",
    to_value: str = "",
    ip: str | None = None,
) -> UserAccessEvent:
    if user is None and onboarding is not None:
        user = onboarding.user
    return UserAccessEvent.objects.create(
        event=event,
        onboarding=onboarding,
        user=user,
        actor=_actor(actor),
        from_value=from_value,
        to_value=to_value,
        ip_address=ip,
    )


def ensure_can_manage(actor, role: str) -> None:
    if not can_manage_role(actor, role):
        label = Role(role).label if role in Role.values else role
        raise PermissionDenied(f"You are not allowed to manage accounts with the {label} role.")


def _lock(onboarding_id: int) -> UserOnboarding:
    return (
        UserOnboarding.objects.select_for_update(of=("self",))
        .select_related("employee", "user")
        .get(pk=onboarding_id)
    )


def validate_login_email_available(
    email: str,
    *,
    exclude_onboarding: UserOnboarding | None = None,
    exclude_user: User | None = None,
) -> str:
    email = normalize_email(email)
    onboardings = UserOnboarding.objects.filter(is_active=True, login_email__iexact=email)
    if exclude_onboarding is not None:
        onboardings = onboardings.exclude(pk=exclude_onboarding.pk)
    if onboardings.exists():
        raise ValidationError({"login_email": EMAIL_IN_ONBOARDING})
    users = User.objects.filter(email__iexact=email)
    if exclude_user is not None:
        users = users.exclude(pk=exclude_user.pk)
    if users.exists():
        raise ValidationError({"login_email": EMAIL_IN_USE})
    return email


def validate_employee_available(
    employee: Employee, *, exclude_onboarding: UserOnboarding | None = None
) -> None:
    if not employee.is_active:
        raise ValidationError({"employee_id": "Inactive employees cannot be onboarded."})
    existing = UserOnboarding.objects.filter(is_active=True, employee=employee)
    if exclude_onboarding is not None:
        existing = existing.exclude(pk=exclude_onboarding.pk)
    if existing.exists():
        raise ValidationError({"employee_id": "This employee already has an ERP user onboarding."})


def _save_guarded(instance, **kwargs) -> None:
    """Save, turning a lost race on the partial unique constraints into a validation error."""
    try:
        with transaction.atomic():
            instance.save(**kwargs)
    except IntegrityError as exc:
        raise ValidationError(
            {"detail": "This employee or login email is already linked to another ERP user."}
        ) from exc


# --- Draft lifecycle -------------------------------------------------------------------


@transaction.atomic
def create_onboarding(
    *,
    employee: Employee,
    login_email: str,
    role: str,
    actor,
    ip: str | None = None,
    access: dict | None = None,
) -> UserOnboarding:
    ensure_can_manage(actor, role)
    employee = Employee.objects.select_for_update().get(pk=employee.pk)
    validate_employee_available(employee)
    email = validate_login_email_available(login_email)
    onboarding = UserOnboarding(
        employee=employee,
        login_email=email,
        role=role,
        created_by=_actor(actor),
        updated_by=_actor(actor),
    )
    _save_guarded(onboarding)
    record_event(Event.ONBOARDING_CREATED, onboarding=onboarding, actor=actor, to_value=role, ip=ip)
    if access is not None and set_pending_access(onboarding, access, actor=actor, ip=ip):
        onboarding.save(update_fields=["pending_access", "updated_at"])
    return onboarding


@transaction.atomic
def update_draft(
    onboarding: UserOnboarding,
    *,
    actor,
    ip: str | None = None,
    employee: Employee | None = None,
    login_email: str | None = None,
    role: str | None = None,
    access: dict | None = None,
) -> UserOnboarding:
    onboarding = _lock(onboarding.pk)
    ensure_can_manage(actor, onboarding.role)
    if onboarding.status != Status.DRAFT:
        raise OnboardingConflict("Only draft onboardings can be edited.")

    changed = False
    if employee is not None and employee.pk != onboarding.employee_id:
        validate_employee_available(employee, exclude_onboarding=onboarding)
        onboarding.employee = employee
        changed = True
    if login_email is not None and normalize_email(login_email) != onboarding.login_email:
        onboarding.login_email = validate_login_email_available(
            login_email, exclude_onboarding=onboarding
        )
        changed = True
    if role is not None and role != onboarding.role:
        ensure_can_manage(actor, role)
        record_event(
            Event.ROLE_CHANGED,
            onboarding=onboarding,
            actor=actor,
            from_value=onboarding.role,
            to_value=role,
            ip=ip,
        )
        onboarding.role = role
        changed = True
        if access is None:
            # Re-normalise so a switch to Superadmin drops the now-irrelevant draft access.
            access = onboarding.pending_access
    if access is not None and set_pending_access(onboarding, access, actor=actor, ip=ip):
        changed = True

    if changed:
        onboarding.updated_by = _actor(actor)
        _save_guarded(onboarding)
        record_event(Event.DRAFT_UPDATED, onboarding=onboarding, actor=actor, ip=ip)
    return onboarding


@transaction.atomic
def discard_draft(onboarding: UserOnboarding, *, actor, ip: str | None = None) -> None:
    onboarding = _lock(onboarding.pk)
    ensure_can_manage(actor, onboarding.role)
    if onboarding.status != Status.DRAFT:
        raise OnboardingConflict("Only draft onboardings can be discarded.")
    onboarding.is_active = False
    onboarding.updated_by = _actor(actor)
    onboarding.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_event(Event.DRAFT_DISCARDED, onboarding=onboarding, actor=actor, ip=ip)


# --- Invitations -----------------------------------------------------------------------


def _ensure_account(onboarding: UserOnboarding) -> User:
    """Create the inactive ERP user for this onboarding once; never duplicates on resend."""
    if onboarding.user is not None:
        if onboarding.user.is_active:
            raise OnboardingConflict("This ERP account is already active.")
        return onboarding.user
    email = validate_login_email_available(onboarding.login_email, exclude_onboarding=onboarding)
    first_name, last_name = split_name(onboarding.employee.full_name)
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=onboarding.role,
        is_active=False,
    )
    user.set_unusable_password()
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError as exc:
        raise ValidationError({"login_email": EMAIL_IN_USE}) from exc
    onboarding.user = user
    apply_pending_access(onboarding, user)
    return user


@transaction.atomic
def queue_invitation(
    onboarding: UserOnboarding, *, actor, ip: str | None = None, resend: bool = False
) -> UserOnboarding:
    """Invalidate any previous token and queue a fresh invitation email after commit.

    The activation token itself is generated by the Celery worker so the raw token never
    travels through the broker.
    """
    from .tasks import send_user_onboarding_email_task

    onboarding = _lock(onboarding.pk)
    ensure_can_manage(actor, onboarding.role)
    allowed = RESEND_FROM if resend else SEND_FROM
    if not onboarding.is_active or onboarding.status not in allowed:
        if resend:
            raise OnboardingConflict("The invitation cannot be resent in its current status.")
        raise OnboardingConflict("The invitation has already been sent. Use Resend Invite instead.")
    if not onboarding.employee.is_active:
        raise OnboardingConflict("The employee is inactive. Activate the employee before inviting.")

    _ensure_account(onboarding)
    previous_status = onboarding.status
    onboarding.status = Status.INVITE_PENDING
    onboarding.invite_version += 1
    onboarding.invite_token_hash = ""
    onboarding.invite_expires_at = None
    onboarding.invite_send_count += 1
    onboarding.last_mail_status = MailStatus.QUEUED
    onboarding.updated_by = _actor(actor)
    onboarding.save()

    mail_log = create_mail_log(
        mail_type=MailType.USER_ONBOARDING_INVITE,
        recipient=onboarding.login_email,
        subject=SUBJECTS[MailType.USER_ONBOARDING_INVITE],
        related_object=onboarding,
    )
    onboarding_id = onboarding.pk
    version = onboarding.invite_version
    enqueue_on_commit(
        send_user_onboarding_email_task,
        mail_log,
        onboarding_id,
        version,
        on_enqueue_error=lambda _exc: mark_invite_failed(onboarding_id, version),
    )
    record_event(
        Event.INVITE_RESENT if resend else Event.INVITE_QUEUED,
        onboarding=onboarding,
        actor=actor,
        from_value=previous_status,
        to_value=Status.INVITE_PENDING,
        ip=ip,
    )
    return onboarding


@transaction.atomic
def issue_invite_token(
    onboarding_id: int, invite_version: int
) -> tuple[UserOnboarding, str] | None:
    """Generate the activation token for a queued invitation (worker side).

    Returns None when the invitation was superseded, revoked or discarded meanwhile.
    """
    try:
        onboarding = _lock(onboarding_id)
    except UserOnboarding.DoesNotExist:
        return None
    if (
        not onboarding.is_active
        or onboarding.invite_version != invite_version
        or onboarding.status != Status.INVITE_PENDING
    ):
        return None
    raw_token = generate_raw_token()
    onboarding.invite_token_hash = hash_token(raw_token)
    onboarding.invite_expires_at = timezone.now() + invite_ttl()
    onboarding.save(update_fields=["invite_token_hash", "invite_expires_at", "updated_at"])
    return onboarding, raw_token


@transaction.atomic
def mark_invite_sent(onboarding_id: int, invite_version: int) -> bool:
    onboarding = _lock(onboarding_id)
    if onboarding.invite_version != invite_version or onboarding.status != Status.INVITE_PENDING:
        return False
    now = timezone.now()
    onboarding.status = Status.INVITED
    onboarding.invite_sent_at = onboarding.invite_sent_at or now
    onboarding.last_invite_sent_at = now
    onboarding.last_mail_status = MailStatus.SENT
    onboarding.save(
        update_fields=[
            "status",
            "invite_sent_at",
            "last_invite_sent_at",
            "last_mail_status",
            "updated_at",
        ]
    )
    record_event(
        Event.INVITE_SENT,
        onboarding=onboarding,
        from_value=Status.INVITE_PENDING,
        to_value=Status.INVITED,
    )
    return True


@transaction.atomic
def mark_invite_failed(onboarding_id: int, invite_version: int) -> bool:
    """Keep the onboarding retryable (INVITE_PENDING) and drop the undelivered token."""
    onboarding = _lock(onboarding_id)
    if onboarding.invite_version != invite_version or onboarding.status != Status.INVITE_PENDING:
        return False
    onboarding.last_mail_status = MailStatus.FAILED
    onboarding.invite_token_hash = ""
    onboarding.save(update_fields=["last_mail_status", "invite_token_hash", "updated_at"])
    record_event(Event.INVITE_FAILED, onboarding=onboarding)
    return True


@transaction.atomic
def revoke_invitation(
    onboarding: UserOnboarding, *, actor, ip: str | None = None
) -> UserOnboarding:
    onboarding = _lock(onboarding.pk)
    ensure_can_manage(actor, onboarding.role)
    if not onboarding.is_active or onboarding.status not in REVOKE_FROM:
        raise OnboardingConflict("Only pending, invited or expired invitations can be revoked.")
    previous_status = onboarding.status
    onboarding.status = Status.REVOKED
    onboarding.revoked_at = timezone.now()
    onboarding.invite_token_hash = ""
    onboarding.invite_version += 1
    onboarding.updated_by = _actor(actor)
    onboarding.save()
    record_event(
        Event.INVITE_REVOKED,
        onboarding=onboarding,
        actor=actor,
        from_value=previous_status,
        to_value=Status.REVOKED,
        ip=ip,
    )
    return onboarding


def _mark_expired(onboarding: UserOnboarding) -> None:
    previous_status = onboarding.status
    onboarding.status = Status.EXPIRED
    onboarding.save(update_fields=["status", "updated_at"])
    record_event(
        Event.INVITE_EXPIRED,
        onboarding=onboarding,
        from_value=previous_status,
        to_value=Status.EXPIRED,
    )


@transaction.atomic
def expire_stale_invitations() -> int:
    """Mark invitations whose activation window has passed as EXPIRED."""
    stale = list(
        UserOnboarding.objects.select_for_update(skip_locked=True).filter(
            is_active=True,
            status=Status.INVITED,
            invite_expires_at__lte=timezone.now(),
        )
    )
    for onboarding in stale:
        _mark_expired(onboarding)
    return len(stale)


# --- Public activation -----------------------------------------------------------------


def _find_by_token(raw_token: str, *, lock: bool = False) -> UserOnboarding | None:
    if not raw_token or len(raw_token) > MAX_TOKEN_LENGTH:
        return None
    qs = UserOnboarding.objects.select_related("employee", "user")
    if lock:
        qs = qs.select_for_update(of=("self",))
    return qs.filter(invite_token_hash=hash_token(raw_token), is_active=True).first()


def _token_state(onboarding: UserOnboarding | None) -> str:
    if onboarding is None:
        return "invalid"
    if onboarding.status in TOKEN_USABLE:
        expires_at = onboarding.invite_expires_at
        if expires_at is None or expires_at <= timezone.now():
            return "expired"
        return "valid"
    if onboarding.status == Status.EXPIRED:
        return "expired"
    return "invalid"


@transaction.atomic
def check_activation_token(raw_token: str) -> TokenCheck:
    onboarding = _find_by_token(raw_token, lock=True)
    state = _token_state(onboarding)
    if state == "expired" and onboarding.status != Status.EXPIRED:
        _mark_expired(onboarding)
    return TokenCheck(state, onboarding if state == "valid" else None)


def activate_account(raw_token: str, password: str, *, ip: str | None = None) -> UserOnboarding:
    """Set the invitee's password and activate the linked ERP user (single use).

    Raises ActivationTokenInvalid / ActivationTokenExpired, or a DRF ValidationError when the
    password fails the configured password validators.
    """
    expired = False
    with transaction.atomic():
        onboarding = _find_by_token(raw_token, lock=True)
        state = _token_state(onboarding)
        if state == "expired":
            if onboarding.status != Status.EXPIRED:
                _mark_expired(onboarding)
            expired = True
        elif state == "valid" and onboarding.user is not None:
            user = onboarding.user
            try:
                validate_password(password, user=user)
            except DjangoValidationError as exc:
                raise ValidationError({"password": list(exc.messages)}) from exc
            user.set_password(password)
            user.is_active = True
            user.role = onboarding.role
            user.save(update_fields=["password", "is_active", "role"])

            previous_status = onboarding.status
            onboarding.status = Status.ACTIVATED
            onboarding.activated_at = timezone.now()
            onboarding.invite_token_hash = ""
            onboarding.save(
                update_fields=["status", "activated_at", "invite_token_hash", "updated_at"]
            )
            record_event(
                Event.ACCOUNT_ACTIVATED,
                onboarding=onboarding,
                user=user,
                actor=user,
                from_value=previous_status,
                to_value=Status.ACTIVATED,
                ip=ip,
            )
            return onboarding
    if expired:
        raise ActivationTokenExpired
    raise ActivationTokenInvalid


# --- Account administration (after activation) -----------------------------------------


def _onboarding_for(user: User) -> UserOnboarding | None:
    return UserOnboarding.objects.filter(user=user).first()


def _has_other_active_superadmin(user: User) -> bool:
    return User.objects.filter(role=Role.SUPERADMIN, is_active=True).exclude(pk=user.pk).exists()


@transaction.atomic
def set_user_active(target: User, active: bool, *, actor, ip: str | None = None) -> User:
    target = User.objects.select_for_update().get(pk=target.pk)
    ensure_can_manage(actor, target.role)
    if target.pk == actor.pk:
        raise OnboardingConflict("You cannot change the status of your own account.")
    if target.is_active == active:
        return target

    onboarding = _onboarding_for(target)
    if active:
        activation_complete = target.has_usable_password() and (
            onboarding is None or onboarding.status == Status.ACTIVATED
        )
        if not activation_complete:
            raise OnboardingConflict(
                "This user has not completed account activation. Use the onboarding invitation."
            )
    elif target.role == Role.SUPERADMIN and not _has_other_active_superadmin(target):
        raise OnboardingConflict("At least one active Superadmin account is required.")

    target.is_active = active
    target.save(update_fields=["is_active"])
    record_event(
        Event.USER_REACTIVATED if active else Event.USER_DEACTIVATED,
        onboarding=onboarding,
        user=target,
        actor=actor,
        from_value="ACTIVE" if not active else "INACTIVE",
        to_value="ACTIVE" if active else "INACTIVE",
        ip=ip,
    )
    return target


@transaction.atomic
def change_user_role(target: User, new_role: str, *, actor, ip: str | None = None) -> User:
    target = User.objects.select_for_update().get(pk=target.pk)
    if new_role not in Role.values:
        raise ValidationError({"role": "Select a valid role."})
    ensure_can_manage(actor, target.role)
    ensure_can_manage(actor, new_role)
    if target.pk == actor.pk:
        raise OnboardingConflict("You cannot change your own role.")
    if target.role == new_role:
        return target
    if (
        target.role == Role.SUPERADMIN
        and target.is_active
        and not _has_other_active_superadmin(target)
    ):
        raise OnboardingConflict("At least one active Superadmin account is required.")

    previous_role = target.role
    target.role = new_role
    target.save(update_fields=["role"])
    onboarding = _onboarding_for(target)
    if onboarding is not None:
        onboarding.role = new_role
        onboarding.updated_by = _actor(actor)
        onboarding.save(update_fields=["role", "updated_by", "updated_at"])
    record_event(
        Event.ROLE_CHANGED,
        onboarding=onboarding,
        user=target,
        actor=actor,
        from_value=previous_role,
        to_value=new_role,
        ip=ip,
    )
    return target


# --- Allowed actions (drive the UI; every action is re-checked server-side) -------------


def onboarding_actions(onboarding: UserOnboarding, actor) -> list[str]:
    actions = ["view"]
    if not onboarding.is_active or not can_manage_role(actor, onboarding.role):
        return actions
    current = onboarding.status
    if current == Status.DRAFT:
        actions += ["edit", "send_invite", "discard"]
    if current in RESEND_FROM:
        actions.append("resend_invite")
    if current in REVOKE_FROM:
        actions.append("revoke")
    user = onboarding.user
    if current == Status.ACTIVATED and user is not None and user.pk != actor.pk:
        actions.append("deactivate_user" if user.is_active else "activate_user")
    if user is not None and user.pk != actor.pk and onboarding.role != Role.SUPERADMIN:
        actions.append("edit_access")
    return actions


def user_actions(target: User, actor, onboarding: UserOnboarding | None) -> list[str]:
    if target.pk == actor.pk or not can_manage_role(actor, target.role):
        return []
    actions = ["change_role"]
    if target.role != Role.SUPERADMIN:
        actions.append("edit_access")
    if target.is_active:
        actions.append("deactivate")
    elif target.has_usable_password() and (
        onboarding is None or onboarding.status == Status.ACTIVATED
    ):
        actions.append("activate")
    return actions

"""Assign and update Module / Submodule / Action access, with escalation checks and audit.

Canonical access shape (API input/output and UserOnboarding.pending_access):

    {"PROCUREMENT": {"enabled": true, "submodules": {"RFQ": ["VIEW", "CREATE"]}}}

Submodules are listed only when at least one action is granted; any granted action implies VIEW.
"""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import (
    User,
    UserAccessEvent,
    UserModuleAccess,
    UserOnboarding,
    UserSubmoduleAccess,
)
from apps.accounts.permissions import can_manage_role

from .constants import ACTION_FIELDS, Action
from .registry import MODULES, get_module
from .selectors import clear_cached_access, get_effective_access

Event = UserAccessEvent.Event
Role = User.Role

ON, OFF = "ON", "OFF"
MAX_DENIED_IN_MESSAGE = 5


def _invalid(message: str) -> ValidationError:
    return ValidationError({"access": [message]})


def normalize_access(raw) -> dict:
    """Validate ``raw`` against the registry and return it in canonical, registry order."""
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise _invalid("Access must be an object keyed by module.")

    for module_key in raw:
        if get_module(module_key) is None:
            raise _invalid(f"Unknown module: {module_key}.")

    result: dict = {}
    for module in MODULES:
        if module.key not in raw:
            continue
        value = raw[module.key]
        if not isinstance(value, dict):
            raise _invalid(f"{module.label}: access must be an object.")
        enabled = value.get("enabled", False)
        if not isinstance(enabled, bool):
            raise _invalid(f"{module.label}: 'enabled' must be true or false.")
        subs_raw = value.get("submodules") or {}
        if not isinstance(subs_raw, dict):
            raise _invalid(f"{module.label}: 'submodules' must be an object.")
        for sub_key in subs_raw:
            if module.submodule(sub_key) is None:
                raise _invalid(f"{module.label}: unknown submodule {sub_key}.")

        submodules: dict[str, list[str]] = {}
        for sub in module.submodules:
            actions = subs_raw.get(sub.key)
            if actions is None:
                continue
            if not isinstance(actions, list):
                raise _invalid(f"{module.label} / {sub.label}: actions must be a list.")
            chosen = set()
            for action in actions:
                if action not in sub.actions:
                    raise _invalid(f"{module.label} / {sub.label} does not support {action}.")
                chosen.add(action)
            if chosen:
                chosen.add(Action.VIEW)
                submodules[sub.key] = [a for a in sub.actions if a in chosen]

        if enabled or submodules:
            result[module.key] = {"enabled": enabled, "submodules": submodules}
    return result


def _flatten(access: dict) -> dict[str, bool]:
    flat: dict[str, bool] = {}
    for module in MODULES:
        entry = access.get(module.key) or {}
        flat[module.key] = bool(entry.get("enabled"))
        submodules = entry.get("submodules") or {}
        for sub in module.submodules:
            actions = set(submodules.get(sub.key) or [])
            flat[f"{module.key}.{sub.key}"] = bool(actions)
            for action in sub.actions:
                flat[f"{module.key}.{sub.key}.{action}"] = action in actions
    return flat


def diff_access(old: dict, new: dict) -> list[tuple[str, bool, bool]]:
    before, after = _flatten(old), _flatten(new)
    return [(key, before[key], after[key]) for key in after if before[key] != after[key]]


def _event_for(key: str) -> str:
    depth = key.count(".")
    if depth == 0:
        return Event.MODULE_ACCESS_CHANGED
    if depth == 1:
        return Event.SUBMODULE_ACCESS_CHANGED
    return Event.ACTION_PERMISSION_CHANGED


def _ensure_actor_can_grant(actor, changes: list[tuple[str, bool, bool]]) -> None:
    """Non-Superadmins may only change permissions they hold themselves."""
    access = get_effective_access(actor)
    if access.full_access:
        return
    denied = []
    for key, _old, _new in changes:
        parts = key.split(".")
        if len(parts) == 1:
            allowed = access.has_module(parts[0])
        elif len(parts) == 2:
            allowed = access.can(parts[0], parts[1], Action.VIEW)
        else:
            allowed = access.can(parts[0], parts[1], parts[2])
        if not allowed:
            denied.append(key)
    if denied:
        shown = ", ".join(denied[:MAX_DENIED_IN_MESSAGE])
        more = len(denied) - MAX_DENIED_IN_MESSAGE
        suffix = f" and {more} more" if more > 0 else ""
        raise PermissionDenied(
            f"You cannot grant or change access you do not have yourself: {shown}{suffix}."
        )


def _record_changes(changes, *, user=None, onboarding=None, actor=None, ip=None) -> None:
    actor = actor if actor is not None and actor.is_authenticated else None
    UserAccessEvent.objects.bulk_create(
        [
            UserAccessEvent(
                event=_event_for(key),
                permission=key,
                from_value=ON if old else OFF,
                to_value=ON if new else OFF,
                onboarding=onboarding,
                user=user,
                actor=actor,
                ip_address=ip,
            )
            for key, old, new in changes
        ]
    )


def user_access_snapshot(user: User) -> dict:
    """Stored access for ``user`` in canonical shape (kept even while a module is disabled)."""
    module_rows = dict(
        UserModuleAccess.objects.filter(user=user).values_list("module_key", "is_enabled")
    )
    sub_rows = UserSubmoduleAccess.objects.filter(user=user, is_enabled=True).values(
        "module_key", "submodule_key", *ACTION_FIELDS.values()
    )
    granted: dict[str, dict[str, list[str]]] = {}
    for row in sub_rows:
        module = get_module(row["module_key"])
        sub = module.submodule(row["submodule_key"]) if module else None
        if sub is None:
            continue
        actions = [a for a in sub.actions if row[ACTION_FIELDS[a]]]
        if actions:
            granted.setdefault(module.key, {})[sub.key] = actions

    raw = {
        key: {"enabled": bool(module_rows.get(key)), "submodules": granted.get(key, {})}
        for key in {*module_rows, *granted}
        if get_module(key) is not None
    }
    return normalize_access(raw)


def _write_user_access(user: User, access: dict, *, actor) -> None:
    actor = actor if actor is not None and actor.is_authenticated else None
    modules = {row.module_key: row for row in UserModuleAccess.objects.filter(user=user)}
    subs = {
        (row.module_key, row.submodule_key): row
        for row in UserSubmoduleAccess.objects.filter(user=user)
    }
    for module in MODULES:
        entry = access.get(module.key)
        enabled = bool(entry and entry["enabled"])
        row = modules.get(module.key)
        if row is None:
            if entry is not None:
                UserModuleAccess.objects.create(
                    user=user,
                    module_key=module.key,
                    is_enabled=enabled,
                    created_by=actor,
                    updated_by=actor,
                )
        elif row.is_enabled != enabled:
            row.is_enabled = enabled
            row.updated_by = actor
            row.save(update_fields=["is_enabled", "updated_by", "updated_at"])

        granted = (entry or {}).get("submodules") or {}
        for sub in module.submodules:
            actions = set(granted.get(sub.key) or [])
            desired = {field: action in actions for action, field in ACTION_FIELDS.items()}
            sub_row = subs.get((module.key, sub.key))
            if sub_row is None:
                if actions:
                    UserSubmoduleAccess.objects.create(
                        user=user,
                        module_key=module.key,
                        submodule_key=sub.key,
                        is_enabled=True,
                        created_by=actor,
                        updated_by=actor,
                        **desired,
                    )
                continue
            changed = [f for f, value in desired.items() if getattr(sub_row, f) != value]
            if sub_row.is_enabled != bool(actions):
                changed.append("is_enabled")
            if changed:
                for field_name, value in desired.items():
                    setattr(sub_row, field_name, value)
                sub_row.is_enabled = bool(actions)
                sub_row.updated_by = actor
                sub_row.save(update_fields=[*changed, "updated_by", "updated_at"])


@transaction.atomic
def set_user_access(target: User, access, *, actor, ip: str | None = None) -> dict:
    """Replace ``target``'s module access. Returns the saved canonical access."""
    target = User.objects.select_for_update().get(pk=target.pk)
    if target.pk == actor.pk:
        raise PermissionDenied("You cannot change your own access.")
    if not can_manage_role(actor, target.role):
        raise PermissionDenied("You are not allowed to manage this user's access.")
    if target.role == Role.SUPERADMIN:
        raise ValidationError(
            {"access": ["Superadmin accounts have full system access and need no module access."]}
        )

    new = normalize_access(access)
    changes = diff_access(user_access_snapshot(target), new)
    if not changes:
        return new
    _ensure_actor_can_grant(actor, changes)
    _write_user_access(target, new, actor=actor)
    onboarding = UserOnboarding.objects.filter(user=target).first()
    _record_changes(changes, user=target, onboarding=onboarding, actor=actor, ip=ip)
    clear_cached_access(target)
    return new


def set_pending_access(onboarding: UserOnboarding, access, *, actor, ip: str | None = None) -> bool:
    """Set a draft onboarding's access (caller saves). Returns True when it changed."""
    new = {} if onboarding.role == Role.SUPERADMIN else normalize_access(access)
    changes = diff_access(onboarding.pending_access or {}, new)
    if not changes:
        return False
    _ensure_actor_can_grant(actor, changes)
    onboarding.pending_access = new
    _record_changes(changes, onboarding=onboarding, actor=actor, ip=ip)
    return True


def apply_pending_access(onboarding: UserOnboarding, user: User) -> None:
    """Materialise a draft's access for its newly created (still inactive) ERP user."""
    if onboarding.role == Role.SUPERADMIN or not onboarding.pending_access:
        return
    _write_user_access(
        user, normalize_access(onboarding.pending_access), actor=onboarding.updated_by
    )


def onboarding_access(onboarding: UserOnboarding) -> dict:
    """Access to display for an onboarding: the user's stored access once the account exists."""
    if onboarding.user_id is not None:
        return user_access_snapshot(onboarding.user)
    return normalize_access(onboarding.pending_access or {})

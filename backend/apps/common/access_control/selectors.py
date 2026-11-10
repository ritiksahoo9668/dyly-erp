"""Effective-access queries. Evaluation order:

active user -> global role override (Superadmin) -> module enabled -> submodule enabled
-> action permitted. Workflow/document authority is a separate, later check.
"""

from dataclasses import dataclass, field

from .constants import ACTION_FIELDS, Action
from .registry import MODULES, get_module

_CACHE_ATTR = "_erp_effective_access"


@dataclass(frozen=True)
class EffectiveAccess:
    full_access: bool = False
    # module key -> submodule key -> granted actions (only enabled modules/submodules appear).
    modules: dict[str, dict[str, frozenset[str]]] = field(default_factory=dict)

    def can(self, module: str, submodule: str | None = None, action: str = Action.VIEW) -> bool:
        if self.full_access:
            return get_module(module) is not None
        submodules = self.modules.get(module)
        if not submodules:
            return False
        if submodule is None:
            return any(action in actions for actions in submodules.values())
        return action in submodules.get(submodule, frozenset())

    def has_module(self, module: str) -> bool:
        return self.can(module, None, Action.VIEW)


NO_ACCESS = EffectiveAccess()
FULL_ACCESS = EffectiveAccess(full_access=True)


def _is_superadmin(user) -> bool:
    from apps.accounts.models import User

    return user.role == User.Role.SUPERADMIN


def compute_effective_access(user) -> EffectiveAccess:
    from apps.accounts.models import UserModuleAccess, UserSubmoduleAccess

    if user is None or not user.is_authenticated or not user.is_active:
        return NO_ACCESS
    if _is_superadmin(user):
        return FULL_ACCESS

    enabled_modules = UserModuleAccess.objects.filter(user=user, is_enabled=True).values(
        "module_key"
    )
    rows = UserSubmoduleAccess.objects.filter(
        user=user, is_enabled=True, module_key__in=enabled_modules
    ).values("module_key", "submodule_key", *ACTION_FIELDS.values())

    modules: dict[str, dict[str, frozenset[str]]] = {}
    for row in rows:
        module = get_module(row["module_key"])
        sub = module.submodule(row["submodule_key"]) if module else None
        if sub is None or not row["can_view"]:
            continue
        actions = frozenset(
            action for action in sub.actions if row[ACTION_FIELDS[action]]
        )
        modules.setdefault(module.key, {})[sub.key] = actions
    return EffectiveAccess(modules=modules)


def get_effective_access(user) -> EffectiveAccess:
    """Effective access, memoised on the user instance (one instance per request)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return NO_ACCESS
    cached = getattr(user, _CACHE_ATTR, None)
    if cached is None:
        cached = compute_effective_access(user)
        setattr(user, _CACHE_ATTR, cached)
    return cached


def clear_cached_access(user) -> None:
    if user is not None and hasattr(user, _CACHE_ATTR):
        delattr(user, _CACHE_ATTR)


def access_payload(user) -> dict:
    """Current-user access for the frontend (Superadmin is not enumerated)."""
    access = get_effective_access(user)
    if access.full_access:
        return {"full_access": True, "modules": {}}
    payload: dict[str, dict] = {}
    for module in MODULES:
        granted = access.modules.get(module.key)
        if not granted:
            continue
        payload[module.key] = {
            "nav_id": module.nav_id,
            "submodules": {
                sub.key: {
                    "nav_id": sub.nav_id,
                    "actions": [a for a in sub.actions if a in granted[sub.key]],
                }
                for sub in module.submodules
                if sub.key in granted
            },
        }
    return {"full_access": False, "modules": payload}

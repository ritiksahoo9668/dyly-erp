"""Test helpers for granting module access without going through the audited service."""

from .constants import ACTION_FIELDS
from .registry import get_module
from .selectors import clear_cached_access


def grant_access(user, module_key: str, submodules: dict[str, list[str]] | None = None) -> None:
    """Enable ``module_key`` and grant actions per submodule (``None`` = every action)."""
    from apps.accounts.models import UserModuleAccess, UserSubmoduleAccess

    module = get_module(module_key)
    UserModuleAccess.objects.update_or_create(
        user=user, module_key=module.key, defaults={"is_enabled": True}
    )
    for sub in module.submodules:
        if submodules is not None and sub.key not in submodules:
            continue
        actions = set(sub.actions if submodules is None else submodules[sub.key]) | {"VIEW"}
        flags = {field: action in actions for action, field in ACTION_FIELDS.items()}
        UserSubmoduleAccess.objects.update_or_create(
            user=user,
            module_key=module.key,
            submodule_key=sub.key,
            defaults={"is_enabled": True, **flags},
        )
    clear_cached_access(user)

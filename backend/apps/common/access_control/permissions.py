"""DRF permission classes and helpers for Module -> Submodule -> Action access.

Views declare what they protect instead of checking roles:

    class IndentViewSet(ModelViewSet):
        permission_classes = [IsAuthenticated, ModuleAccessPermission]
        access_module = Module.PROCUREMENT
        access_submodule = "INDENT"

The frontend is never trusted: every protected API action is resolved to an action key here.
"""

from collections.abc import Callable

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .constants import Action
from .selectors import get_effective_access

# Sentinel for view actions any active user may call (e.g. Master reference lookups).
OPEN = "OPEN"

DEFAULT_ACTION_MAP: dict[str, str] = {
    "list": Action.VIEW,
    "retrieve": Action.VIEW,
    "create": Action.CREATE,
    "update": Action.EDIT,
    "partial_update": Action.EDIT,
    "export": Action.EXPORT,
    "cancel": Action.CANCEL,
}


def has_access(user, module: str, submodule: str | None = None, action: str = Action.VIEW) -> bool:
    return get_effective_access(user).can(module, submodule, action)


def require_access(user, module: str, submodule: str | None, action: str) -> None:
    if not has_access(user, module, submodule, action):
        raise PermissionDenied("You do not have permission to perform this action.")


def check_document_action(
    user,
    *,
    module: str,
    submodule: str,
    action: str,
    workflow_check: Callable[[], bool],
) -> None:
    """Gate for workflow actions (approve, reject, forward, ...) on a specific document.

    Module access is necessary but never sufficient: ``workflow_check`` must confirm the existing
    workflow rules (stage, assignment, approval level, financial authority, bypass rules) for this
    document. Superadmin does not skip ``workflow_check``.
    """
    require_access(user, module, submodule, action)
    if not workflow_check():
        raise PermissionDenied("This document is not assigned to you for this action.")


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class ModuleAccessPermission(BasePermission):
    """Resolve the view action to a permission key and check the user's effective access.

    View attributes:
    - ``access_module`` / ``access_submodule``: registry keys.
    - ``access_action_map``: overrides/extends DEFAULT_ACTION_MAP (value ``OPEN`` = any active
      authenticated user).
    Unmapped unsafe actions are denied.
    """

    message = "You do not have permission to perform this action."

    def _required_action(self, request, view) -> str | None:
        action_map = {**DEFAULT_ACTION_MAP, **getattr(view, "access_action_map", {})}
        name = getattr(view, "action", None)
        if name in action_map:
            return action_map[name]
        if request.method in SAFE_METHODS:
            return Action.VIEW
        return None

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        required = self._required_action(request, view)
        if required is None:
            return False
        if required == OPEN:
            return True
        return has_access(user, view.access_module, view.access_submodule, required)

    def has_object_permission(self, request, view, obj) -> bool:
        # Toggling is_active through an edit is an Activate/Deactivate action, not a plain edit.
        if getattr(view, "action", None) in {"update", "partial_update"} and hasattr(
            obj, "is_active"
        ):
            data = request.data
            if hasattr(data, "get") and "is_active" in data:
                if _truthy(data.get("is_active")) != bool(obj.is_active):
                    return has_access(
                        request.user,
                        view.access_module,
                        view.access_submodule,
                        Action.ACTIVATE_DEACTIVATE,
                    )
        return True

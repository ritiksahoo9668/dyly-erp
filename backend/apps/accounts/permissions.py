"""Global-role rules for user administration (onboarding, activation, role changes).

Global roles only govern who may administer ERP user accounts. They do not grant
operational access to other modules.
"""

from rest_framework.permissions import BasePermission

from .models import User

Role = User.Role

ROLE_ASSIGNMENT: dict[str, tuple[str, ...]] = {
    Role.SUPERADMIN: (Role.SUPERADMIN, Role.ADMIN, Role.USER),
    Role.ADMIN: (Role.USER,),
    Role.USER: (),
}


def _is_active_user(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active)


def assignable_roles(user) -> list[str]:
    if not _is_active_user(user):
        return []
    return list(ROLE_ASSIGNMENT.get(user.role, ()))


def can_manage_users(user) -> bool:
    return bool(assignable_roles(user))


def can_manage_role(actor, role: str) -> bool:
    """True when ``actor`` may create, invite, change or (de)activate an account with ``role``."""
    return role in assignable_roles(actor)


class CanManageUsers(BasePermission):
    message = "You do not have permission to manage ERP users."

    def has_permission(self, request, view) -> bool:
        return can_manage_users(request.user)

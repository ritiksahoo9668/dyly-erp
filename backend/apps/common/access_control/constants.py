"""Stable access-control keys. Keys are database identities; display text lives in the registry."""

from enum import StrEnum


class Module(StrEnum):
    DASHBOARD = "DASHBOARD"
    PROCUREMENT = "PROCUREMENT"
    PRODUCTION = "PRODUCTION"
    SALES = "SALES"
    HR = "HR"
    MASTER = "MASTER"


class Action(StrEnum):
    VIEW = "VIEW"
    CREATE = "CREATE"
    EDIT = "EDIT"
    EXPORT = "EXPORT"
    CANCEL = "CANCEL"
    UPLOAD = "UPLOAD"
    ACTIVATE_DEACTIVATE = "ACTIVATE_DEACTIVATE"


ACTION_LABELS: dict[str, str] = {
    Action.VIEW: "View",
    Action.CREATE: "Create",
    Action.EDIT: "Edit",
    Action.EXPORT: "Export",
    Action.CANCEL: "Cancel",
    Action.UPLOAD: "Upload",
    Action.ACTIVATE_DEACTIVATE: "Activate / Deactivate",
}

# Column on UserSubmoduleAccess that stores each action.
ACTION_FIELDS: dict[str, str] = {
    Action.VIEW: "can_view",
    Action.CREATE: "can_create",
    Action.EDIT: "can_edit",
    Action.EXPORT: "can_export",
    Action.CANCEL: "can_cancel",
    Action.UPLOAD: "can_upload",
    Action.ACTIVATE_DEACTIVATE: "can_activate_deactivate",
}

# Approval is intentionally absent: approving a document depends on workflow stage, assignment,
# approval level and financial authority, never on a module checkbox.
TRANSACTION_ACTIONS: tuple[str, ...] = (
    Action.VIEW,
    Action.CREATE,
    Action.EDIT,
    Action.EXPORT,
    Action.CANCEL,
)
MASTER_ACTIONS: tuple[str, ...] = (
    Action.VIEW,
    Action.CREATE,
    Action.EDIT,
    Action.EXPORT,
    Action.UPLOAD,
    Action.ACTIVATE_DEACTIVATE,
)
VIEW_ONLY: tuple[str, ...] = (Action.VIEW,)

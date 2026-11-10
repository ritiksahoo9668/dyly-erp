"""Single registry of ERP modules, submodules and the actions each submodule supports.

Drives permission validation, the permission matrix UI (served by the registry API), navigation
filtering (via ``nav_id``, which matches the frontend navigation ids) and backend checks.
"""

from dataclasses import dataclass

from .constants import (
    ACTION_LABELS,
    MASTER_ACTIONS,
    TRANSACTION_ACTIONS,
    VIEW_ONLY,
    Module,
)


@dataclass(frozen=True)
class SubmoduleDef:
    key: str
    label: str
    nav_id: str
    actions: tuple[str, ...]


@dataclass(frozen=True)
class ModuleDef:
    key: str
    label: str
    nav_id: str
    submodules: tuple[SubmoduleDef, ...]

    def submodule(self, key: str) -> SubmoduleDef | None:
        return next((sub for sub in self.submodules if sub.key == key), None)


def _txn(key: str, label: str, nav_id: str) -> SubmoduleDef:
    return SubmoduleDef(key, label, nav_id, TRANSACTION_ACTIONS)


def _master(key: str, label: str, nav_id: str) -> SubmoduleDef:
    return SubmoduleDef(key, label, nav_id, MASTER_ACTIONS)


MODULES: tuple[ModuleDef, ...] = (
    ModuleDef(
        Module.DASHBOARD,
        "Dashboard",
        "dashboard",
        (SubmoduleDef("OVERVIEW", "Overview", "overview", VIEW_ONLY),),
    ),
    ModuleDef(
        Module.PROCUREMENT,
        "Procurement",
        "procurement",
        (
            _txn("PLANNING", "Planning", "planning"),
            _txn("INDENT", "Indent", "indent"),
            _txn("RFQ", "RFQ", "rfq"),
            _txn("CS", "CS", "cs"),
            _txn("PO", "PO", "po"),
            _txn("GATE_ENTRY", "Gate Entry", "gate-entry"),
            _txn("WEIGHBRIDGE", "WeighBridge", "weighbridge"),
            _txn("QC", "QC", "qc"),
            _txn("GRN", "GRN", "grn"),
        ),
    ),
    ModuleDef(
        Module.PRODUCTION,
        "Production",
        "production",
        (
            _txn("PLANNING", "Planning", "planning"),
            _txn("FEED_CONSUMPTION", "Feed & Consumption", "feed-consumption"),
            _txn("PRODUCTION_ENTRY", "Production Entry", "production-entry"),
        ),
    ),
    ModuleDef(
        Module.SALES,
        "Sales",
        "sales",
        (
            _txn("PLANNING", "Planning", "planning"),
            _txn("INQUIRY_CAPTURE", "Inquiry Capture", "inquiry-capture"),
            _txn("SALES_OFFER", "Sales Offer", "sales-offer"),
            _txn("PO_RECEIVED", "PO Received", "po-received"),
            _txn("DO", "DO", "do"),
            _txn("GATE_ENTRY", "Gate Entry", "gate-entry"),
            _txn("DISPATCH_LOADING", "Dispatch / Loading", "dispatch-loading"),
            _txn("INVOICE", "Invoice", "invoice"),
            _txn("GATE_EXIT", "Gate Exit", "gate-exit"),
        ),
    ),
    # HR currently has a single overview screen; add submodules here as HR screens are built.
    ModuleDef(
        Module.HR,
        "HR",
        "hr",
        (SubmoduleDef("OVERVIEW", "Overview", "overview", VIEW_ONLY),),
    ),
    # User Onboarding is not listed: it is governed by the global role (see accounts.permissions).
    ModuleDef(
        Module.MASTER,
        "Master",
        "master",
        (
            _master("EMPLOYEE", "Employee", "employee"),
            _master("DEPARTMENT", "Department", "department"),
            _master("MATERIAL_CATEGORY", "Material Category", "material-category"),
            _master("MATERIAL_SUBCATEGORY", "Material Sub Category", "material-sub-category"),
            _master("MATERIAL_GROUP", "Material Group", "material-group"),
            _master("PURCHASING_GROUP", "Purchasing Group", "purchasing-group"),
            _master("PLANT", "Plant", "plant"),
            _master("MATERIAL_TYPE", "Material Type", "material-type"),
            _master("MATERIAL", "Material / Item", "material-item"),
            _master("UOM", "UOM", "uom"),
            _master("QC_PARAMETER", "QC Parameter", "qc-parameter"),
            _master("VENDOR", "Vendor", "vendor"),
            _master("DIVISION", "Division", "division"),
            _master("VERTICAL", "Vertical", "vertical"),
            _master("FACILITY", "Facility", "facility"),
            _master("COMPANY", "Company", "company"),
            _master("UNIT", "Unit", "unit"),
            _master("DESIGNATION", "Designation", "designation"),
            _master("WEIGHBRIDGE", "WeighBridge", "weighbridge"),
            _master("STOCK_YARD", "Stock Yard", "stock-yard"),
        ),
    ),
)

MODULES_BY_KEY: dict[str, ModuleDef] = {module.key: module for module in MODULES}


def get_module(key: str) -> ModuleDef | None:
    return MODULES_BY_KEY.get(key)


def get_submodule(module_key: str, submodule_key: str) -> SubmoduleDef | None:
    module = get_module(module_key)
    return module.submodule(submodule_key) if module else None


def supports(module_key: str, submodule_key: str, action: str) -> bool:
    sub = get_submodule(module_key, submodule_key)
    return sub is not None and action in sub.actions


def registry_payload() -> list[dict]:
    return [
        {
            "key": module.key,
            "label": module.label,
            "nav_id": module.nav_id,
            "submodules": [
                {
                    "key": sub.key,
                    "label": sub.label,
                    "nav_id": sub.nav_id,
                    "actions": [{"key": a, "label": ACTION_LABELS[a]} for a in sub.actions],
                }
                for sub in module.submodules
            ],
        }
        for module in MODULES
    ]

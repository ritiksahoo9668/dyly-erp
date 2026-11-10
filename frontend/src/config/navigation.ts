import { canOpen } from "@/config/access";
import type { AuthUser } from "@/types/auth";
import type { ModuleStage, NavItem } from "@/types/navigation";

export const mainNavigation: NavItem[] = [
  { id: "dashboard", label: "Dashboard", to: "/dashboard" },
  { id: "procurement", label: "Procurement", to: "/procurement", opensMenu: true },
  { id: "production", label: "Production", to: "/production", opensMenu: true },
  { id: "sales", label: "Sales", to: "/sales", opensMenu: true },
  { id: "hr", label: "HR", to: "/hr" },
  { id: "master", label: "Master", to: "/master", opensMenu: true },
];

/**
 * Visual extension points for a later procurement phase.
 * These entries must not be wired to routes in Phase 1.
 */
export const procurementStages: ModuleStage[] = [
  {
    id: "planning",
    label: "Planning",
    description: "Procurement planning.",
    accent: "blue",
  },
  {
    id: "indent",
    label: "Indent",
    description: "Create & track indents.",
    accent: "orange",
  },
  {
    id: "rfq",
    label: "RFQ",
    description: "Request for quotation.",
    accent: "purple",
  },
  {
    id: "cs",
    label: "CS",
    description: "Comparative statement.",
    accent: "green",
  },
  {
    id: "po",
    label: "PO",
    description: "Purchase order.",
    accent: "blue",
  },
  {
    id: "gate-entry",
    label: "Gate Entry",
    description: "Material gate entry.",
    accent: "red",
  },
  {
    id: "weighbridge",
    label: "WeighBridge",
    description: "Weighment process.",
    accent: "amber",
  },
  {
    id: "qc",
    label: "QC",
    description: "Quality inspection.",
    accent: "purple",
  },
  {
    id: "grn",
    label: "GRN",
    description: "Goods receipt note.",
    accent: "green",
  },
];

/**
 * Production submodules only. Extension points — no workflow routes yet.
 */
export const productionStages: ModuleStage[] = [
  {
    id: "planning",
    label: "Planning",
    description: "Production planning.",
    accent: "blue",
    to: "/production/planning",
  },
  {
    id: "feed-consumption",
    label: "Feed & Consumption",
    description: "Material feed and consumption.",
    accent: "orange",
    to: "/production/feed-consumption",
  },
  {
    id: "production-entry",
    label: "Production Entry",
    description: "Record production output.",
    accent: "green",
    to: "/production/production-entry",
  },
];

/**
 * Sales submodules. Navigation only — each route renders a placeholder page.
 */
export const salesStages: ModuleStage[] = [
  {
    id: "planning",
    label: "Planning",
    description: "Sales planning.",
    accent: "blue",
    to: "/sales/planning",
  },
  {
    id: "inquiry-capture",
    label: "Inquiry Capture",
    description: "Capture customer inquiries.",
    accent: "orange",
    to: "/sales/inquiry-capture",
  },
  {
    id: "sales-offer",
    label: "Sales Offer",
    description: "Prepare & send offers.",
    accent: "purple",
    to: "/sales/sales-offer",
  },
  {
    id: "po-received",
    label: "PO Received",
    description: "Customer purchase orders.",
    accent: "green",
    to: "/sales/po-received",
  },
  {
    id: "do",
    label: "DO",
    description: "Delivery order.",
    accent: "blue",
    to: "/sales/do",
  },
  {
    id: "gate-entry",
    label: "Gate Entry",
    description: "Vehicle gate entry.",
    accent: "red",
    to: "/sales/gate-entry",
  },
  {
    id: "dispatch-loading",
    label: "Dispatch / Loading",
    description: "Loading & dispatch.",
    accent: "amber",
    to: "/sales/dispatch-loading",
  },
  {
    id: "invoice",
    label: "Invoice",
    description: "Sales invoicing.",
    accent: "purple",
    to: "/sales/invoice",
  },
  {
    id: "gate-exit",
    label: "Gate Exit",
    description: "Vehicle gate exit.",
    accent: "green",
    to: "/sales/gate-exit",
  },
];

/**
 * Master submodules. Entries with `to` open a live master page.
 */
export const masterStages: ModuleStage[] = [
  {
    id: "employee",
    label: "Employee",
    description: "Employee master records.",
    accent: "blue",
    to: "/master/employee",
  },
  {
    id: "user-onboarding",
    label: "User Onboarding",
    description: "ERP users, roles and invitations.",
    accent: "green",
    to: "/master/user-onboarding",
    requiresUserAdmin: true,
  },
  {
    id: "department",
    label: "Department",
    description: "Department structure.",
    accent: "indigo",
    to: "/master/department",
  },
  {
    id: "material-category",
    label: "Material Category",
    description: "Top-level material groups.",
    accent: "orange",
    to: "/master/material-category",
  },
  {
    id: "material-sub-category",
    label: "Material Sub Category",
    description: "Material sub-groups.",
    accent: "amber",
    to: "/master/material-sub-category",
  },
  {
    id: "material-group",
    label: "Material Group",
    description: "SAP material group mapping.",
    accent: "teal",
    to: "/master/material-group",
  },
  {
    id: "purchasing-group",
    label: "Purchasing Group",
    description: "SAP purchase group mapping.",
    accent: "indigo",
    to: "/master/purchasing-group",
  },
  {
    id: "plant",
    label: "Plant",
    description: "SAP plant mapping.",
    accent: "blue",
    to: "/master/plant",
  },
  {
    id: "material-type",
    label: "Material Type",
    description: "SAP material type mapping.",
    accent: "orange",
    to: "/master/material-type",
  },
  {
    id: "material-item",
    label: "Material / Item",
    description: "Item and material masters.",
    accent: "teal",
    to: "/master/material",
  },
  {
    id: "uom",
    label: "UOM",
    description: "Units of measure.",
    accent: "purple",
    to: "/master/uom",
  },
  {
    id: "qc-parameter",
    label: "QC Parameter",
    description: "Quality check parameters.",
    accent: "purple",
    to: "/master/qc-parameter",
  },
  {
    id: "vendor",
    label: "Vendor",
    description: "Supplier and vendor records.",
    accent: "green",
    to: "/master/vendor",
  },
  {
    id: "division",
    label: "Division",
    description: "Business divisions.",
    accent: "blue",
    to: "/master/division",
  },
  {
    id: "vertical",
    label: "Vertical",
    description: "Business verticals.",
    accent: "purple",
    to: "/master/vertical",
  },
  {
    id: "facility",
    label: "Facility",
    description: "Plants and facilities.",
    accent: "indigo",
    to: "/master/facility",
  },
  {
    id: "company",
    label: "Company",
    description: "Legal companies.",
    accent: "blue",
    to: "/master/company",
  },
  {
    id: "unit",
    label: "Unit",
    description: "Company operating units.",
    accent: "teal",
    to: "/master/unit",
  },
  {
    id: "designation",
    label: "Designation",
    description: "Job titles and roles.",
    accent: "orange",
    to: "/master/designation",
  },
  {
    id: "weighbridge",
    label: "WeighBridge",
    description: "Weighbridge masters.",
    accent: "red",
    to: "/master/weighbridge",
  },
  {
    id: "stock-yard",
    label: "Stock Yard",
    description: "Yard and storage locations.",
    accent: "amber",
    to: "/master/stock-yard",
  },
];

export function canManageUsers(user: AuthUser | null | undefined) {
  return Boolean(user?.can_manage_users);
}

/** Master stages the signed-in user may open (UI hint only; the API enforces access). */
export function visibleMasterStages(user: AuthUser | null | undefined) {
  const userAdmin = canManageUsers(user);
  return masterStages.filter((stage) =>
    stage.requiresUserAdmin ? userAdmin : canOpen(user, "master", stage.id),
  );
}

/** Stages of a transactional module (procurement / production / sales) the user may open. */
export function visibleStages(
  user: AuthUser | null | undefined,
  moduleNavId: string,
  stages: ModuleStage[],
) {
  return stages.filter((stage) => canOpen(user, moduleNavId, stage.id));
}

/** Main navigation entries the user may open. Master also opens for user administrators. */
export function visibleNavigation(user: AuthUser | null | undefined) {
  return mainNavigation.filter((item) =>
    item.id === "master" ? visibleMasterStages(user).length > 0 : canOpen(user, item.id),
  );
}

/** First page the user may open, used after sign-in and for unknown URLs. */
export function homePath(user: AuthUser | null | undefined) {
  const item = visibleNavigation(user)[0];
  if (!item) return null;
  if (item.id === "master" && !canOpen(user, "master")) {
    return visibleMasterStages(user)[0]?.to ?? null;
  }
  return item.to;
}

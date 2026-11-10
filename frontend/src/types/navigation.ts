export type NavItem = {
  id: string;
  label: string;
  to: string;
  opensMenu?: boolean;
};

export type StageAccent =
  | "blue"
  | "green"
  | "purple"
  | "orange"
  | "teal"
  | "indigo"
  | "red"
  | "amber";

export type ModuleStage = {
  id: string;
  label: string;
  description: string;
  accent: StageAccent;
  /** Optional submodule route. When set, the stage menu navigates here. */
  to?: string;
  /** Visible only to users who can manage ERP user accounts (Superadmin / Admin). */
  requiresUserAdmin?: boolean;
};

/** @deprecated Prefer ModuleStage */
export type ProcurementStage = ModuleStage;

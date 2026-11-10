import type { AccessAction, AccessModuleKey } from "@/types/access";
import type { AuthUser } from "@/types/auth";

/**
 * UI hints derived from `/auth/me`. They hide navigation and buttons only; every API checks the
 * same permissions on the server.
 */

type MaybeUser = AuthUser | null | undefined;

/** Main navigation ids (see `mainNavigation`) mapped to registry module keys. */
export const MODULE_BY_NAV_ID: Record<string, AccessModuleKey> = {
  dashboard: "DASHBOARD",
  procurement: "PROCUREMENT",
  production: "PRODUCTION",
  sales: "SALES",
  hr: "HR",
  master: "MASTER",
};

export function hasFullAccess(user: MaybeUser) {
  return Boolean(user?.access?.full_access);
}

/** Whether `user` may perform `action` on a module (any submodule) or a specific submodule. */
export function canAccess(
  user: MaybeUser,
  module: AccessModuleKey,
  submodule?: string,
  action: AccessAction = "VIEW",
) {
  const access = user?.access;
  if (!access) return false;
  if (access.full_access) return true;
  const entry = access.modules[module];
  if (!entry) return false;
  if (!submodule) {
    return Object.values(entry.submodules).some((sub) => sub.actions.includes(action));
  }
  return entry.submodules[submodule]?.actions.includes(action) ?? false;
}

/** Navigation check by nav ids: a main module and optionally one of its stages. */
export function canOpen(user: MaybeUser, moduleNavId: string, stageId?: string) {
  const module = MODULE_BY_NAV_ID[moduleNavId];
  if (!module) return false;
  const access = user?.access;
  if (!access) return false;
  if (access.full_access) return true;
  const entry = access.modules[module];
  if (!entry) return false;
  if (!stageId) return true;
  return Object.values(entry.submodules).some((sub) => sub.nav_id === stageId);
}

/** Registry submodule key for a module stage nav id (e.g. MASTER + "material-item" → "MATERIAL"). */
export function submoduleForStage(user: MaybeUser, module: AccessModuleKey, stageId: string) {
  const entry = user?.access?.modules[module];
  if (!entry) return undefined;
  return Object.entries(entry.submodules).find(([, sub]) => sub.nav_id === stageId)?.[0];
}

/** Actions `user` holds on a stage, e.g. to show or hide Add / Upload / Deactivate buttons. */
export function stageActions(
  user: MaybeUser,
  moduleNavId: string,
  stageId: string,
): Record<AccessAction, boolean> {
  const module = MODULE_BY_NAV_ID[moduleNavId];
  const full = hasFullAccess(user);
  const key = module ? submoduleForStage(user, module, stageId) : undefined;
  const granted = new Set(key && module ? user?.access?.modules[module]?.submodules[key]?.actions : []);
  const has = (action: AccessAction) => full || granted.has(action);
  return {
    VIEW: has("VIEW"),
    CREATE: has("CREATE"),
    EDIT: has("EDIT"),
    EXPORT: has("EXPORT"),
    CANCEL: has("CANCEL"),
    UPLOAD: has("UPLOAD"),
    ACTIVATE_DEACTIVATE: has("ACTIVATE_DEACTIVATE"),
  };
}

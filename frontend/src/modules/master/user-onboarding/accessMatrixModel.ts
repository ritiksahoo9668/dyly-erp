import type {
  AccessAction,
  AccessAssignment,
  AccessModuleKey,
  AccessRegistryModule,
} from "@/types/access";

type ModuleEntry = { enabled: boolean; submodules: Record<string, AccessAction[]> };

/** Decides whether the signed-in administrator may change one permission (mirrors the API rule). */
export type GrantCheck = (module: AccessModuleKey, submodule?: string, action?: AccessAction) => boolean;

export function moduleEntry(value: AccessAssignment, module: AccessModuleKey): ModuleEntry {
  return value[module] ?? { enabled: false, submodules: {} };
}

function withEntry(value: AccessAssignment, module: AccessModuleKey, entry: ModuleEntry) {
  const next = { ...value };
  if (!entry.enabled && Object.keys(entry.submodules).length === 0) delete next[module];
  else next[module] = entry;
  return next;
}

export function setModuleEnabled(
  value: AccessAssignment,
  module: AccessModuleKey,
  enabled: boolean,
): AccessAssignment {
  return withEntry(value, module, { ...moduleEntry(value, module), enabled });
}

/** Toggle one action. Any action implies View; removing View removes the submodule. */
export function setAction(
  value: AccessAssignment,
  module: AccessModuleKey,
  submodule: string,
  action: AccessAction,
  checked: boolean,
): AccessAssignment {
  const entry = moduleEntry(value, module);
  const actions = new Set(entry.submodules[submodule] ?? []);
  if (checked) {
    actions.add(action);
    actions.add("VIEW");
  } else if (action === "VIEW") {
    actions.clear();
  } else {
    actions.delete(action);
  }
  const submodules = { ...entry.submodules };
  if (actions.size) submodules[submodule] = [...actions];
  else delete submodules[submodule];
  return withEntry(value, module, {
    enabled: checked ? true : entry.enabled,
    submodules,
  });
}

/** Grant (or clear) every action the administrator is allowed to change within a module. */
export function setAllActions(
  value: AccessAssignment,
  module: AccessRegistryModule,
  checked: boolean,
  canGrant: GrantCheck,
): AccessAssignment {
  const entry = moduleEntry(value, module.key);
  const submodules: Record<string, AccessAction[]> = {};
  for (const sub of module.submodules) {
    const actions = new Set(entry.submodules[sub.key] ?? []);
    for (const { key } of sub.actions) {
      if (!canGrant(module.key, sub.key, key)) continue;
      if (checked) actions.add(key);
      else actions.delete(key);
    }
    if (checked && actions.size) actions.add("VIEW");
    if (!actions.has("VIEW")) actions.clear();
    if (actions.size) submodules[sub.key] = [...actions];
  }
  const enabled = checked && canGrant(module.key) ? true : entry.enabled;
  return withEntry(value, module.key, { enabled, submodules });
}

export function enabledSubmoduleCount(value: AccessAssignment, module: AccessModuleKey) {
  return Object.values(moduleEntry(value, module).submodules).filter((actions) => actions.length)
    .length;
}

/** Columns for a module's table: every action any of its submodules supports, in registry order. */
export function actionColumns(module: AccessRegistryModule) {
  const seen = new Map<AccessAction, string>();
  for (const sub of module.submodules) {
    for (const action of sub.actions) {
      if (!seen.has(action.key)) seen.set(action.key, action.label);
    }
  }
  return [...seen].map(([key, label]) => ({ key, label }));
}

/** One-line summary, e.g. "Procurement: 5 of 9 · Master: 20 of 20". */
export function accessSummary(value: AccessAssignment, registry: AccessRegistryModule[]) {
  return registry
    .filter((module) => value[module.key]?.enabled)
    .map(
      (module) =>
        `${module.label}: ${enabledSubmoduleCount(value, module.key)} of ${module.submodules.length}`,
    );
}

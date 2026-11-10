import { useState } from "react";
import { useGetAccessRegistryQuery } from "@/app/store/api";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { canAccess } from "@/config/access";
import { ChevronIcon } from "@/modules/master/employee/employeeIcons";
import type { AccessAssignment, AccessRegistryModule } from "@/types/access";
import type { UserRole } from "@/types/userOnboarding";
import {
  actionColumns,
  enabledSubmoduleCount,
  moduleEntry,
  setAction,
  setAllActions,
  setModuleEnabled,
  type GrantCheck,
} from "./accessMatrixModel";
import styles from "./AccessMatrix.module.css";

type Props = {
  value: AccessAssignment;
  role: UserRole | "";
  onChange?: (next: AccessAssignment) => void;
  readOnly?: boolean;
};

/** Module → Submodule → Action permission matrix (editable in forms, read-only in details). */
export function AccessMatrix({ value, role, onChange, readOnly = false }: Props) {
  const actor = useAppSelector(selectAuthUser);
  const registryQuery = useGetAccessRegistryQuery();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  if (role === "SUPERADMIN") {
    return (
      <div className={styles.fullAccess}>
        <strong>Full System Access</strong>
        <span>
          Superadmin can open every module and perform every action. No module permissions are
          stored for this role.
        </span>
      </div>
    );
  }
  if (registryQuery.isLoading) return <p className={styles.muted}>Loading modules…</p>;
  if (!registryQuery.data) return <p className={styles.muted}>Modules are unavailable right now.</p>;

  const canGrant: GrantCheck = (module, submodule, action) =>
    !readOnly && canAccess(actor, module, submodule, action ?? "VIEW");
  const modules = registryQuery.data.modules.filter(
    (module) => !readOnly || value[module.key] !== undefined,
  );

  if (readOnly && modules.length === 0) {
    return <p className={styles.muted}>No module access assigned. The user can sign in only.</p>;
  }

  function toggleExpanded(key: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className={styles.matrix}>
      {modules.map((module) => (
        <ModuleCard
          key={module.key}
          module={module}
          value={value}
          open={readOnly || expanded.has(module.key)}
          readOnly={readOnly}
          canGrant={canGrant}
          onToggleOpen={() => toggleExpanded(module.key)}
          onChange={(next) => onChange?.(next)}
        />
      ))}
    </div>
  );
}

function ModuleCard({
  module,
  value,
  open,
  readOnly,
  canGrant,
  onToggleOpen,
  onChange,
}: {
  module: AccessRegistryModule;
  value: AccessAssignment;
  open: boolean;
  readOnly: boolean;
  canGrant: GrantCheck;
  onToggleOpen: () => void;
  onChange: (next: AccessAssignment) => void;
}) {
  const entry = moduleEntry(value, module.key);
  const columns = actionColumns(module);
  const count = enabledSubmoduleCount(value, module.key);
  const moduleLocked = !canGrant(module.key);
  const bodyId = `access-${module.key}`;

  return (
    <section className={`${styles.module} ${entry.enabled ? styles.moduleOn : ""}`}>
      <header className={styles.moduleHead}>
        {readOnly ? null : (
          <button
            type="button"
            className={styles.expand}
            aria-expanded={open}
            aria-controls={bodyId}
            aria-label={`${open ? "Collapse" : "Expand"} ${module.label}`}
            onClick={onToggleOpen}
          >
            <span className={open ? styles.chevronOpen : styles.chevron}>
              <ChevronIcon />
            </span>
          </button>
        )}
        <label className={styles.moduleToggle} title={moduleLocked ? LOCKED_HINT : undefined}>
          <input
            type="checkbox"
            checked={entry.enabled}
            disabled={readOnly || moduleLocked}
            onChange={(event) => onChange(setModuleEnabled(value, module.key, event.target.checked))}
          />
          <strong>{module.label}</strong>
        </label>
        <span className={styles.moduleCount}>
          {entry.enabled
            ? `${count} of ${module.submodules.length} submodule${module.submodules.length === 1 ? "" : "s"} enabled`
            : count
              ? "Module disabled"
              : "No access"}
        </span>
        {readOnly ? null : (
          <span className={styles.bulk}>
            <button type="button" onClick={() => onChange(setAllActions(value, module, true, canGrant))}>
              Select all
            </button>
            <button type="button" onClick={() => onChange(setAllActions(value, module, false, canGrant))}>
              Clear
            </button>
          </span>
        )}
      </header>

      {open ? (
        <div id={bodyId} className={styles.tableWrap}>
          {!entry.enabled && count > 0 ? (
            <p className={styles.disabledNote}>
              Module is disabled, so these submodule permissions are kept but not effective.
            </p>
          ) : null}
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Submodule</th>
                {columns.map((column) => (
                  <th key={column.key} scope="col">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {module.submodules.map((sub) => {
                const granted = new Set(entry.submodules[sub.key] ?? []);
                const supported = new Set(sub.actions.map((action) => action.key));
                if (readOnly && granted.size === 0) return null;
                return (
                  <tr key={sub.key} className={granted.size ? styles.rowOn : undefined}>
                    <th scope="row">{sub.label}</th>
                    {columns.map((column) => {
                      if (!supported.has(column.key)) {
                        return (
                          <td key={column.key} className={styles.na} aria-label="Not applicable">
                            —
                          </td>
                        );
                      }
                      const checked = granted.has(column.key);
                      if (readOnly) {
                        return (
                          <td key={column.key} className={checked ? styles.yes : styles.no}>
                            {checked ? "✓" : "—"}
                          </td>
                        );
                      }
                      const locked = !canGrant(module.key, sub.key, column.key);
                      return (
                        <td key={column.key}>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={locked}
                            title={locked ? LOCKED_HINT : undefined}
                            aria-label={`${sub.label} ${column.label}`}
                            onChange={(event) =>
                              onChange(
                                setAction(value, module.key, sub.key, column.key, event.target.checked),
                              )
                            }
                          />
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

const LOCKED_HINT = "You can only grant access that you have yourself.";

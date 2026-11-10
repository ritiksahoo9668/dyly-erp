import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  useChangeErpUserRoleMutation,
  useGetErpUsersQuery,
  useSetErpUserActiveMutation,
} from "@/app/store/api";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { MoreIcon, SearchIcon } from "@/components/navigation/icons";
import employeeStyles from "@/modules/master/employee/EmployeePage.module.css";
import { ChevronIcon, RefreshIcon } from "@/modules/master/employee/employeeIcons";
import { avatarColor, initials } from "@/modules/master/employee/employeeFormat";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import {
  USER_ROLES,
  type ErpUserListParams,
  type ErpUserRecord,
  type UserRole,
} from "@/types/userOnboarding";
import { extractApiError } from "@/utils/extractApiError";
import { AccessEditorModal } from "./AccessEditorModal";
import { Badge } from "./Badge";
import { ConfirmDialog, NoticeDialog, type ConfirmRequest, type Notice } from "./Dialogs";
import { formatDateTime, roleLabel, roleTone } from "./onboardingFormat";
import { RowActionMenu, type RowMenuItem } from "./RowActionMenu";
import { anchorFor, type RowMenuAnchor } from "./rowMenuAnchor";
import styles from "./UserOnboardingPage.module.css";

const PAGE_SIZE = 20;

type RoleChange = { user: ErpUserRecord; role: UserRole };

export function ErpUsersPanel() {
  const currentUser = useAppSelector(selectAuthUser);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<UserRole | "">("");
  const [status, setStatus] = useState<"all" | "active" | "inactive">("all");
  const [page, setPage] = useState(1);
  const [menu, setMenu] = useState<RowMenuAnchor | null>(null);
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null);
  const [roleChange, setRoleChange] = useState<RoleChange | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [accessUser, setAccessUser] = useState<ErpUserRecord | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const params = useMemo<ErpUserListParams>(
    () => ({
      search,
      page,
      page_size: PAGE_SIZE,
      role: role || undefined,
      is_active: status === "all" ? undefined : status === "active",
    }),
    [search, page, role, status],
  );
  const { data, isLoading, isFetching, isError, refetch } = useGetErpUsersQuery(params);
  const [setActive, activeState] = useSetErpUserActiveMutation();
  const [changeRole, roleState] = useChangeErpUserRoleMutation();
  const busy = activeState.isLoading || roleState.isLoading;

  const rows = data?.results ?? [];
  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const closeMenu = useCallback(() => setMenu(null), []);
  const assignable = currentUser?.assignable_roles ?? [];

  async function runConfirm() {
    if (!confirm) return;
    try {
      await confirm.run();
    } catch (err) {
      setNotice({ title: "Action failed", message: extractApiError(err) });
    } finally {
      setConfirm(null);
    }
  }

  async function submitRoleChange() {
    if (!roleChange) return;
    try {
      await changeRole({ id: roleChange.user.id, role: roleChange.role }).unwrap();
      setRoleChange(null);
    } catch (err) {
      setRoleChange(null);
      setNotice({ title: "Role not changed", message: extractApiError(err) });
    }
  }

  function menuItems(user: ErpUserRecord): RowMenuItem[] {
    const items: RowMenuItem[] = [];
    if (user.allowed_actions.includes("change_role")) {
      items.push({
        key: "change_role",
        label: "Change Role",
        onSelect: () => setRoleChange({ user, role: user.role }),
      });
    }
    if (user.allowed_actions.includes("edit_access")) {
      items.push({
        key: "edit_access",
        label: "Edit Module Access",
        onSelect: () => setAccessUser(user),
      });
    }
    if (user.allowed_actions.includes("activate")) {
      items.push({
        key: "activate",
        label: "Activate User",
        onSelect: () =>
          setConfirm({
            title: "Activate User",
            message: `Allow ${user.display_name} (${user.email}) to sign in again?`,
            confirmLabel: "Activate",
            run: async () => {
              await setActive({ id: user.id, active: true }).unwrap();
            },
          }),
      });
    }
    if (user.allowed_actions.includes("deactivate")) {
      items.push({
        key: "deactivate",
        label: "Deactivate User",
        danger: true,
        onSelect: () =>
          setConfirm({
            title: "Deactivate User",
            subtitle: "The employee record is not changed.",
            message: `${user.display_name} (${user.email}) will be signed out and unable to log in until reactivated.`,
            confirmLabel: "Deactivate",
            danger: true,
            run: async () => {
              await setActive({ id: user.id, active: false }).unwrap();
            },
          }),
      });
    }
    return items;
  }

  const menuUser = menu ? rows.find((row) => row.id === menu.id) : undefined;

  return (
    <>
      <section className={employeeStyles.filterCard}>
        <label className={employeeStyles.searchBox}>
          <SearchIcon />
          <input
            type="search"
            placeholder="Search by name, email or employee code..."
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            aria-label="Search users"
          />
        </label>
        <div className={employeeStyles.filterGrid}>
          <label className={employeeStyles.filterField}>
            <span>Role</span>
            <select
              value={role}
              onChange={(event) => {
                setRole(event.target.value as UserRole | "");
                setPage(1);
              }}
            >
              <option value="">All Roles</option>
              {USER_ROLES.map((item) => (
                <option key={item} value={item}>
                  {roleLabel(item)}
                </option>
              ))}
            </select>
          </label>
          <label className={employeeStyles.filterField}>
            <span>Status</span>
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as typeof status);
                setPage(1);
              }}
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
        </div>
        <div className={employeeStyles.filterFooter}>
          <span className={employeeStyles.filterHint}>
            ERP user accounts. Deactivating a user never changes the employee record.
          </span>
          <button
            type="button"
            className={`${shared.secondaryBtn} ${employeeStyles.iconBtnLabel}`}
            onClick={() => {
              setSearchInput("");
              setSearch("");
              setRole("");
              setStatus("all");
              setPage(1);
            }}
          >
            <RefreshIcon />
            Reset
          </button>
        </div>
      </section>

      <section className={employeeStyles.tableCard}>
        {isLoading ? <p className={shared.loading}>Loading users…</p> : null}
        {isError ? (
          <p className={shared.error}>
            Unable to load users.{" "}
            <button type="button" className={shared.linkBtn} onClick={() => refetch()}>
              Retry
            </button>
          </p>
        ) : null}
        {!isLoading && !isError && rows.length === 0 ? (
          <p className={shared.empty}>No users match the search or filters.</p>
        ) : null}

        {!isLoading && !isError && rows.length > 0 ? (
          <>
            <div className={employeeStyles.tableWrap}>
              <table className={`${employeeStyles.table} ${styles.usersTable}`}>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Employee Code</th>
                    <th>Login Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Last Login</th>
                    <th className={employeeStyles.actionsHead}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((user) => {
                    const name = user.employee?.full_name || user.display_name;
                    const items = menuItems(user);
                    return (
                      <tr key={user.id} style={{ cursor: "default" }}>
                        <td>
                          <div className={employeeStyles.employeeCell}>
                            <span
                              className={employeeStyles.avatar}
                              style={{ background: avatarColor(name) }}
                              aria-hidden="true"
                            >
                              {initials(name)}
                            </span>
                            <div className={employeeStyles.stack}>
                              <strong>{name}</strong>
                              <span>{user.employee?.department?.name ?? "No linked employee"}</span>
                            </div>
                          </div>
                        </td>
                        <td>{user.employee?.employee_code ?? "—"}</td>
                        <td>{user.email}</td>
                        <td>
                          <Badge label={roleLabel(user.role)} tone={roleTone(user.role)} />
                        </td>
                        <td>
                          <Badge
                            label={user.is_active ? "Active" : "Inactive"}
                            tone={user.is_active ? "green" : "gray"}
                            dot
                          />
                        </td>
                        <td>{formatDateTime(user.last_login)}</td>
                        <td className={employeeStyles.actionsCell}>
                          <div className={employeeStyles.rowActions}>
                            {items.length ? (
                              <button
                                type="button"
                                className={`${employeeStyles.iconBtn} ${
                                  menu?.id === user.id ? employeeStyles.iconBtnOpen : ""
                                }`}
                                data-action-trigger="true"
                                aria-label={`Actions for ${name}`}
                                aria-haspopup="menu"
                                aria-expanded={menu?.id === user.id}
                                onClick={(event) =>
                                  setMenu(
                                    menu?.id === user.id
                                      ? null
                                      : anchorFor(user.id, event.currentTarget, items.length),
                                  )
                                }
                              >
                                <MoreIcon size={15} />
                              </button>
                            ) : (
                              <span className={employeeStyles.muted}>—</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <footer className={employeeStyles.footer}>
              <span className={employeeStyles.footerInfo}>
                {total} user{total === 1 ? "" : "s"}
                {isFetching ? " · Refreshing…" : ""}
              </span>
              <nav className={employeeStyles.pagination} aria-label="Pagination">
                <button
                  type="button"
                  className={employeeStyles.pageBtn}
                  aria-label="Previous page"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronIcon left />
                </button>
                <span className={employeeStyles.pageGap}>
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className={employeeStyles.pageBtn}
                  aria-label="Next page"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  <ChevronIcon />
                </button>
              </nav>
            </footer>
          </>
        ) : null}
      </section>

      {menu && menuUser ? (
        <RowActionMenu anchor={menu} items={menuItems(menuUser)} onClose={closeMenu} />
      ) : null}

      {createPortal(
        <>
          {confirm ? (
            <ConfirmDialog
              request={confirm}
              busy={busy}
              onCancel={() => setConfirm(null)}
              onConfirm={() => void runConfirm()}
            />
          ) : null}
          {roleChange ? (
            <ConfirmDialog
              request={{
                title: "Change Role",
                subtitle: roleChange.user.email,
                confirmLabel: "Save Role",
                message: (
                  <select
                    className={styles.selectField}
                    aria-label="New role"
                    value={roleChange.role}
                    onChange={(event) =>
                      setRoleChange({ ...roleChange, role: event.target.value as UserRole })
                    }
                  >
                    {Array.from(new Set([roleChange.user.role, ...assignable])).map((item) => (
                      <option key={item} value={item}>
                        {roleLabel(item)}
                      </option>
                    ))}
                  </select>
                ),
                run: submitRoleChange,
              }}
              busy={busy}
              onCancel={() => setRoleChange(null)}
              onConfirm={() => {
                if (roleChange.role === roleChange.user.role) setRoleChange(null);
                else void submitRoleChange();
              }}
            />
          ) : null}
          {notice ? <NoticeDialog notice={notice} onClose={() => setNotice(null)} /> : null}
          {accessUser ? (
            <AccessEditorModal
              userId={accessUser.id}
              name={accessUser.employee?.full_name || accessUser.display_name}
              email={accessUser.email}
              onClose={() => setAccessUser(null)}
            />
          ) : null}
        </>,
        document.body,
      )}
    </>
  );
}

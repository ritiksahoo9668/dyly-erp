import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  useDiscardUserOnboardingMutation,
  useGetUnitsQuery,
  useGetUserOnboardingQuery,
  useGetUserOnboardingStatsQuery,
  useGetUserOnboardingsQuery,
  useLazyGetUserOnboardingQuery,
  useOnboardingActionMutation,
  useSetErpUserActiveMutation,
} from "@/app/store/api";
import { PageContainer } from "@/components/common/PageContainer";
import {
  MasterUserOnboardingIcon,
  MoreIcon,
  PlusIcon,
  SearchIcon,
} from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import employeeStyles from "@/modules/master/employee/EmployeePage.module.css";
import {
  ChevronIcon,
  ClockIcon,
  RefreshIcon,
  UserCheckIcon,
  UsersIcon,
} from "@/modules/master/employee/employeeIcons";
import { avatarColor, initials } from "@/modules/master/employee/employeeFormat";
import { useEmployeeMasters } from "@/modules/master/employee/useEmployeeLookups";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import {
  ONBOARDING_STATUSES,
  ONBOARDING_STATUS_LABELS,
  USER_ROLES,
  type OnboardingAction,
  type OnboardingStatus,
  type UserOnboardingDetail,
  type UserOnboardingListParams,
  type UserOnboardingRecord,
  type UserRole,
} from "@/types/userOnboarding";
import { extractApiError } from "@/utils/extractApiError";
import { Badge } from "./Badge";
import { ConfirmDialog, NoticeDialog, type ConfirmRequest, type Notice } from "./Dialogs";
import { ErpUsersPanel } from "./ErpUsersPanel";
import { AccessEditorModal } from "./AccessEditorModal";
import { OnboardingDetailsModal } from "./OnboardingDetailsModal";
import { OnboardingFormDrawer } from "./OnboardingFormDrawer";
import {
  ACTION_LABELS,
  DANGER_ACTIONS,
  accountStatus,
  formatDateTime,
  invitationBadge,
  roleLabel,
  roleTone,
} from "./onboardingFormat";
import { RowActionMenu } from "./RowActionMenu";
import { anchorFor, type RowMenuAnchor } from "./rowMenuAnchor";
import styles from "./UserOnboardingPage.module.css";

const PAGE_SIZE = 20;
const LOOKUP_PAGE_SIZE = 500;
const QUEUED_POLL_MS = 2000;

type Tab = "onboarding" | "users";
type IdFilter = number | "";
type Filters = {
  status: OnboardingStatus | "";
  role: UserRole | "";
  department: IdFilter;
  company: IdFilter;
  unit: IdFilter;
};

const EMPTY_FILTERS: Filters = { status: "", role: "", department: "", company: "", unit: "" };

type Panel =
  | { kind: "view"; id: number }
  | { kind: "form"; record: UserOnboardingDetail | null }
  | null;

function StatCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: number | undefined;
  icon: ReactNode;
  tone: "blue" | "amber" | "green" | "red";
}) {
  return (
    <div className={employeeStyles.statCard}>
      <span className={`${employeeStyles.statIcon} ${styles[`icon_${tone}`]}`}>{icon}</span>
      <div>
        <span className={employeeStyles.statLabel}>{label}</span>
        <strong className={employeeStyles.statValue}>{value ?? "—"}</strong>
      </div>
    </div>
  );
}

function IdSelect({
  label,
  placeholder,
  value,
  options,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: IdFilter;
  options: { id: number; name: string }[] | undefined;
  onChange: (value: IdFilter) => void;
}) {
  return (
    <label className={employeeStyles.filterField}>
      <span>{label}</span>
      <select
        value={value === "" ? "" : String(value)}
        onChange={(event) => onChange(event.target.value === "" ? "" : Number(event.target.value))}
      >
        <option value="">{placeholder}</option>
        {(options ?? []).map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    </label>
  );
}

export function UserOnboardingPage() {
  useDocumentTitle("Master · User Onboarding");
  const [tab, setTab] = useState<Tab>("onboarding");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [menu, setMenu] = useState<RowMenuAnchor | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [confirm, setConfirm] = useState<ConfirmRequest | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [accessTarget, setAccessTarget] = useState<{
    userId: number;
    name: string;
    email: string;
  } | null>(null);

  const masters = useEmployeeMasters();
  const units = useGetUnitsQuery({ lookup: true, page_size: LOOKUP_PAGE_SIZE }).data?.results;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const params = useMemo<UserOnboardingListParams>(
    () => ({
      search,
      page,
      page_size: PAGE_SIZE,
      status: filters.status || undefined,
      role: filters.role || undefined,
      department: filters.department === "" ? undefined : filters.department,
      company: filters.company === "" ? undefined : filters.company,
      unit: filters.unit === "" ? undefined : filters.unit,
    }),
    [search, page, filters],
  );
  const [pollingInterval, setPollingInterval] = useState(0);
  const { data, isLoading, isFetching, isError, refetch } = useGetUserOnboardingsQuery(params, {
    pollingInterval,
  });
  const { data: stats } = useGetUserOnboardingStatsQuery(undefined, { pollingInterval });
  const viewId = panel?.kind === "view" ? panel.id : null;
  const detailQuery = useGetUserOnboardingQuery(viewId ?? 0, { skip: viewId === null });
  const [fetchDetail] = useLazyGetUserOnboardingQuery();
  const [runAction, actionState] = useOnboardingActionMutation();
  const [discard, discardState] = useDiscardUserOnboardingMutation();
  const [setUserActive, userState] = useSetErpUserActiveMutation();
  const busy = actionState.isLoading || discardState.isLoading || userState.isLoading;

  const rows = data?.results ?? [];
  const total = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const activeFilterCount = Object.values(filters).filter((value) => value !== "").length;
  const closeMenu = useCallback(() => setMenu(null), []);
  const mailInFlight = rows.some(
    (row) => row.status === "INVITE_PENDING" && row.last_mail_status === "QUEUED",
  );

  useEffect(() => {
    setPollingInterval(mailInFlight ? QUEUED_POLL_MS : 0);
  }, [mailInFlight]);

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function resetFilters() {
    setFilters(EMPTY_FILTERS);
    setSearchInput("");
    setSearch("");
    setPage(1);
  }

  async function openEdit(id: number) {
    try {
      const record = await fetchDetail(id).unwrap();
      setPanel({ kind: "form", record });
    } catch (err) {
      setNotice({ title: "Unable to open", message: extractApiError(err) });
    }
  }

  async function perform(run: () => Promise<unknown>, success?: Notice) {
    try {
      await run();
      if (success) setNotice(success);
    } catch (err) {
      setNotice({ title: "Action failed", message: extractApiError(err) });
    }
  }

  function handleAction(record: UserOnboardingRecord, action: OnboardingAction) {
    const name = record.employee.full_name;
    switch (action) {
      case "view":
        setPanel({ kind: "view", id: record.id });
        return;
      case "edit":
        void openEdit(record.id);
        return;
      case "send_invite":
      case "resend_invite":
        void perform(
          () =>
            runAction({
              id: record.id,
              action: action === "send_invite" ? "send-invite" : "resend-invite",
            }).unwrap(),
          {
            title: "Invitation queued",
            message: `An activation email will be sent to ${record.login_email} shortly.`,
          },
        );
        return;
      case "discard":
        setConfirm({
          title: "Discard Draft",
          message: `Discard the onboarding draft for ${name}? No account was created for this draft.`,
          confirmLabel: "Discard",
          danger: true,
          run: async () => {
            await discard(record.id).unwrap();
            if (panel?.kind === "view" && panel.id === record.id) setPanel(null);
          },
        });
        return;
      case "revoke":
        setConfirm({
          title: "Revoke Invitation",
          subtitle: "The current activation link stops working immediately.",
          message: `Revoke the invitation sent to ${record.login_email}? You can send a new invitation later.`,
          confirmLabel: "Revoke",
          danger: true,
          run: async () => {
            await runAction({ id: record.id, action: "revoke" }).unwrap();
          },
        });
        return;
      case "deactivate_user":
        if (!record.user) return;
        setConfirm({
          title: "Deactivate User",
          subtitle: "The employee record is not changed.",
          message: `${name} will be signed out and unable to log in until reactivated.`,
          confirmLabel: "Deactivate",
          danger: true,
          run: async () => {
            await setUserActive({ id: record.user!.id, active: false }).unwrap();
          },
        });
        return;
      case "activate_user":
        if (!record.user) return;
        void perform(() => setUserActive({ id: record.user!.id, active: true }).unwrap());
        return;
      case "edit_access":
        if (!record.user) return;
        setAccessTarget({ userId: record.user.id, name, email: record.login_email });
        return;
    }
  }

  async function runConfirm() {
    if (!confirm) return;
    await perform(confirm.run);
    setConfirm(null);
  }

  function onSaved(record: UserOnboardingDetail, sent: boolean) {
    setPanel({ kind: "view", id: record.id });
    if (sent) {
      setNotice({
        title: "Invitation queued",
        message: `An activation email will be sent to ${record.login_email} shortly.`,
      });
    }
  }

  const menuRecord = menu ? rows.find((row) => row.id === menu.id) : undefined;

  return (
    <PageContainer>
      <div className={employeeStyles.page}>
        <header className={employeeStyles.header}>
          <div className={employeeStyles.titleBlock}>
            <span className={employeeStyles.titleIcon}>
              <MasterUserOnboardingIcon size={24} />
            </span>
            <div>
              <h1>User Onboarding</h1>
              <p>Manage ERP users, roles and account invitations.</p>
            </div>
          </div>
          <div className={employeeStyles.headerActions}>
            <button
              type="button"
              className={`${shared.primaryBtn} ${employeeStyles.iconBtnLabel}`}
              onClick={() => setPanel({ kind: "form", record: null })}
            >
              <PlusIcon />
              Onboard User
            </button>
          </div>
        </header>

        <section className={styles.stats} aria-label="User onboarding summary">
          <StatCard
            label="Total Users"
            value={stats?.total_users}
            icon={<UsersIcon size={20} />}
            tone="blue"
          />
          <StatCard
            label="Pending Invitations"
            value={stats?.pending_invitations}
            icon={<ClockIcon size={20} />}
            tone="amber"
          />
          <StatCard
            label="Active Users"
            value={stats?.active_users}
            icon={<UserCheckIcon size={20} />}
            tone="green"
          />
          <StatCard
            label="Expired Invitations"
            value={stats?.expired_invitations}
            icon={<ClockIcon size={20} />}
            tone="red"
          />
        </section>

        <div className={styles.tabs} role="tablist" aria-label="User onboarding views">
          {(
            [
              ["onboarding", "Onboarding"],
              ["users", "Users"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              className={`${styles.tab} ${tab === key ? styles.tabActive : ""}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "users" ? (
          <ErpUsersPanel />
        ) : (
          <>
            <section className={employeeStyles.filterCard}>
              <label className={employeeStyles.searchBox}>
                <SearchIcon />
                <input
                  type="search"
                  placeholder="Search by employee, code, onboarding code or login email..."
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  aria-label="Search onboarding"
                />
              </label>
              <div className={employeeStyles.filterGrid}>
                <label className={employeeStyles.filterField}>
                  <span>Status</span>
                  <select
                    value={filters.status}
                    onChange={(event) =>
                      setFilter("status", event.target.value as OnboardingStatus | "")
                    }
                  >
                    <option value="">All Status</option>
                    {ONBOARDING_STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {ONBOARDING_STATUS_LABELS[status]}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={employeeStyles.filterField}>
                  <span>Role</span>
                  <select
                    value={filters.role}
                    onChange={(event) => setFilter("role", event.target.value as UserRole | "")}
                  >
                    <option value="">All Roles</option>
                    {USER_ROLES.map((role) => (
                      <option key={role} value={role}>
                        {roleLabel(role)}
                      </option>
                    ))}
                  </select>
                </label>
                <IdSelect
                  label="Department"
                  placeholder="All Departments"
                  value={filters.department}
                  options={masters.departments}
                  onChange={(value) => setFilter("department", value)}
                />
                <IdSelect
                  label="Company"
                  placeholder="All Companies"
                  value={filters.company}
                  options={masters.companies}
                  onChange={(value) => setFilter("company", value)}
                />
                <IdSelect
                  label="Unit"
                  placeholder="All Units"
                  value={filters.unit}
                  options={units}
                  onChange={(value) => setFilter("unit", value)}
                />
              </div>
              <div className={employeeStyles.filterFooter}>
                <span className={employeeStyles.filterHint}>
                  {activeFilterCount > 0
                    ? `${activeFilterCount} filter${activeFilterCount === 1 ? "" : "s"} applied`
                    : "Employees get ERP access only through onboarding."}
                </span>
                <button
                  type="button"
                  className={`${shared.secondaryBtn} ${employeeStyles.iconBtnLabel}`}
                  onClick={resetFilters}
                >
                  <RefreshIcon />
                  Reset
                </button>
              </div>
            </section>

            <section className={employeeStyles.tableCard}>
              {isLoading ? <p className={shared.loading}>Loading onboarding records…</p> : null}
              {isError ? (
                <p className={shared.error}>
                  Unable to load onboarding records.{" "}
                  <button type="button" className={shared.linkBtn} onClick={() => refetch()}>
                    Retry
                  </button>
                </p>
              ) : null}
              {!isLoading && !isError && rows.length === 0 ? (
                <p className={shared.empty}>
                  {search || activeFilterCount
                    ? "No onboarding records match the search or filters."
                    : "No users onboarded yet. Click Onboard User to invite an employee."}
                </p>
              ) : null}

              {!isLoading && !isError && rows.length > 0 ? (
                <>
                  <div className={employeeStyles.tableWrap}>
                    <table className={`${employeeStyles.table} ${styles.table}`}>
                      <thead>
                        <tr>
                          <th>Employee</th>
                          <th>Login Email</th>
                          <th>Department</th>
                          <th>Role</th>
                          <th>Invitation Status</th>
                          <th>Last Invite</th>
                          <th>Account Status</th>
                          <th className={employeeStyles.actionsHead}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((row) => {
                          const invite = invitationBadge(row);
                          const account = accountStatus(row);
                          const name = row.employee.full_name;
                          return (
                            <tr key={row.id} onClick={() => handleAction(row, "view")}>
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
                                    <span>
                                      {row.employee.employee_code}
                                      <span className={styles.code}> · {row.onboarding_code}</span>
                                    </span>
                                  </div>
                                </div>
                              </td>
                              <td>{row.login_email}</td>
                              <td>{row.employee.department?.name ?? "—"}</td>
                              <td>
                                <Badge label={roleLabel(row.role)} tone={roleTone(row.role)} />
                              </td>
                              <td>
                                <Badge label={invite.label} tone={invite.tone} dot />
                              </td>
                              <td>{formatDateTime(row.last_invite_sent_at)}</td>
                              <td>
                                <Badge label={account.label} tone={account.tone} dot />
                              </td>
                              <td
                                className={employeeStyles.actionsCell}
                                onClick={(event) => event.stopPropagation()}
                              >
                                <div className={employeeStyles.rowActions}>
                                  <button
                                    type="button"
                                    className={`${employeeStyles.iconBtn} ${
                                      menu?.id === row.id ? employeeStyles.iconBtnOpen : ""
                                    }`}
                                    data-action-trigger="true"
                                    aria-label={`Actions for ${name}`}
                                    aria-haspopup="menu"
                                    aria-expanded={menu?.id === row.id}
                                    onClick={(event) =>
                                      setMenu(
                                        menu?.id === row.id
                                          ? null
                                          : anchorFor(
                                              row.id,
                                              event.currentTarget,
                                              row.allowed_actions.length,
                                            ),
                                      )
                                    }
                                  >
                                    <MoreIcon size={15} />
                                  </button>
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
                      {total} record{total === 1 ? "" : "s"}
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
          </>
        )}
      </div>

      {menu && menuRecord ? (
        <RowActionMenu
          anchor={menu}
          onClose={closeMenu}
          items={menuRecord.allowed_actions.map((action) => ({
            key: action,
            label: ACTION_LABELS[action],
            danger: DANGER_ACTIONS.has(action),
            disabled: busy && action !== "view",
            onSelect: () => handleAction(menuRecord, action),
          }))}
        />
      ) : null}

      {createPortal(
        <>
          {panel?.kind === "view" ? (
            <OnboardingDetailsModal
              record={detailQuery.data?.id === panel.id ? detailQuery.data : undefined}
              loading={detailQuery.isFetching && detailQuery.data?.id !== panel.id}
              error={detailQuery.isError ? extractApiError(detailQuery.error) : null}
              busy={busy}
              onClose={() => setPanel(null)}
              onAction={handleAction}
            />
          ) : null}
          {panel?.kind === "form" ? (
            <OnboardingFormDrawer
              key={panel.record?.id ?? "new"}
              record={panel.record}
              onClose={() => setPanel(null)}
              onSaved={onSaved}
            />
          ) : null}
          {confirm ? (
            <ConfirmDialog
              request={confirm}
              busy={busy}
              onCancel={() => setConfirm(null)}
              onConfirm={() => void runConfirm()}
            />
          ) : null}
          {notice ? <NoticeDialog notice={notice} onClose={() => setNotice(null)} /> : null}
          {accessTarget ? (
            <AccessEditorModal
              userId={accessTarget.userId}
              name={accessTarget.name}
              email={accessTarget.email}
              onClose={() => setAccessTarget(null)}
            />
          ) : null}
        </>,
        document.body,
      )}
    </PageContainer>
  );
}

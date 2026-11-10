import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  downloadNameMasterTemplate,
  useActivateEmployeeMutation,
  useBulkSetEmployeeStatusMutation,
  useDeactivateEmployeeMutation,
  useGetEmployeeStatsQuery,
  useGetEmployeesQuery,
  useLazyGetEmployeeQuery,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import {
  CloseIcon,
  EyeIcon,
  MailIcon,
  MoreIcon,
  PlusIcon,
  SearchIcon,
} from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import {
  EMPLOYEE_GENDERS,
  type EmployeeGender,
  type EmployeeListParams,
  type EmployeeListRecord,
  type EmployeeOrdering,
  type EmployeeRecord,
} from "@/types/employee";
import { extractApiError } from "@/utils/extractApiError";
import { EmployeeDetailsModal } from "./EmployeeDetailsModal";
import { avatarColor, formatDate, formatMobile, initials } from "./employeeFormat";
import { EmployeeFormDrawer } from "./EmployeeFormDrawer";
import { EmployeeImportModal } from "./EmployeeImportModal";
import {
  BuildingIcon,
  ChevronIcon,
  DownloadIcon,
  FilterIcon,
  PencilIcon,
  PhoneIcon,
  RefreshIcon,
  SortIcon,
  UploadIcon,
  UserCheckIcon,
  UsersIcon,
} from "./employeeIcons";
import styles from "./EmployeePage.module.css";
import { useDepartmentVerticals, useEmployeeMasters } from "./useEmployeeLookups";

const PAGE_SIZES = [10, 25, 50, 100] as const;

type StatusFilter = "all" | "active" | "inactive";
type IdFilter = number | "";
type Filters = {
  department: IdFilter;
  vertical: IdFilter;
  designation: IdFilter;
  company: IdFilter;
  division: IdFilter;
  facility: IdFilter;
  gender: EmployeeGender | "";
  status: StatusFilter;
};

const EMPTY_FILTERS: Filters = {
  department: "",
  vertical: "",
  designation: "",
  company: "",
  division: "",
  facility: "",
  gender: "",
  status: "all",
};

type SortKey =
  | "full_name"
  | "department"
  | "designation"
  | "company"
  | "division"
  | "date_of_joining"
  | "status";
type Panel = { kind: "view"; id: number } | { kind: "form"; record: EmployeeRecord | null } | null;
type ActionMenuState = { row: EmployeeListRecord; top: number; left: number };
type ConfirmState =
  { kind: "single"; id: number; name: string } | { kind: "bulk"; ids: number[] } | null;

function optional(value: IdFilter) {
  return value === "" ? undefined : value;
}

function pageItems(page: number, totalPages: number): (number | "gap")[] {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const items: (number | "gap")[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);
  if (start > 2) items.push("gap");
  for (let i = start; i <= end; i += 1) items.push(i);
  if (end < totalPages - 1) items.push("gap");
  items.push(totalPages);
  return items;
}

function FilterField({
  label,
  value,
  options,
  onChange,
  disabled,
  placeholder,
}: {
  label: string;
  value: IdFilter;
  options: { id: number; name: string }[] | undefined;
  onChange: (value: IdFilter) => void;
  disabled?: boolean;
  placeholder: string;
}) {
  return (
    <label className={styles.filterField}>
      <span>{label}</span>
      <select
        value={value === "" ? "" : String(value)}
        disabled={disabled}
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

function StatCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: number | undefined;
  icon: ReactNode;
  tone: "blue" | "green" | "purple";
}) {
  return (
    <div className={`${styles.statCard} ${styles[`tone_${tone}`]}`}>
      <span className={styles.statIcon}>{icon}</span>
      <div>
        <span className={styles.statLabel}>{label}</span>
        <strong className={styles.statValue}>{value ?? "—"}</strong>
      </div>
    </div>
  );
}

export function EmployeePage() {
  useDocumentTitle("Master · Employee");
  const { canCreate, canEdit, canUpload, canToggleActive } = useMasterPermissions("employee");
  const accessToken = useAppSelector(selectAccessToken);
  const fileRef = useRef<HTMLInputElement>(null);
  const actionMenuRef = useRef<HTMLDivElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState<Filters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [ordering, setOrdering] = useState<EmployeeOrdering>("employee_code");
  const [pageSize, setPageSize] = useState<number>(10);
  const [page, setPage] = useState(1);
  const [selection, setSelection] = useState<{ key: string; ids: Set<number> }>({
    key: "",
    ids: new Set(),
  });

  const [panel, setPanel] = useState<Panel>(null);
  const [detail, setDetail] = useState<EmployeeRecord | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [actionMenu, setActionMenu] = useState<ActionMenuState | null>(null);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [notice, setNotice] = useState<{ title: string; message: string } | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);

  const masters = useEmployeeMasters();
  const { verticals: draftVerticals } = useDepartmentVerticals(draft.department);

  const queryArgs = useMemo<EmployeeListParams>(
    () => ({
      search,
      page,
      page_size: pageSize,
      ordering,
      is_active: filters.status === "all" ? undefined : filters.status === "active",
      department: optional(filters.department),
      vertical: optional(filters.vertical),
      designation: optional(filters.designation),
      company: optional(filters.company),
      division: optional(filters.division),
      facility: optional(filters.facility),
      gender: filters.gender || undefined,
    }),
    [search, page, pageSize, ordering, filters],
  );
  const queryKey = JSON.stringify(queryArgs);
  const { data, isLoading, isFetching, isError, refetch } = useGetEmployeesQuery(queryArgs);
  const { data: stats } = useGetEmployeeStatsQuery();
  const [fetchEmployee, fetchState] = useLazyGetEmployeeQuery();
  const [deactivateEmployee, deactivateState] = useDeactivateEmployeeMutation();
  const [activateEmployee, activateState] = useActivateEmployeeMutation();
  const [bulkSetStatus, bulkState] = useBulkSetEmployeeStatusMutation();
  const statusBusy = deactivateState.isLoading || activateState.isLoading || bulkState.isLoading;

  const rows = data?.results ?? [];
  const selectedIds = selection.key === queryKey ? selection.ids : new Set<number>();
  const selectedRows = rows.filter((row) => selectedIds.has(row.id));
  const allSelected = rows.length > 0 && selectedRows.length === rows.length;
  const someSelected = selectedRows.length > 0 && !allSelected;

  const totalCount = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const rangeFrom = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeTo = Math.min(page * pageSize, totalCount);
  const activeFilterCount = Object.entries(filters).filter(
    ([key, value]) => value !== "" && !(key === "status" && value === "all"),
  ).length;
  const draftDirty = JSON.stringify(draft) !== JSON.stringify(filters);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (!actionMenu) return;
    const close = () => setActionMenu(null);
    function onPointerDown(event: PointerEvent) {
      const target = event.target as HTMLElement;
      if (actionMenuRef.current?.contains(target)) return;
      if (target.closest?.("[data-action-trigger='true']")) return;
      close();
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [actionMenu]);

  function setDraftFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setDraft((current) => {
      const next = { ...current, [key]: value };
      if (key === "department") next.vertical = "";
      return next;
    });
  }

  function applyFilters() {
    setFilters(draft);
    setPage(1);
  }

  function resetFilters() {
    setDraft(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setSearchInput("");
    setSearch("");
    setPage(1);
  }

  function changePageSize(size: number) {
    setPageSize(size);
    setPage(1);
  }

  function toggleSort(key: SortKey) {
    setPage(1);
    setOrdering((current) => (current === key ? (`-${key}` as EmployeeOrdering) : key));
  }

  function toggleRow(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelection({ key: queryKey, ids: next });
  }

  function toggleAll() {
    setSelection({
      key: queryKey,
      ids: allSelected ? new Set() : new Set(rows.map((row) => row.id)),
    });
  }

  function clearSelection() {
    setSelection({ key: queryKey, ids: new Set() });
  }

  const loadDetail = useCallback(
    async (id: number) => {
      setDetailError(null);
      setDetail(null);
      try {
        const record = await fetchEmployee(id).unwrap();
        setDetail(record);
        return record;
      } catch (err) {
        setDetailError(extractApiError(err));
        return null;
      }
    },
    [fetchEmployee],
  );

  function openView(row: { id: number }) {
    setPanel({ kind: "view", id: row.id });
    void loadDetail(row.id);
  }

  async function openEdit(row: { id: number }) {
    const record = await loadDetail(row.id);
    if (record) setPanel({ kind: "form", record });
    else setNotice({ title: "Unable to open", message: "The employee could not be loaded." });
  }

  function closePanel() {
    setPanel(null);
    setDetail(null);
    setDetailError(null);
  }

  function toggleActionMenu(row: EmployeeListRecord, button: HTMLButtonElement) {
    if (actionMenu?.row.id === row.id) {
      setActionMenu(null);
      return;
    }
    const rect = button.getBoundingClientRect();
    const menuWidth = 168;
    const menuHeight = 56;
    const left = Math.min(Math.max(8, rect.right - menuWidth), window.innerWidth - menuWidth - 8);
    const openUp = rect.bottom + 6 + menuHeight > window.innerHeight;
    const top = openUp ? Math.max(8, rect.top - menuHeight - 6) : rect.bottom + 6;
    setActionMenu({ row, top, left });
  }

  async function confirmDeactivate() {
    if (!confirm) return;
    try {
      if (confirm.kind === "single") {
        await deactivateEmployee(confirm.id).unwrap();
        if (panel?.kind === "view" && panel.id === confirm.id) await loadDetail(confirm.id);
      } else {
        await bulkSetStatus({ ids: confirm.ids, is_active: false }).unwrap();
        clearSelection();
      }
    } catch (err) {
      setNotice({ title: "Action failed", message: extractApiError(err) });
    } finally {
      setConfirm(null);
    }
  }

  async function onActivate(id: number) {
    try {
      const record = await activateEmployee(id).unwrap();
      if (panel?.kind === "view" && panel.id === id) setDetail(record);
    } catch (err) {
      setNotice({ title: "Action failed", message: extractApiError(err) });
    }
  }

  async function onBulkActivate() {
    try {
      await bulkSetStatus({ ids: selectedRows.map((row) => row.id), is_active: true }).unwrap();
      clearSelection();
    } catch (err) {
      setNotice({ title: "Action failed", message: extractApiError(err) });
    }
  }

  async function onDownloadTemplate() {
    setTemplateBusy(true);
    try {
      await downloadNameMasterTemplate("employees", "employee_template.xlsx", accessToken);
    } catch {
      setNotice({ title: "Download failed", message: "Unable to download template." });
    } finally {
      setTemplateBusy(false);
    }
  }

  function onFileSelected(file: File | null) {
    if (fileRef.current) fileRef.current.value = "";
    if (file) setImportFile(file);
  }

  function onSaved(record: EmployeeRecord) {
    setPanel({ kind: "view", id: record.id });
    setDetail(record);
    setDetailError(null);
  }

  const sortHeader = (key: SortKey, label: string) => {
    const direction = ordering === key ? "asc" : ordering === `-${key}` ? "desc" : undefined;
    return (
      <th
        aria-sort={direction === "asc" ? "ascending" : direction === "desc" ? "descending" : "none"}
      >
        <button
          type="button"
          className={`${styles.sortBtn} ${direction ? styles.sortActive : ""}`}
          onClick={() => toggleSort(key)}
        >
          {label}
          <SortIcon direction={direction} />
        </button>
      </th>
    );
  };

  const entriesSelect = (
    <select
      value={pageSize}
      aria-label="Entries per page"
      onChange={(event) => changePageSize(Number(event.target.value))}
    >
      {PAGE_SIZES.map((size) => (
        <option key={size} value={size}>
          {size}
        </option>
      ))}
    </select>
  );

  return (
    <PageContainer>
      <div className={styles.page}>
        <header className={styles.header}>
          <div className={styles.titleBlock}>
            <span className={styles.titleIcon}>
              <UsersIcon size={24} />
            </span>
            <div>
              <h1>Employee Master</h1>
              <p>Manage employee records and organizational assignments.</p>
            </div>
          </div>
          <div className={styles.headerActions}>
            {canUpload ? (
              <>
                <button
                  type="button"
                  className={`${shared.secondaryBtn} ${styles.iconBtnLabel}`}
                  onClick={onDownloadTemplate}
                  disabled={templateBusy}
                >
                  <DownloadIcon />
                  {templateBusy ? "Downloading…" : "Download Template"}
                </button>
                <button
                  type="button"
                  className={`${shared.secondaryBtn} ${styles.iconBtnLabel}`}
                  onClick={() => fileRef.current?.click()}
                  disabled={Boolean(importFile)}
                >
                  <UploadIcon />
                  Upload Excel
                </button>
              </>
            ) : null}
            {canCreate ? (
              <button
                type="button"
                className={`${shared.primaryBtn} ${styles.iconBtnLabel}`}
                onClick={() => setPanel({ kind: "form", record: null })}
              >
                <PlusIcon />
                Add Employee
              </button>
            ) : null}
            <input
              ref={fileRef}
              className={shared.fileInput}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={(event) => onFileSelected(event.target.files?.[0] ?? null)}
            />
          </div>
        </header>

        <section className={styles.stats} aria-label="Employee summary">
          <StatCard
            label="Total Employees"
            value={stats?.total}
            icon={<UsersIcon size={20} />}
            tone="blue"
          />
          <StatCard
            label="Active Employees"
            value={stats?.active}
            icon={<UserCheckIcon size={20} />}
            tone="green"
          />
          <StatCard
            label="Departments"
            value={stats?.departments}
            icon={<BuildingIcon size={20} />}
            tone="purple"
          />
        </section>

        <section className={styles.filterCard}>
          <label className={styles.searchBox}>
            <SearchIcon />
            <input
              type="search"
              placeholder="Search by name, mobile, personal email, company email..."
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label="Search employees"
            />
          </label>

          <div className={styles.filterGrid}>
            <FilterField
              label="Department"
              placeholder="All Departments"
              value={draft.department}
              options={masters.departments}
              onChange={(v) => setDraftFilter("department", v)}
            />
            <FilterField
              label="Vertical"
              placeholder={draft.department === "" ? "Select Department first" : "All Verticals"}
              value={draft.vertical}
              options={draftVerticals}
              disabled={draft.department === ""}
              onChange={(v) => setDraftFilter("vertical", v)}
            />
            <FilterField
              label="Designation"
              placeholder="All Designations"
              value={draft.designation}
              options={masters.designations}
              onChange={(v) => setDraftFilter("designation", v)}
            />
            <FilterField
              label="Company"
              placeholder="All Companies"
              value={draft.company}
              options={masters.companies}
              onChange={(v) => setDraftFilter("company", v)}
            />
            <FilterField
              label="Division"
              placeholder="All Divisions"
              value={draft.division}
              options={masters.divisions}
              onChange={(v) => setDraftFilter("division", v)}
            />
            <FilterField
              label="Facility"
              placeholder="All Facilities"
              value={draft.facility}
              options={masters.facilities}
              onChange={(v) => setDraftFilter("facility", v)}
            />
            <label className={styles.filterField}>
              <span>Gender</span>
              <select
                value={draft.gender}
                onChange={(event) =>
                  setDraftFilter("gender", event.target.value as EmployeeGender | "")
                }
              >
                <option value="">All Genders</option>
                {EMPLOYEE_GENDERS.map((gender) => (
                  <option key={gender} value={gender}>
                    {gender}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.filterField}>
              <span>Status</span>
              <select
                value={draft.status}
                onChange={(event) => setDraftFilter("status", event.target.value as StatusFilter)}
              >
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </label>
          </div>

          <div className={styles.filterFooter}>
            <span className={styles.filterHint}>
              {draftDirty
                ? "Filters changed — click Apply Filters to update the list."
                : activeFilterCount > 0
                  ? `${activeFilterCount} filter${activeFilterCount === 1 ? "" : "s"} applied`
                  : ""}
            </span>
            <div className={styles.filterControls}>
              <label className={styles.entries}>Show {entriesSelect} entries</label>
              <button
                type="button"
                className={`${shared.secondaryBtn} ${styles.iconBtnLabel}`}
                onClick={resetFilters}
              >
                <RefreshIcon />
                Reset
              </button>
              <button
                type="button"
                className={`${shared.primaryBtn} ${styles.iconBtnLabel}`}
                onClick={applyFilters}
              >
                <FilterIcon />
                Apply Filters
              </button>
            </div>
          </div>
        </section>

        <section className={styles.tableCard}>
          {canToggleActive && selectedRows.length > 0 ? (
            <div className={styles.bulkBar}>
              <strong>
                {selectedRows.length} employee{selectedRows.length === 1 ? "" : "s"} selected
              </strong>
              <div className={styles.bulkActions}>
                <button
                  type="button"
                  className={shared.secondaryBtn}
                  disabled={statusBusy}
                  onClick={onBulkActivate}
                >
                  Activate
                </button>
                <button
                  type="button"
                  className={shared.dangerBtn}
                  disabled={statusBusy}
                  onClick={() => setConfirm({ kind: "bulk", ids: selectedRows.map((r) => r.id) })}
                >
                  Deactivate
                </button>
                <button type="button" className={shared.linkBtn} onClick={clearSelection}>
                  Clear selection
                </button>
              </div>
            </div>
          ) : null}

          {isLoading ? <p className={shared.loading}>Loading employees…</p> : null}
          {isError ? (
            <p className={shared.error}>
              Unable to load employees.{" "}
              <button type="button" className={shared.linkBtn} onClick={() => refetch()}>
                Retry
              </button>
            </p>
          ) : null}
          {!isLoading && !isError && data && rows.length === 0 ? (
            <p className={shared.empty}>
              {search || activeFilterCount
                ? "No employees match the search or filters."
                : "No employees yet. Add one or upload Excel."}
            </p>
          ) : null}

          {!isLoading && !isError && rows.length > 0 ? (
            <>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      {canToggleActive ? (
                        <th className={styles.checkCol}>
                          <input
                            type="checkbox"
                            aria-label="Select all employees on this page"
                            checked={allSelected}
                            ref={(el) => {
                              if (el) el.indeterminate = someSelected;
                            }}
                            onChange={toggleAll}
                          />
                        </th>
                      ) : null}
                      {sortHeader("full_name", "Employee")}
                      {sortHeader("department", "Department")}
                      {sortHeader("designation", "Designation")}
                      {sortHeader("company", "Company")}
                      {sortHeader("division", "Division / Facility")}
                      <th>Contact</th>
                      {sortHeader("date_of_joining", "Date Of Joining")}
                      {sortHeader("status", "Status")}
                      <th className={styles.actionsHead}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const email = row.company_email || row.personal_email;
                      const checked = selectedIds.has(row.id);
                      return (
                        <tr
                          key={row.id}
                          className={checked ? styles.rowSelected : undefined}
                          onClick={() => openView(row)}
                        >
                          {canToggleActive ? (
                            <td className={styles.checkCol} onClick={(e) => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                aria-label={`Select ${row.full_name}`}
                                checked={checked}
                                onChange={() => toggleRow(row.id)}
                              />
                            </td>
                          ) : null}
                          <td>
                            <div className={styles.employeeCell}>
                              <span
                                className={styles.avatar}
                                style={{ background: avatarColor(row.full_name) }}
                                aria-hidden="true"
                              >
                                {initials(row.full_name)}
                              </span>
                              <div className={styles.stack}>
                                <strong>{row.full_name}</strong>
                                <span>{row.gender}</span>
                              </div>
                            </div>
                          </td>
                          <td>{row.department.name}</td>
                          <td>{row.designation.name}</td>
                          <td>{row.company.name}</td>
                          <td>
                            <div className={styles.stack}>
                              <strong>{row.division?.name ?? "—"}</strong>
                              <span>{row.facility?.name ?? "—"}</span>
                            </div>
                          </td>
                          <td>
                            <div className={styles.contact}>
                              <a
                                className={styles.contactLine}
                                href={`tel:${row.mobile_number}`}
                                title={`Call ${row.mobile_number}`}
                                onClick={(e) => e.stopPropagation()}
                              >
                                <PhoneIcon size={13} />
                                <span className={styles.contactPhone}>
                                  {formatMobile(row.mobile_number)}
                                </span>
                              </a>
                              {email ? (
                                <a
                                  className={styles.contactLine}
                                  href={`mailto:${email}`}
                                  title={row.company_email ? email : `Personal email: ${email}`}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <MailIcon size={13} />
                                  <span className={styles.contactText}>{email}</span>
                                </a>
                              ) : (
                                <span className={`${styles.contactLine} ${styles.contactEmpty}`}>
                                  <MailIcon size={13} />
                                  <span>No email</span>
                                </span>
                              )}
                            </div>
                          </td>
                          <td>{formatDate(row.date_of_joining)}</td>
                          <td>
                            <span
                              className={`${styles.statusBadge} ${
                                row.is_active ? styles.statusActive : styles.statusInactive
                              }`}
                            >
                              <i aria-hidden="true" />
                              {row.is_active ? "Active" : "Inactive"}
                            </span>
                          </td>
                          <td className={styles.actionsCell} onClick={(e) => e.stopPropagation()}>
                            <div className={styles.rowActions}>
                              <button
                                type="button"
                                className={styles.iconBtn}
                                aria-label={`View ${row.full_name}`}
                                title="View"
                                onClick={() => openView(row)}
                              >
                                <EyeIcon size={15} />
                              </button>
                              {canEdit ? (
                                <button
                                  type="button"
                                  className={styles.iconBtn}
                                  aria-label={`Edit ${row.full_name}`}
                                  title="Edit"
                                  onClick={() => void openEdit(row)}
                                >
                                  <PencilIcon size={15} />
                                </button>
                              ) : null}
                              {canToggleActive ? (
                                <button
                                  type="button"
                                  className={`${styles.iconBtn} ${
                                    actionMenu?.row.id === row.id ? styles.iconBtnOpen : ""
                                  }`}
                                  data-action-trigger="true"
                                  aria-label={`More actions for ${row.full_name}`}
                                  aria-haspopup="menu"
                                  aria-expanded={actionMenu?.row.id === row.id}
                                  onClick={(event) => toggleActionMenu(row, event.currentTarget)}
                                >
                                  <MoreIcon size={15} />
                                </button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <footer className={styles.footer}>
                <span className={styles.footerInfo}>
                  Showing {rangeFrom} to {rangeTo} of {totalCount} employee
                  {totalCount === 1 ? "" : "s"}
                  {isFetching ? " · Refreshing…" : ""}
                </span>
                <nav className={styles.pagination} aria-label="Pagination">
                  <button
                    type="button"
                    className={styles.pageBtn}
                    aria-label="Previous page"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronIcon left />
                  </button>
                  {pageItems(page, totalPages).map((item, index) =>
                    item === "gap" ? (
                      <span key={`gap-${index}`} className={styles.pageGap}>
                        …
                      </span>
                    ) : (
                      <button
                        key={item}
                        type="button"
                        className={`${styles.pageBtn} ${item === page ? styles.pageBtnActive : ""}`}
                        aria-current={item === page ? "page" : undefined}
                        onClick={() => setPage(item)}
                      >
                        {item}
                      </button>
                    ),
                  )}
                  <button
                    type="button"
                    className={styles.pageBtn}
                    aria-label="Next page"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    <ChevronIcon />
                  </button>
                </nav>
                <select
                  className={styles.perPage}
                  value={pageSize}
                  aria-label="Rows per page"
                  onChange={(event) => changePageSize(Number(event.target.value))}
                >
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size} / page
                    </option>
                  ))}
                </select>
              </footer>
            </>
          ) : null}
        </section>
      </div>

      {actionMenu
        ? createPortal(
            <div
              ref={actionMenuRef}
              className={shared.actionsMenu}
              role="menu"
              style={{ top: actionMenu.top, left: actionMenu.left }}
            >
              {actionMenu.row.is_active ? (
                <button
                  type="button"
                  className={`${shared.menuItem} ${shared.menuItemDanger}`}
                  role="menuitem"
                  onClick={() => {
                    setActionMenu(null);
                    setConfirm({
                      kind: "single",
                      id: actionMenu.row.id,
                      name: actionMenu.row.full_name,
                    });
                  }}
                >
                  Deactivate
                </button>
              ) : (
                <button
                  type="button"
                  className={shared.menuItem}
                  role="menuitem"
                  disabled={statusBusy}
                  onClick={() => {
                    setActionMenu(null);
                    void onActivate(actionMenu.row.id);
                  }}
                >
                  Activate
                </button>
              )}
            </div>,
            document.body,
          )
        : null}

      {createPortal(
        <>
          {panel?.kind === "view" ? (
            <EmployeeDetailsModal
              record={detail}
              loading={fetchState.isFetching && !detail}
              error={detailError}
              busy={statusBusy}
              onClose={closePanel}
              onEdit={canEdit ? (record) => setPanel({ kind: "form", record }) : undefined}
              onDeactivate={
                canToggleActive
                  ? (record) =>
                      setConfirm({ kind: "single", id: record.id, name: record.full_name })
                  : undefined
              }
              onActivate={canToggleActive ? (record) => void onActivate(record.id) : undefined}
            />
          ) : null}

          {panel?.kind === "form" ? (
            <EmployeeFormDrawer
              key={panel.record?.id ?? "new"}
              record={panel.record}
              onClose={closePanel}
              onSaved={onSaved}
            />
          ) : null}

          {importFile ? (
            <EmployeeImportModal
              file={importFile}
              onClose={() => setImportFile(null)}
              onFinished={refetch}
            />
          ) : null}

          {confirm ? (
            <>
              <button
                type="button"
                className={shared.backdrop}
                style={{ zIndex: 80 }}
                aria-label="Close"
                onClick={() => !statusBusy && setConfirm(null)}
              />
              <div
                className={shared.modal}
                style={{ zIndex: 90 }}
                role="dialog"
                aria-modal="true"
                data-layer="confirm"
                aria-labelledby="employee-confirm-title"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2 id="employee-confirm-title">
                      {confirm.kind === "bulk" ? "Deactivate Employees" : "Deactivate Employee"}
                    </h2>
                    <p>Deactivated employees can be activated again later.</p>
                  </div>
                  <button
                    type="button"
                    className={shared.closeBtn}
                    aria-label="Close"
                    disabled={statusBusy}
                    onClick={() => setConfirm(null)}
                  >
                    <CloseIcon />
                  </button>
                </div>
                <p className={shared.confirmMessage}>
                  {confirm.kind === "bulk" ? (
                    <>
                      Deactivate <strong>{confirm.ids.length}</strong> selected employee
                      {confirm.ids.length === 1 ? "" : "s"}?
                    </>
                  ) : (
                    <>
                      Deactivate <strong>&quot;{confirm.name}&quot;</strong>?
                    </>
                  )}
                </p>
                <div className={shared.formActions}>
                  <button
                    type="button"
                    className={shared.secondaryBtn}
                    disabled={statusBusy}
                    onClick={() => setConfirm(null)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className={shared.dangerBtn}
                    disabled={statusBusy}
                    onClick={confirmDeactivate}
                  >
                    {statusBusy ? "Please wait…" : "Deactivate"}
                  </button>
                </div>
              </div>
            </>
          ) : null}

          {notice ? (
            <>
              <button
                type="button"
                className={shared.backdrop}
                style={{ zIndex: 80 }}
                aria-label="Close"
                onClick={() => setNotice(null)}
              />
              <div
                className={shared.modal}
                style={{ zIndex: 90 }}
                role="dialog"
                aria-modal="true"
                data-layer="confirm"
                aria-labelledby="employee-notice-title"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2 id="employee-notice-title">{notice.title}</h2>
                    <p>{notice.message}</p>
                  </div>
                  <button
                    type="button"
                    className={shared.closeBtn}
                    aria-label="Close"
                    onClick={() => setNotice(null)}
                  >
                    <CloseIcon />
                  </button>
                </div>
                <div className={shared.formActions}>
                  <button
                    type="button"
                    className={shared.primaryBtn}
                    onClick={() => setNotice(null)}
                  >
                    OK
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </>,
        document.body,
      )}
    </PageContainer>
  );
}

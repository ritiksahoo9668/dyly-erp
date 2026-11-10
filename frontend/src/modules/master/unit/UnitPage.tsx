import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  downloadImportJobErrors,
  downloadNameMasterTemplate,
  useCreateUnitMutation,
  useDeactivateUnitMutation,
  useGetCompaniesQuery,
  useGetUnitsQuery,
  useImportUnitsMutation,
  useLazyGetImportJobQuery,
  useUpdateUnitMutation,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import {
  SearchableSelect,
  type SearchableSelectOption,
} from "@/components/common/SearchableSelect";
import { CloseIcon, MoreIcon, SearchIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import type { ImportJob } from "@/types/nameMaster";
import type { UnitRecord } from "@/types/unit";
import { extractApiError } from "@/utils/extractApiError";
import styles from "@/modules/master/shared/NameMasterPage.module.css";

type ModalMode = "create" | "edit" | "view" | "import" | null;

const TERMINAL_JOB_STATUSES = new Set(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]);

type ConfirmDialog = {
  action: "delete" | "deactivate";
  row: UnitRecord;
};

type NoticeDialog = {
  title: string;
  message: string;
};

type ActionMenuState = {
  row: UnitRecord;
  top: number;
  left: number;
};

type StatusFilter = "all" | "active" | "inactive";

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function UnitPage() {
  const { canCreate, canEdit, canUpload, canToggleActive } = useMasterPermissions("unit");
  useDocumentTitle("Master · Unit");
  const accessToken = useAppSelector(selectAccessToken);
  const fileRef = useRef<HTMLInputElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [companyFilter, setCompanyFilter] = useState<number | "">("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState<ModalMode>(null);
  const [selected, setSelected] = useState<UnitRecord | null>(null);
  const [name, setName] = useState("");
  const [companyId, setCompanyId] = useState<number | "">("");
  const [isActive, setIsActive] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const [errorDownloadBusy, setErrorDownloadBusy] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog | null>(null);
  const [noticeDialog, setNoticeDialog] = useState<NoticeDialog | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [actionMenu, setActionMenu] = useState<ActionMenuState | null>(null);
  const actionMenuRef = useRef<HTMLDivElement>(null);

  const queryArgs = useMemo(
    () => ({
      search,
      page,
      company: typeof companyFilter === "number" ? companyFilter : undefined,
      is_active: statusFilter === "all" ? undefined : statusFilter === "active",
    }),
    [search, page, companyFilter, statusFilter],
  );

  const { data, isLoading, isFetching, isError, refetch } = useGetUnitsQuery(queryArgs);
  const { data: companiesData } = useGetCompaniesQuery({ lookup: true, page_size: 500 });
  const [createRecord, createState] = useCreateUnitMutation();
  const [updateRecord, updateState] = useUpdateUnitMutation();
  const [deleteRecord, deleteState] = useDeactivateUnitMutation();
  const [importRecords, importState] = useImportUnitsMutation();
  const [fetchImportJob] = useLazyGetImportJobQuery();
  const importBusy =
    importState.isLoading ||
    Boolean(importJob && !TERMINAL_JOB_STATUSES.has(importJob.status));

  const companies = useMemo(() => companiesData?.results ?? [], [companiesData]);
  const totalPages = Math.max(1, Math.ceil((data?.count ?? 0) / 20));
  const saving = createState.isLoading || updateState.isLoading;

  const companyOptions = useMemo<SearchableSelectOption[]>(() => {
    const currentId = selected?.company.id;
    const options = companies
      .filter((company) => company.is_active || company.id === currentId)
      .map((company) => ({
        value: company.id,
        label: company.name,
        hint: company.is_active ? undefined : "Inactive",
      }));
    if (selected && !options.some((option) => option.value === selected.company.id)) {
      options.push({
        value: selected.company.id,
        label: selected.company.name,
        hint: selected.company.is_active ? undefined : "Inactive",
      });
    }
    return options;
  }, [companies, selected]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [companyFilter, statusFilter]);

  useEffect(() => {
    if (!actionMenu) return;

    function closeMenu() {
      setActionMenu(null);
    }

    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (actionMenuRef.current?.contains(target)) return;
      if ((target as HTMLElement).closest?.("[data-action-trigger='true']")) return;
      closeMenu();
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeMenu();
    }

    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("resize", closeMenu);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("resize", closeMenu);
    };
  }, [actionMenu]);

  function openCreate() {
    setSelected(null);
    setName("");
    setCompanyId(typeof companyFilter === "number" ? companyFilter : "");
    setIsActive(true);
    setFormError(null);
    setModal("create");
  }

  function openEdit(row: UnitRecord) {
    setSelected(row);
    setName(row.name);
    setCompanyId(row.company.id);
    setIsActive(row.is_active);
    setFormError(null);
    setModal("edit");
  }

  function openView(row: UnitRecord) {
    setSelected(row);
    setFormError(null);
    setModal("view");
  }

  function closeModal() {
    setModal(null);
    setSelected(null);
    setFormError(null);
    setImportJob(null);
  }

  function showNotice(title: string, message: string) {
    setNoticeDialog({ title, message });
  }

  function toggleActionMenu(row: UnitRecord, button: HTMLButtonElement) {
    if (actionMenu?.row.id === row.id) {
      setActionMenu(null);
      return;
    }
    const rect = button.getBoundingClientRect();
    const menuWidth = 168;
    const menuHeight = 180;
    const gap = 6;
    const left = Math.min(
      Math.max(8, rect.right - menuWidth),
      window.innerWidth - menuWidth - 8,
    );
    const openUp = rect.bottom + gap + menuHeight > window.innerHeight;
    const top = openUp
      ? Math.max(8, rect.top - menuHeight - gap)
      : Math.min(rect.bottom + gap, window.innerHeight - menuHeight - 8);
    setActionMenu({ row, top, left });
  }

  function runMenuAction(action: () => void) {
    setActionMenu(null);
    action();
  }

  function askDelete(row: UnitRecord) {
    setConfirmDialog({ action: "delete", row });
  }

  function askDeactivate(row: UnitRecord) {
    if (!row.is_active) return;
    setConfirmDialog({ action: "deactivate", row });
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const cleaned = name.trim();
    if (!cleaned) {
      setFormError("Unit Name is required.");
      return;
    }
    if (companyId === "") {
      setFormError("Company is required.");
      return;
    }
    try {
      if (modal === "create") {
        await createRecord({ name: cleaned, company_id: companyId, is_active: isActive }).unwrap();
      } else if (modal === "edit" && selected) {
        await updateRecord({
          id: selected.id,
          body: { name: cleaned, company_id: companyId, is_active: isActive },
        }).unwrap();
      }
      closeModal();
    } catch (err) {
      setFormError(extractApiError(err));
    }
  }

  async function confirmAction() {
    if (!confirmDialog) return;
    const { action, row } = confirmDialog;
    setConfirmBusy(true);
    try {
      if (action === "delete") {
        await deleteRecord(row.id).unwrap();
        if (selected?.id === row.id) closeModal();
      } else {
        await updateRecord({ id: row.id, body: { is_active: false } }).unwrap();
      }
      setConfirmDialog(null);
    } catch (err) {
      setConfirmDialog(null);
      showNotice("Action failed", extractApiError(err));
    } finally {
      setConfirmBusy(false);
    }
  }

  async function onActivate(row: UnitRecord) {
    if (row.is_active) return;
    try {
      await updateRecord({ id: row.id, body: { is_active: true } }).unwrap();
    } catch (err) {
      showNotice("Action failed", extractApiError(err));
    }
  }

  async function onDownloadTemplate() {
    setTemplateBusy(true);
    try {
      await downloadNameMasterTemplate("units", "unit_template.xlsx", accessToken);
    } catch {
      showNotice("Download failed", "Unable to download template.");
    } finally {
      setTemplateBusy(false);
    }
  }

  async function onFileSelected(file: File | null) {
    if (!file) return;
    setFormError(null);
    setImportJob(null);
    setModal("import");
    try {
      const job = await importRecords(file).unwrap();
      setImportJob(job);
    } catch (err) {
      setFormError(extractApiError(err));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  useEffect(() => {
    if (!importJob || TERMINAL_JOB_STATUSES.has(importJob.status)) return;

    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchImportJob(importJob.id).unwrap();
        if (!cancelled) {
          setImportJob(latest);
          if (TERMINAL_JOB_STATUSES.has(latest.status)) {
            refetch();
          }
        }
      } catch {
        // Keep polling on transient errors.
      }
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [importJob, fetchImportJob, refetch]);

  async function onDownloadErrors() {
    if (!importJob?.has_error_file) return;
    setErrorDownloadBusy(true);
    try {
      await downloadImportJobErrors(importJob.id, accessToken);
    } catch {
      showNotice("Download failed", "Unable to download error file.");
    } finally {
      setErrorDownloadBusy(false);
    }
  }

  return (
    <PageContainer>
      <div className={styles.page}>
        <div className={styles.toolbar}>
          <div className={styles.heading}>
            <h1>Unit</h1>
            <p>Manage units linked to companies.</p>
          </div>
          <div className={styles.actions}>
            {canUpload ? (
              <>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={onDownloadTemplate}
                  disabled={templateBusy}
                >
                  {templateBusy ? "Downloading…" : "Download Template"}
                </button>
                <button
                  type="button"
                  className={styles.ghostBtn}
                  onClick={() => fileRef.current?.click()}
                  disabled={importBusy}
                >
                  Upload Excel
                </button>
              </>
            ) : null}
            {canCreate ? (
              <button type="button" className={styles.primaryBtn} onClick={openCreate}>
                Add Unit
              </button>
            ) : null}
            <input
              ref={fileRef}
              className={styles.fileInput}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={(event) => onFileSelected(event.target.files?.[0] ?? null)}
            />
          </div>
        </div>

        <div className={styles.filters}>
          <label className={styles.search}>
            <span className={styles.searchIcon} aria-hidden="true">
              <SearchIcon />
            </span>
            <input
              type="search"
              placeholder="Search by Unit Name"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label="Search units"
            />
          </label>
          <select
            className={styles.filterSelect}
            value={companyFilter === "" ? "" : String(companyFilter)}
            onChange={(event) => {
              const value = event.target.value;
              setCompanyFilter(value ? Number(value) : "");
            }}
            aria-label="Filter by Company"
          >
            <option value="">All Companies</option>
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name}
              </option>
            ))}
          </select>
          <select
            className={styles.filterSelect}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
            aria-label="Filter by Status"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>

        <div className={styles.panel}>
          {isLoading ? <p className={styles.loading}>Loading units…</p> : null}
          {isError ? (
            <p className={styles.error}>
              Unable to load units.{" "}
              <button type="button" className={styles.linkBtn} onClick={() => refetch()}>
                Retry
              </button>
            </p>
          ) : null}
          {!isLoading && !isError && data && data.results.length === 0 ? (
            <p className={styles.empty}>No units found. Add one or upload Excel.</p>
          ) : null}
          {!isLoading && !isError && data && data.results.length > 0 ? (
            <>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Unit Name</th>
                      <th>Company</th>
                      <th>Status</th>
                      <th>Updated</th>
                      <th className={styles.actionsCol}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <strong>{row.name}</strong>
                        </td>
                        <td>{row.company.name}</td>
                        <td>
                          <span
                            className={`${styles.badge} ${
                              row.is_active ? styles.badgeActive : styles.badgeInactive
                            }`}
                          >
                            {row.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td>{formatDate(row.updated_at)}</td>
                        <td className={styles.actionsCol}>
                          <div className={styles.rowActions}>
                            <button
                              type="button"
                              className={`${styles.actionsTrigger} ${
                                actionMenu?.row.id === row.id ? styles.actionsTriggerOpen : ""
                              }`}
                              data-action-trigger="true"
                              aria-label={`Actions for ${row.name}`}
                              aria-haspopup="menu"
                              aria-expanded={actionMenu?.row.id === row.id}
                              onClick={(event) => {
                                event.stopPropagation();
                                toggleActionMenu(row, event.currentTarget);
                              }}
                            >
                              <MoreIcon size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className={styles.pager}>
                <span>
                  {data.count} total · Page {page} of {totalPages}
                  {isFetching ? " · Refreshing…" : ""}
                </span>
                <div className={styles.pagerControls}>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    disabled={page <= 1}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    disabled={page >= totalPages}
                    onClick={() => setPage((value) => value + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {actionMenu
        ? createPortal(
            <div
              ref={actionMenuRef}
              className={styles.actionsMenu}
              role="menu"
              style={{ top: actionMenu.top, left: actionMenu.left }}
            >
              <button
                type="button"
                className={styles.menuItem}
                role="menuitem"
                onClick={() => runMenuAction(() => openView(actionMenu.row))}
              >
                View
              </button>
              {canEdit ? (
                <button
                  type="button"
                  className={styles.menuItem}
                  role="menuitem"
                  onClick={() => runMenuAction(() => openEdit(actionMenu.row))}
                >
                  Edit
                </button>
              ) : null}
              {canToggleActive ? (
                <>
                  <button
                    type="button"
                    className={`${styles.menuItem} ${styles.menuItemDanger}`}
                    role="menuitem"
                    onClick={() => runMenuAction(() => askDelete(actionMenu.row))}
                    disabled={deleteState.isLoading}
                  >
                    Delete
                  </button>
                  {actionMenu.row.is_active ? (
                    <button
                      type="button"
                      className={styles.menuItem}
                      role="menuitem"
                      onClick={() => runMenuAction(() => askDeactivate(actionMenu.row))}
                      disabled={updateState.isLoading}
                    >
                      Deactivate
                    </button>
                  ) : (
                    <button
                      type="button"
                      className={styles.menuItem}
                      role="menuitem"
                      onClick={() => runMenuAction(() => onActivate(actionMenu.row))}
                      disabled={updateState.isLoading}
                    >
                      Activate
                    </button>
                  )}
                </>
              ) : null}
            </div>,
            document.body,
          )
        : null}

      {modal === "create" || modal === "edit" ? (
        <>
          <button type="button" className={styles.backdrop} aria-label="Close" onClick={closeModal} />
          <div className={styles.modal} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>{modal === "create" ? "Add Unit" : "Edit Unit"}</h2>
                <p>Unit Name and Company are required.</p>
              </div>
              <button type="button" className={styles.closeBtn} aria-label="Close" onClick={closeModal}>
                <CloseIcon />
              </button>
            </div>
            <form className={styles.form} onSubmit={onSubmit}>
              {formError ? <p className={styles.formError}>{formError}</p> : null}
              <div className={styles.field}>
                <label htmlFor="unit-name">Unit Name *</label>
                <input
                  id="unit-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoFocus
                  required
                  maxLength={150}
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="unit-company">Company *</label>
                <SearchableSelect
                  id="unit-company"
                  value={companyId}
                  options={companyOptions}
                  onChange={setCompanyId}
                  placeholder="Select company"
                  searchPlaceholder="Search company…"
                  emptyText="No matching company in Company Master."
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="unit-status">Status</label>
                <select
                  id="unit-status"
                  value={isActive ? "active" : "inactive"}
                  onChange={(event) => setIsActive(event.target.value === "active")}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
              <div className={styles.formActions}>
                <button type="button" className={styles.secondaryBtn} onClick={closeModal}>
                  Cancel
                </button>
                <button type="submit" className={styles.primaryBtn} disabled={saving}>
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </>
      ) : null}

      {modal === "view" && selected ? (
        <>
          <button type="button" className={styles.backdrop} aria-label="Close" onClick={closeModal} />
          <div className={styles.modal} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>View Unit</h2>
                <p>Read-only unit details.</p>
              </div>
              <button type="button" className={styles.closeBtn} aria-label="Close" onClick={closeModal}>
                <CloseIcon />
              </button>
            </div>
            <div className={styles.detailGrid}>
              <div className={styles.detailRow}>
                <span>Unit Name</span>
                <strong>{selected.name}</strong>
              </div>
              <div className={styles.detailRow}>
                <span>Company</span>
                <strong>{selected.company.name}</strong>
              </div>
              <div className={styles.detailRow}>
                <span>Status</span>
                <strong>{selected.is_active ? "Active" : "Inactive"}</strong>
              </div>
              <div className={styles.detailRow}>
                <span>Created</span>
                <strong>{formatDate(selected.created_at)}</strong>
              </div>
              <div className={styles.detailRow}>
                <span>Updated</span>
                <strong>{formatDate(selected.updated_at)}</strong>
              </div>
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.secondaryBtn} onClick={closeModal}>
                Close
              </button>
              {canEdit ? (
                <button type="button" className={styles.primaryBtn} onClick={() => openEdit(selected)}>
                  Edit
                </button>
              ) : null}
            </div>
          </div>
        </>
      ) : null}

      {modal === "import" ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close"
            onClick={() => {
              if (!importBusy) closeModal();
            }}
          />
          <div className={`${styles.modal} ${styles.importModal}`} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>
                  {importJob && TERMINAL_JOB_STATUSES.has(importJob.status)
                    ? importJob.status === "FAILED"
                      ? "Import Failed"
                      : "Import Completed"
                    : "Excel Import"}
                </h2>
                <p>
                  {importJob
                    ? importJob.progress_label || importJob.detail || "Processing in the background…"
                    : "Uploading file and starting background import…"}
                </p>
              </div>
              <button
                type="button"
                className={styles.closeBtn}
                aria-label="Close"
                disabled={importBusy && !formError}
                onClick={closeModal}
              >
                <CloseIcon />
              </button>
            </div>
            {importState.isLoading ? <p className={styles.loading}>Uploading…</p> : null}
            {formError ? <p className={styles.formError}>{formError}</p> : null}
            {importJob ? (
              <>
                <div className={styles.progressBlock}>
                  <div className={styles.progressMeta}>
                    <strong>{importJob.status.replaceAll("_", " ")}</strong>
                    <span>{importJob.progress_label}</span>
                  </div>
                  <div className={styles.progressTrack}>
                    <div
                      className={styles.progressFill}
                      style={{ width: `${importJob.progress_percentage}%` }}
                    />
                  </div>
                </div>
                <div className={styles.summary}>
                  <div className={styles.summaryCard}>
                    <span>Total Rows</span>
                    <strong>{importJob.total_rows}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Processed</span>
                    <strong>{importJob.processed_rows}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Created</span>
                    <strong>{importJob.created_rows}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Skipped Existing</span>
                    <strong>{importJob.skipped_rows}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Failed</span>
                    <strong>{importJob.failed_rows}</strong>
                  </div>
                </div>
                {importJob.detail ? <p className={styles.importDetail}>{importJob.detail}</p> : null}
                <div className={styles.formActions}>
                  {importJob.has_error_file ? (
                    <button
                      type="button"
                      className={styles.secondaryBtn}
                      disabled={errorDownloadBusy}
                      onClick={onDownloadErrors}
                    >
                      {errorDownloadBusy ? "Downloading…" : "Download Error Excel"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className={styles.primaryBtn}
                    disabled={importBusy && !TERMINAL_JOB_STATUSES.has(importJob.status)}
                    onClick={closeModal}
                  >
                    {TERMINAL_JOB_STATUSES.has(importJob.status) ? "Done" : "Running…"}
                  </button>
                </div>
              </>
            ) : null}
            {formError && !importJob ? (
              <div className={styles.formActions}>
                <button type="button" className={styles.primaryBtn} onClick={closeModal}>
                  Close
                </button>
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      {confirmDialog ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close"
            onClick={() => !confirmBusy && setConfirmDialog(null)}
          />
          <div className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <div className={styles.modalHeader}>
              <div>
                <h2 id="confirm-title">
                  {confirmDialog.action === "delete" ? "Delete Unit" : "Deactivate Unit"}
                </h2>
                <p>
                  {confirmDialog.action === "delete"
                    ? "This will permanently remove the record."
                    : "The record will be marked inactive and can be activated later."}
                </p>
              </div>
              <button
                type="button"
                className={styles.closeBtn}
                aria-label="Close"
                disabled={confirmBusy}
                onClick={() => setConfirmDialog(null)}
              >
                <CloseIcon />
              </button>
            </div>
            <p className={styles.confirmMessage}>
              {confirmDialog.action === "delete" ? (
                <>
                  Permanently delete unit <strong>&quot;{confirmDialog.row.name}&quot;</strong>? This
                  cannot be undone.
                </>
              ) : (
                <>
                  Deactivate unit <strong>&quot;{confirmDialog.row.name}&quot;</strong>?
                </>
              )}
            </p>
            <div className={styles.formActions}>
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={confirmBusy}
                onClick={() => setConfirmDialog(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={confirmDialog.action === "delete" ? styles.dangerBtn : styles.primaryBtn}
                disabled={confirmBusy}
                onClick={confirmAction}
              >
                {confirmBusy
                  ? "Please wait…"
                  : confirmDialog.action === "delete"
                    ? "Delete"
                    : "Deactivate"}
              </button>
            </div>
          </div>
        </>
      ) : null}

      {noticeDialog ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close"
            onClick={() => setNoticeDialog(null)}
          />
          <div className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="notice-title">
            <div className={styles.modalHeader}>
              <div>
                <h2 id="notice-title">{noticeDialog.title}</h2>
                <p>{noticeDialog.message}</p>
              </div>
              <button
                type="button"
                className={styles.closeBtn}
                aria-label="Close"
                onClick={() => setNoticeDialog(null)}
              >
                <CloseIcon />
              </button>
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.primaryBtn} onClick={() => setNoticeDialog(null)}>
                OK
              </button>
            </div>
          </div>
        </>
      ) : null}
    </PageContainer>
  );
}

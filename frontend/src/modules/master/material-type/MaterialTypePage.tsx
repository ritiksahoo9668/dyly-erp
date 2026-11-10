import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  downloadImportJobErrors,
  downloadNameMasterTemplate,
  useCreateMaterialTypeMutation,
  useDeactivateMaterialTypeMutation,
  useGetMaterialTypesQuery,
  useImportMaterialTypesMutation,
  useLazyGetImportJobQuery,
  useUpdateMaterialTypeMutation,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import { CloseIcon, MoreIcon, SearchIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import type { ImportJob } from "@/types/nameMaster";
import type { MaterialTypeRecord } from "@/types/materialType";
import { extractApiError } from "@/utils/extractApiError";
import styles from "@/modules/master/shared/NameMasterPage.module.css";

type ModalMode = "create" | "edit" | "view" | "import" | null;
type StatusFilter = "all" | "active" | "inactive";

const TERMINAL_JOB_STATUSES = new Set(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]);

type ConfirmDialog = { action: "delete" | "deactivate"; row: MaterialTypeRecord };
type NoticeDialog = { title: string; message: string };
type ActionMenuState = { row: MaterialTypeRecord; top: number; left: number };

function extractError(error: unknown): string {
  return extractApiError(error);
}

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

export function MaterialTypePage() {
  const { canCreate, canEdit, canUpload, canToggleActive } = useMasterPermissions("material-type");
  useDocumentTitle("Master · Material Type");
  const accessToken = useAppSelector(selectAccessToken);
  const fileRef = useRef<HTMLInputElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState<ModalMode>(null);
  const [selected, setSelected] = useState<MaterialTypeRecord | null>(null);
  const [desc, setDesc] = useState("");
  const [sapCode, setSapCode] = useState("");
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
      is_active: statusFilter === "all" ? undefined : statusFilter === "active",
    }),
    [search, page, statusFilter],
  );

  const { data, isLoading, isFetching, isError, refetch } = useGetMaterialTypesQuery(queryArgs);
  const [createRecord, createState] = useCreateMaterialTypeMutation();
  const [updateRecord, updateState] = useUpdateMaterialTypeMutation();
  const [deleteRecord, deleteState] = useDeactivateMaterialTypeMutation();
  const [importRecords, importState] = useImportMaterialTypesMutation();
  const [fetchImportJob] = useLazyGetImportJobQuery();
  const importBusy =
    importState.isLoading ||
    Boolean(importJob && !TERMINAL_JOB_STATUSES.has(importJob.status));
  const totalPages = Math.max(1, Math.ceil((data?.count ?? 0) / 20));
  const saving = createState.isLoading || updateState.isLoading;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter]);

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

  useEffect(() => {
    if (!importJob || TERMINAL_JOB_STATUSES.has(importJob.status)) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchImportJob(importJob.id).unwrap();
        if (!cancelled) {
          setImportJob(latest);
          if (TERMINAL_JOB_STATUSES.has(latest.status)) refetch();
        }
      } catch {
        // keep polling
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [importJob, fetchImportJob, refetch]);

  function openCreate() {
    setSelected(null);
    setDesc("");
    setSapCode("");
    setFormError(null);
    setModal("create");
  }

  function openEdit(row: MaterialTypeRecord) {
    setSelected(row);
    setDesc(row.erp_category_desc);
    setSapCode(row.material_type_code);
    setFormError(null);
    setModal("edit");
  }

  function openView(row: MaterialTypeRecord) {
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

  function toggleActionMenu(row: MaterialTypeRecord, button: HTMLButtonElement) {
    if (actionMenu?.row.id === row.id) {
      setActionMenu(null);
      return;
    }
    const rect = button.getBoundingClientRect();
    const menuWidth = 168;
    const menuHeight = 180;
    const gap = 6;
    const left = Math.min(Math.max(8, rect.right - menuWidth), window.innerWidth - menuWidth - 8);
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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const cleanedCode = sapCode.trim();
    const cleanedDesc = desc.trim();
    if (!cleanedCode) {
      setFormError("Material Type Code is required.");
      return;
    }
    if (!cleanedDesc) {
      setFormError("ERP Category Desc is required.");
      return;
    }
    try {
      if (modal === "create") {
        await createRecord({
          material_type_code: cleanedCode,
          erp_category_desc: cleanedDesc,
        }).unwrap();
      } else if (modal === "edit" && selected) {
        await updateRecord({
          id: selected.id,
          body: {
            material_type_code: cleanedCode,
            erp_category_desc: cleanedDesc,
            is_active: selected.is_active,
          },
        }).unwrap();
      }
      closeModal();
    } catch (err) {
      setFormError(extractError(err));
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
        await updateRecord({
          id: row.id,
          body: { material_type_code: row.material_type_code, erp_category_desc: row.erp_category_desc, is_active: false },
        }).unwrap();
      }
      setConfirmDialog(null);
    } catch (err) {
      setConfirmDialog(null);
      showNotice("Action failed", extractError(err));
    } finally {
      setConfirmBusy(false);
    }
  }

  async function onActivate(row: MaterialTypeRecord) {
    if (row.is_active) return;
    try {
      await updateRecord({
        id: row.id,
        body: { material_type_code: row.material_type_code, erp_category_desc: row.erp_category_desc, is_active: true },
      }).unwrap();
    } catch (err) {
      showNotice("Action failed", extractError(err));
    }
  }

  async function onDownloadTemplate() {
    setTemplateBusy(true);
    try {
      await downloadNameMasterTemplate("material-types", "material_type_template.xlsx", accessToken);
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
      setFormError(extractError(err));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

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
            <h1>Material Type</h1>
            <p>Manage SAP material types for DYLY ERP.</p>
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
                Add Material Type
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
              placeholder="Search by Material Type Code or ERP Category Desc"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label="Search material types"
            />
          </label>
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
          {isLoading ? <p className={styles.loading}>Loading material types…</p> : null}
          {isError ? (
            <p className={styles.error}>
              Unable to load material types.{" "}
              <button type="button" className={styles.linkBtn} onClick={() => refetch()}>
                Retry
              </button>
            </p>
          ) : null}
          {!isLoading && !isError && data && data.results.length === 0 ? (
            <p className={styles.empty}>No material types found. Add one or upload Excel.</p>
          ) : null}
          {!isLoading && !isError && data && data.results.length > 0 ? (
            <>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Material Type Code</th>
                      <th>ERP Category Desc</th>
                      <th>Status</th>
                      <th>Updated</th>
                      <th className={styles.actionsCol}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <strong>{row.material_type_code}</strong>
                        </td>
                        <td>{row.erp_category_desc}</td>
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
                              aria-label={`Actions for ${row.erp_category_desc}`}
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
                    onClick={() => runMenuAction(() => setConfirmDialog({ action: "delete", row: actionMenu.row }))}
                    disabled={deleteState.isLoading}
                  >
                    Delete
                  </button>
                  {actionMenu.row.is_active ? (
                    <button
                      type="button"
                      className={styles.menuItem}
                      role="menuitem"
                      onClick={() =>
                        runMenuAction(() => setConfirmDialog({ action: "deactivate", row: actionMenu.row }))
                      }
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
                <h2>{modal === "create" ? "Add Material Type" : "Edit Material Type"}</h2>
                <p>Material Type Code and ERP Category Desc are required.</p>
              </div>
              <button type="button" className={styles.closeBtn} aria-label="Close" onClick={closeModal}>
                <CloseIcon />
              </button>
            </div>
            <form className={styles.form} onSubmit={onSubmit}>
              {formError ? <p className={styles.formError}>{formError}</p> : null}
              <div className={styles.field}>
                <label htmlFor="material-type-code">Material Type Code</label>
                <input
                  id="material-type-code"
                  value={sapCode}
                  onChange={(event) => setSapCode(event.target.value)}
                  autoFocus
                  required
                  maxLength={50}
                />
              </div>
              <div className={styles.field}>
                <label htmlFor="material-type-desc">ERP Category Desc</label>
                <input
                  id="material-type-desc"
                  value={desc}
                  onChange={(event) => setDesc(event.target.value)}
                  required
                  maxLength={150}
                />
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
                <h2>View Material Type</h2>
                <p>Read-only material type details.</p>
              </div>
              <button type="button" className={styles.closeBtn} aria-label="Close" onClick={closeModal}>
                <CloseIcon />
              </button>
            </div>
            <div className={styles.detailGrid}>
              <div className={styles.detailRow}>
                <span>Material Type Code</span>
                <strong>{selected.material_type_code}</strong>
              </div>
              <div className={styles.detailRow}>
                <span>ERP Category Desc</span>
                <strong>{selected.erp_category_desc}</strong>
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
          <div className={styles.modal} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>
                  {confirmDialog.action === "delete" ? "Delete Material Type" : "Deactivate Material Type"}
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
                  Permanently delete material type <strong>&quot;{confirmDialog.row.erp_category_desc}&quot;</strong>?
                </>
              ) : (
                <>
                  Deactivate Material Type <strong>&quot;{confirmDialog.row.erp_category_desc}&quot;</strong>?
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
          <div className={styles.modal} role="dialog" aria-modal="true">
            <div className={styles.modalHeader}>
              <div>
                <h2>{noticeDialog.title}</h2>
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

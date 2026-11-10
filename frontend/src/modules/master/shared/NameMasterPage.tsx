import { type FormEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  downloadImportJobErrors,
  downloadNameMasterTemplate,
  useLazyGetImportJobQuery,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import { CloseIcon, MoreIcon, SearchIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import type {
  ImportJob,
  NameMasterImportPreview,
  NameMasterListParams,
  NameMasterListResponse,
  NameMasterRecord,
  NameMasterResource,
  NameMasterWritePayload,
} from "@/types/nameMaster";
import { extractApiError } from "@/utils/extractApiError";
import styles from "./NameMasterPage.module.css";

type ModalMode = "create" | "edit" | "view" | "import" | null;

type ConfirmDialog = {
  action: "delete" | "deactivate";
  row: NameMasterRecord;
};

type NoticeDialog = {
  title: string;
  message: string;
};

type ActionMenuState = {
  row: NameMasterRecord;
  top: number;
  left: number;
};

type Unwrapable<T> = { unwrap: () => Promise<T> };

const TERMINAL_JOB_STATUSES = new Set(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]);

export type NameMasterApiHooks = {
  useListQuery: (params: NameMasterListParams | void) => {
    data?: NameMasterListResponse;
    isLoading: boolean;
    isFetching: boolean;
    isError: boolean;
    refetch: () => void;
  };
  useCreateMutation: () => readonly [
    (arg: NameMasterWritePayload) => Unwrapable<NameMasterRecord>,
    { isLoading: boolean },
  ];
  useUpdateMutation: () => readonly [
    (arg: { id: number; body: NameMasterWritePayload }) => Unwrapable<NameMasterRecord>,
    { isLoading: boolean },
  ];
  useDeleteMutation: () => readonly [
    (arg: number) => Unwrapable<unknown>,
    { isLoading: boolean },
  ];
  useImportMutation: () => readonly [
    (arg: File) => Unwrapable<ImportJob>,
    { isLoading: boolean },
  ];
  /** When provided, uploads are validated and previewed before the background import starts. */
  useValidateMutation?: () => readonly [
    (arg: File) => Unwrapable<NameMasterImportPreview>,
    { isLoading: boolean },
  ];
};

export type NameMasterPageConfig = {
  title: string;
  singular: string;
  plural: string;
  nameLabel: string;
  description: string;
  resource: NameMasterResource;
  templateFilename: string;
  hooks: NameMasterApiHooks;
  showStatusFilter?: boolean;
  renderViewDetails?: (record: NameMasterRecord) => ReactNode;
  extraColumns?: { header: string; render: (record: NameMasterRecord) => ReactNode }[];
  extraActions?: {
    label: string;
    visible?: (record: NameMasterRecord) => boolean;
    onSelect: (record: NameMasterRecord) => void;
  }[];
  /** Extra fields in the Add/Edit form. `onSaved` runs after the record is saved and returns an error message, if any. */
  formSection?: {
    render: (record: NameMasterRecord | null) => ReactNode;
    onSaved: (record: NameMasterRecord) => Promise<string | null>;
  };
};

type StatusFilter = "all" | "active" | "inactive";

const noopValidate = () =>
  [
    (() => ({ unwrap: () => Promise.reject(new Error("Validation is not configured.")) })) as (
      arg: File,
    ) => Unwrapable<NameMasterImportPreview>,
    { isLoading: false },
  ] as const;

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

const STAGE_BY_RESOURCE: Record<NameMasterResource, string> = {
  divisions: "division",
  departments: "department",
  designations: "designation",
  facilities: "facility",
  companies: "company",
  "material-categories": "material-category",
  weighbridges: "weighbridge",
};

export function NameMasterPage({ config }: { config: NameMasterPageConfig }) {
  useDocumentTitle(`Master · ${config.title}`);
  const accessToken = useAppSelector(selectAccessToken);
  const { canCreate, canEdit, canUpload, canToggleActive } = useMasterPermissions(
    STAGE_BY_RESOURCE[config.resource],
  );
  const fileRef = useRef<HTMLInputElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState<ModalMode>(null);
  const [selected, setSelected] = useState<NameMasterRecord | null>(null);
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const [errorDownloadBusy, setErrorDownloadBusy] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialog | null>(null);
  const [noticeDialog, setNoticeDialog] = useState<NoticeDialog | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [actionMenu, setActionMenu] = useState<ActionMenuState | null>(null);
  const actionMenuRef = useRef<HTMLDivElement>(null);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [importPreview, setImportPreview] = useState<NameMasterImportPreview | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);

  const queryArgs = useMemo(
    () =>
      statusFilter === "all"
        ? { search, page }
        : { search, page, is_active: statusFilter === "active" },
    [search, page, statusFilter],
  );
  const { data, isLoading, isFetching, isError, refetch } = config.hooks.useListQuery(queryArgs);
  const [createRecord, createState] = config.hooks.useCreateMutation();
  const [updateRecord, updateState] = config.hooks.useUpdateMutation();
  const [deleteRecord, deleteState] = config.hooks.useDeleteMutation();
  const [importRecords, importState] = config.hooks.useImportMutation();
  const previewEnabled = Boolean(config.hooks.useValidateMutation);
  const [validateImport, validateState] = (config.hooks.useValidateMutation ?? noopValidate)();
  const [fetchImportJob] = useLazyGetImportJobQuery();
  const importBusy =
    importState.isLoading ||
    Boolean(importJob && !TERMINAL_JOB_STATUSES.has(importJob.status));

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (!actionMenu) return;

    function closeMenu() {
      setActionMenu(null);
    }

    function onPointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (actionMenuRef.current?.contains(target)) return;
      if ((target as Element).closest?.("[data-action-trigger]")) return;
      closeMenu();
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeMenu();
    }

    function onReposition() {
      closeMenu();
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", onReposition);
    window.addEventListener("scroll", onReposition, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onReposition);
      window.removeEventListener("scroll", onReposition, true);
    };
  }, [actionMenu]);

  const totalPages = data ? Math.max(1, Math.ceil(data.count / 20)) : 1;
  const saving = createState.isLoading || updateState.isLoading;

  function openCreate() {
    setSelected(null);
    setName("");
    setFormError(null);
    setModal("create");
  }

  function openEdit(row: NameMasterRecord) {
    setSelected(row);
    setName(row.name);
    setFormError(null);
    setModal("edit");
  }

  function openView(row: NameMasterRecord) {
    setSelected(row);
    setFormError(null);
    setModal("view");
  }

  function closeModal() {
    setModal(null);
    setSelected(null);
    setFormError(null);
    setImportJob(null);
    setImportPreview(null);
    setImportFile(null);
  }

  function showNotice(title: string, message: string) {
    setNoticeDialog({ title, message });
  }

  function toggleActionMenu(row: NameMasterRecord, button: HTMLButtonElement) {
    if (actionMenu?.row.id === row.id) {
      setActionMenu(null);
      return;
    }
    const rect = button.getBoundingClientRect();
    const menuWidth = 168;
    const menuHeight = 180 + (config.extraActions?.length ?? 0) * 36;
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

  function askDelete(row: NameMasterRecord) {
    setConfirmDialog({ action: "delete", row });
  }

  function askDeactivate(row: NameMasterRecord) {
    if (!row.is_active) return;
    setConfirmDialog({ action: "deactivate", row });
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const cleaned = name.trim();
    if (!cleaned) {
      setFormError(`${config.nameLabel} is required.`);
      return;
    }
    try {
      let saved: NameMasterRecord | null = null;
      if (modal === "create") {
        saved = await createRecord({ name: cleaned }).unwrap();
      } else if (modal === "edit" && selected) {
        saved = await updateRecord({
          id: selected.id,
          body: { name: cleaned, is_active: selected.is_active },
        }).unwrap();
      }
      if (saved && config.formSection) {
        const sectionError = await config.formSection.onSaved(saved);
        if (sectionError) {
          setSelected(saved);
          setName(saved.name);
          setModal("edit");
          setFormError(sectionError);
          return;
        }
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
        await updateRecord({ id: row.id, body: { name: row.name, is_active: false } }).unwrap();
      }
      setConfirmDialog(null);
    } catch (err) {
      setConfirmDialog(null);
      showNotice("Action failed", extractError(err));
    } finally {
      setConfirmBusy(false);
    }
  }

  async function onActivate(row: NameMasterRecord) {
    if (row.is_active) return;
    try {
      await updateRecord({ id: row.id, body: { name: row.name, is_active: true } }).unwrap();
    } catch (err) {
      showNotice("Action failed", extractError(err));
    }
  }

  async function onDownloadTemplate() {
    setTemplateBusy(true);
    try {
      await downloadNameMasterTemplate(config.resource, config.templateFilename, accessToken);
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
    setImportPreview(null);
    setImportFile(file);
    setModal("import");
    try {
      if (previewEnabled) {
        setImportPreview(await validateImport(file).unwrap());
      } else {
        setImportJob(await importRecords(file).unwrap());
      }
    } catch (err) {
      setFormError(extractError(err));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onConfirmImport() {
    if (!importFile) return;
    setFormError(null);
    try {
      const job = await importRecords(importFile).unwrap();
      setImportPreview(null);
      setImportJob(job);
    } catch (err) {
      setFormError(extractError(err));
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
        // Keep polling; transient network errors should not close the modal.
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
            <h1>{config.title}</h1>
            <p>{config.description}</p>
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
                Add {config.singular}
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
              placeholder={`Search by ${config.nameLabel}`}
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label={`Search ${config.plural}`}
            />
          </label>
          {config.showStatusFilter ? (
            <select
              className={styles.filterSelect}
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value as StatusFilter);
                setPage(1);
              }}
              aria-label="Filter by Status"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          ) : null}
        </div>

        <div className={styles.panel}>
          {isLoading ? <p className={styles.loading}>Loading {config.plural}…</p> : null}
          {isError ? (
            <p className={styles.error}>
              Unable to load {config.plural}.{" "}
              <button type="button" className={styles.linkBtn} onClick={() => refetch()}>
                Retry
              </button>
            </p>
          ) : null}
          {!isLoading && !isError && data && data.results.length === 0 ? (
            <p className={styles.empty}>No {config.plural} found. Add one or upload Excel.</p>
          ) : null}
          {!isLoading && !isError && data && data.results.length > 0 ? (
            <>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>{config.nameLabel}</th>
                      {config.extraColumns?.map((column) => (
                        <th key={column.header}>{column.header}</th>
                      ))}
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
                        {config.extraColumns?.map((column) => (
                          <td key={column.header}>{column.render(row)}</td>
                        ))}
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
              {config.extraActions
                ?.filter((action) => action.visible?.(actionMenu.row) ?? true)
                .map((action) => (
                  <button
                    key={action.label}
                    type="button"
                    className={styles.menuItem}
                    role="menuitem"
                    onClick={() => runMenuAction(() => action.onSelect(actionMenu.row))}
                  >
                    {action.label}
                  </button>
                ))}
              {canToggleActive ? (
                <button
                  type="button"
                  className={`${styles.menuItem} ${styles.menuItemDanger}`}
                  role="menuitem"
                  onClick={() => runMenuAction(() => askDelete(actionMenu.row))}
                  disabled={deleteState.isLoading}
                >
                  Delete
                </button>
              ) : null}
              {!canToggleActive ? null : actionMenu.row.is_active ? (
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
                <h2>
                  {modal === "create" ? `Add ${config.singular}` : `Edit ${config.singular}`}
                </h2>
                <p>Only {config.nameLabel} is required.</p>
              </div>
              <button type="button" className={styles.closeBtn} aria-label="Close" onClick={closeModal}>
                <CloseIcon />
              </button>
            </div>
            <form className={styles.form} onSubmit={onSubmit}>
              {formError ? <p className={styles.formError}>{formError}</p> : null}
              <div className={styles.field}>
                <label htmlFor="name-master-name">{config.nameLabel}</label>
                <input
                  id="name-master-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoFocus
                  required
                  maxLength={150}
                />
              </div>
              {config.formSection ? config.formSection.render(modal === "edit" ? selected : null) : null}
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
                <h2>View {config.singular}</h2>
                <p>Read-only {config.singular.toLowerCase()} details.</p>
              </div>
              <button type="button" className={styles.closeBtn} aria-label="Close" onClick={closeModal}>
                <CloseIcon />
              </button>
            </div>
            <div className={styles.detailGrid}>
              <div className={styles.detailRow}>
                <span>{config.nameLabel}</span>
                <strong>{selected.name}</strong>
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
            {config.renderViewDetails ? config.renderViewDetails(selected) : null}
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
                    : importPreview
                      ? "Validate Import"
                      : "Excel Import"}
                </h2>
                <p>
                  {importJob
                    ? importJob.progress_label || importJob.detail || "Processing in the background…"
                    : importPreview
                      ? "Review validation results before confirming import."
                      : previewEnabled
                        ? "Validating file…"
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
            {validateState.isLoading ? <p className={styles.loading}>Validating…</p> : null}
            {importState.isLoading ? <p className={styles.loading}>Uploading…</p> : null}
            {formError ? <p className={styles.formError}>{formError}</p> : null}

            {importPreview && !importJob ? (
              <>
                <div className={styles.summary}>
                  <div className={styles.summaryCard}>
                    <span>Total</span>
                    <strong>{importPreview.total}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>New</span>
                    <strong>{importPreview.valid}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Existing</span>
                    <strong>{importPreview.existing}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Duplicate</span>
                    <strong>{importPreview.duplicate}</strong>
                  </div>
                  <div className={styles.summaryCard}>
                    <span>Failed</span>
                    <strong>{importPreview.failed}</strong>
                  </div>
                </div>
                <p className={styles.importDetail}>
                  {importPreview.valid > 0
                    ? `${importPreview.valid} new ${config.plural} will be created as Active. Existing and duplicate rows are skipped.`
                    : `No new ${config.plural} to create.`}
                </p>
                {importPreview.rows.length > 0 ? (
                  <div className={styles.previewTableWrap}>
                    <table className={styles.previewTable}>
                      <thead>
                        <tr>
                          <th>Row</th>
                          <th>{config.nameLabel}</th>
                          <th>Status</th>
                          <th>Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importPreview.rows.map((row) => (
                          <tr key={row.row}>
                            <td>{row.row}</td>
                            <td>{row.name}</td>
                            <td>{row.status}</td>
                            <td>{row.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <div className={styles.formActions}>
                  <button type="button" className={styles.secondaryBtn} onClick={closeModal}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className={styles.primaryBtn}
                    disabled={importState.isLoading || importPreview.valid === 0}
                    onClick={onConfirmImport}
                  >
                    {importState.isLoading ? "Starting import…" : "Confirm Import"}
                  </button>
                </div>
              </>
            ) : null}

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

            {formError && !importJob && !importPreview ? (
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
                  {confirmDialog.action === "delete" ? `Delete ${config.singular}` : `Deactivate ${config.singular}`}
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
                  Permanently delete {config.singular.toLowerCase()}{" "}
                  <strong>&quot;{confirmDialog.row.name}&quot;</strong>? This cannot be undone.
                </>
              ) : (
                <>
                  Deactivate {config.singular.toLowerCase()}{" "}
                  <strong>&quot;{confirmDialog.row.name}&quot;</strong>?
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

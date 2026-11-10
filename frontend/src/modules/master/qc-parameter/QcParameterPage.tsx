import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  downloadNameMasterTemplate,
  useActivateQcParameterMutation,
  useCreateQcParameterMutation,
  useDeactivateQcParameterMutation,
  useGetQcParametersQuery,
  useUpdateQcParameterMutation,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import { CloseIcon, MoreIcon, SearchIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import type { QcParameterRecord, QcParameterUserRef } from "@/types/qcParameter";
import { extractApiError } from "@/utils/extractApiError";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import { QcParameterImportModal } from "./QcParameterImportModal";
import styles from "./QcParameterPage.module.css";

const PAGE_SIZE = 20;
const NAME_MAX = 150;
const SHORT_NAME_MAX = 30;
const UNIT_MAX = 50;
const COMMON_UNITS = ["%", "ppm", "mm", "kg/cm²", "°C", "kcal/kg"];

type ModalMode = "create" | "edit" | "view" | null;
type StatusFilter = "all" | "active" | "inactive";
type FieldKey = "name" | "short_name" | "unit";
type FieldErrors = Partial<Record<FieldKey, string>>;
type NoticeDialog = { title: string; message: string };
type ActionMenuState = { row: QcParameterRecord; top: number; left: number };

const FIELD_KEYS: FieldKey[] = ["name", "short_name", "unit"];

function parseFormErrors(error: unknown): { fields: FieldErrors; message: string | null } {
  const detail = (error as { data?: { error?: { detail?: unknown } } } | null)?.data?.error?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const fields: FieldErrors = {};
    let message: string | null = null;
    for (const [key, value] of Object.entries(detail as Record<string, unknown>)) {
      const text = Array.isArray(value) ? String(value[0]) : String(value);
      if ((FIELD_KEYS as string[]).includes(key)) fields[key as FieldKey] = text;
      else message ??= text;
    }
    if (Object.keys(fields).length || message) return { fields, message };
  }
  return { fields: {}, message: extractApiError(error) };
}

const dateFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});
const dateTimeFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

function formatDateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateTimeFormatter.format(date);
}

function auditLine(value: string, user: QcParameterUserRef | null) {
  return user ? `${formatDateTime(value)} · by ${user.name || user.email}` : formatDateTime(value);
}

export function QcParameterPage() {
  useDocumentTitle("Master · QC Parameter");
  const { canCreate, canEdit, canUpload, canToggleActive } = useMasterPermissions("qc-parameter");
  const accessToken = useAppSelector(selectAccessToken);
  const fileRef = useRef<HTMLInputElement>(null);
  const actionMenuRef = useRef<HTMLDivElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState<ModalMode>(null);
  const [selected, setSelected] = useState<QcParameterRecord | null>(null);
  const [name, setName] = useState("");
  const [shortName, setShortName] = useState("");
  const [unit, setUnit] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);
  const [confirmRow, setConfirmRow] = useState<QcParameterRecord | null>(null);
  const [noticeDialog, setNoticeDialog] = useState<NoticeDialog | null>(null);
  const [actionMenu, setActionMenu] = useState<ActionMenuState | null>(null);

  const queryArgs = useMemo(
    () => ({
      search,
      page,
      page_size: PAGE_SIZE,
      is_active: statusFilter === "all" ? undefined : statusFilter === "active",
    }),
    [search, page, statusFilter],
  );

  const { data, isLoading, isFetching, isError, refetch } = useGetQcParametersQuery(queryArgs);
  const [createRecord, createState] = useCreateQcParameterMutation();
  const [updateRecord, updateState] = useUpdateQcParameterMutation();
  const [deactivateRecord, deactivateState] = useDeactivateQcParameterMutation();
  const [activateRecord, activateState] = useActivateQcParameterMutation();
  const saving = createState.isLoading || updateState.isLoading;
  const count = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const rangeStart = count ? (page - 1) * PAGE_SIZE + 1 : 0;
  const rangeEnd = Math.min(page * PAGE_SIZE, count);
  const filtered = Boolean(search) || statusFilter !== "all";

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

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

  const closeModal = useCallback(() => {
    setModal(null);
    setSelected(null);
    setFieldErrors({});
    setFormError(null);
  }, []);

  useEffect(() => {
    if (!modal || confirmRow || noticeDialog) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeModal();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [modal, confirmRow, noticeDialog, closeModal]);

  function openCreate() {
    setSelected(null);
    setName("");
    setShortName("");
    setUnit("");
    setFieldErrors({});
    setFormError(null);
    setModal("create");
  }

  function openEdit(row: QcParameterRecord) {
    setSelected(row);
    setName(row.name);
    setShortName(row.short_name);
    setUnit(row.unit);
    setFieldErrors({});
    setFormError(null);
    setModal("edit");
  }

  function openView(row: QcParameterRecord) {
    setSelected(row);
    setModal("view");
  }

  function toggleActionMenu(row: QcParameterRecord, button: HTMLButtonElement) {
    if (actionMenu?.row.id === row.id) {
      setActionMenu(null);
      return;
    }
    const rect = button.getBoundingClientRect();
    const menuWidth = 168;
    const menuHeight = 136;
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

  function clearFieldError(key: FieldKey) {
    setFieldErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const payload = {
      name: name.trim(),
      short_name: shortName.trim().toUpperCase(),
      unit: unit.trim(),
    };
    const missing: FieldErrors = {};
    if (!payload.name) missing.name = "QC Parameter Name is required.";
    if (!payload.short_name) missing.short_name = "Short Name is required.";
    if (Object.keys(missing).length) {
      setFieldErrors(missing);
      return;
    }
    setFieldErrors({});
    try {
      if (modal === "create") {
        await createRecord(payload).unwrap();
      } else if (modal === "edit" && selected) {
        await updateRecord({ id: selected.id, body: payload }).unwrap();
      }
      closeModal();
    } catch (err) {
      const parsed = parseFormErrors(err);
      setFieldErrors(parsed.fields);
      setFormError(parsed.message);
    }
  }

  async function onConfirmDeactivate() {
    if (!confirmRow) return;
    try {
      await deactivateRecord(confirmRow.id).unwrap();
      if (selected?.id === confirmRow.id) setSelected({ ...selected, is_active: false });
      setConfirmRow(null);
    } catch (err) {
      setConfirmRow(null);
      setNoticeDialog({ title: "Action failed", message: extractApiError(err) });
    }
  }

  async function onActivate(row: QcParameterRecord) {
    try {
      const updated = await activateRecord(row.id).unwrap();
      if (selected?.id === row.id) setSelected(updated);
    } catch (err) {
      setNoticeDialog({ title: "Action failed", message: extractApiError(err) });
    }
  }

  async function onDownloadTemplate() {
    setTemplateBusy(true);
    try {
      await downloadNameMasterTemplate("qc-parameters", "qc_parameter_template.xlsx", accessToken);
    } catch {
      setNoticeDialog({ title: "Download failed", message: "Unable to download template." });
    } finally {
      setTemplateBusy(false);
    }
  }

  function onFileSelected(file: File | null) {
    if (fileRef.current) fileRef.current.value = "";
    if (file) setImportFile(file);
  }

  const onImportFinished = useCallback(() => {
    void refetch();
  }, [refetch]);

  const closeImport = useCallback(() => setImportFile(null), []);

  function inputClass(key: FieldKey, extra = "") {
    return [fieldErrors[key] ? styles.inputInvalid : "", extra].filter(Boolean).join(" ");
  }

  return (
    <PageContainer>
      <div className={shared.page}>
        <div className={shared.toolbar}>
          <div className={shared.heading}>
            <h1>QC Parameter</h1>
            <p>Manage quality check parameters and their units.</p>
          </div>
          <div className={shared.actions}>
            {canUpload ? (
              <>
                <button
                  type="button"
                  className={shared.secondaryBtn}
                  onClick={onDownloadTemplate}
                  disabled={templateBusy}
                >
                  {templateBusy ? "Downloading…" : "Download Template"}
                </button>
                <button
                  type="button"
                  className={shared.ghostBtn}
                  onClick={() => fileRef.current?.click()}
                  disabled={Boolean(importFile)}
                >
                  Upload Excel
                </button>
              </>
            ) : null}
            {canCreate ? (
              <button type="button" className={shared.primaryBtn} onClick={openCreate}>
                + Add QC Parameter
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
        </div>

        <div className={shared.filters}>
          <label className={shared.search}>
            <span className={shared.searchIcon} aria-hidden="true">
              <SearchIcon />
            </span>
            <input
              type="search"
              placeholder="Search by name or short name..."
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label="Search QC Parameters"
            />
          </label>
          <select
            className={shared.filterSelect}
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
        </div>

        <div className={shared.panel}>
          {isLoading ? <p className={shared.loading}>Loading QC Parameters…</p> : null}
          {isError ? (
            <p className={shared.error}>
              Unable to load QC Parameters.{" "}
              <button type="button" className={shared.linkBtn} onClick={() => refetch()}>
                Retry
              </button>
            </p>
          ) : null}
          {!isLoading && !isError && data && data.results.length === 0 ? (
            <p className={shared.empty}>
              {filtered
                ? "No QC Parameters match your search or filter."
                : "No QC Parameters yet. Add one or upload Excel."}
            </p>
          ) : null}
          {!isLoading && !isError && data && data.results.length > 0 ? (
            <>
              <div className={shared.tableWrap}>
                <table className={shared.table}>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Short Name</th>
                      <th>Unit</th>
                      <th>Status</th>
                      <th>Updated</th>
                      <th className={shared.actionsCol}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.map((row) => (
                      <tr
                        key={row.id}
                        className={styles.clickableRow}
                        onClick={() => openView(row)}
                      >
                        <td>
                          <strong>{row.name}</strong>
                        </td>
                        <td>
                          <span className={styles.shortName}>{row.short_name}</span>
                        </td>
                        <td className={styles.unit}>
                          {row.unit || <span className={styles.muted}>—</span>}
                        </td>
                        <td>
                          <span
                            className={`${shared.badge} ${
                              row.is_active ? shared.badgeActive : shared.badgeInactive
                            }`}
                          >
                            {row.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td title={formatDateTime(row.updated_at)}>{formatDate(row.updated_at)}</td>
                        <td className={shared.actionsCol}>
                          <div className={shared.rowActions}>
                            <button
                              type="button"
                              className={`${shared.actionsTrigger} ${
                                actionMenu?.row.id === row.id ? shared.actionsTriggerOpen : ""
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
              <div className={shared.pager}>
                <span>
                  Showing {rangeStart}–{rangeEnd} of {count}
                  {isFetching ? " · Refreshing…" : ""}
                </span>
                <div className={shared.pagerControls}>
                  <button
                    type="button"
                    className={shared.secondaryBtn}
                    disabled={page <= 1}
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className={shared.secondaryBtn}
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

      {createPortal(
        <>
          {actionMenu ? (
            <div
              ref={actionMenuRef}
              className={shared.actionsMenu}
              role="menu"
              style={{ top: actionMenu.top, left: actionMenu.left }}
            >
              <button
                type="button"
                className={shared.menuItem}
                role="menuitem"
                onClick={() => runMenuAction(() => openView(actionMenu.row))}
              >
                View
              </button>
              {canEdit ? (
                <button
                  type="button"
                  className={shared.menuItem}
                  role="menuitem"
                  onClick={() => runMenuAction(() => openEdit(actionMenu.row))}
                >
                  Edit
                </button>
              ) : null}
              {!canToggleActive ? null : actionMenu.row.is_active ? (
                <button
                  type="button"
                  className={`${shared.menuItem} ${shared.menuItemDanger}`}
                  role="menuitem"
                  onClick={() => runMenuAction(() => setConfirmRow(actionMenu.row))}
                >
                  Deactivate
                </button>
              ) : (
                <button
                  type="button"
                  className={shared.menuItem}
                  role="menuitem"
                  disabled={activateState.isLoading}
                  onClick={() => runMenuAction(() => onActivate(actionMenu.row))}
                >
                  Activate
                </button>
              )}
            </div>
          ) : null}

          {modal === "create" || modal === "edit" ? (
            <>
              <button
                type="button"
                className={shared.backdrop}
                aria-label="Close"
                onClick={closeModal}
              />
              <div
                className={shared.modal}
                role="dialog"
                aria-modal="true"
                aria-labelledby="qc-form-title"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2 id="qc-form-title">
                      {modal === "create" ? "Add QC Parameter" : "Edit QC Parameter"}
                    </h2>
                    <p>
                      {modal === "edit" && selected
                        ? `Update details for ${selected.name}.`
                        : "Name and Short Name are required."}
                    </p>
                  </div>
                  <button
                    type="button"
                    className={shared.closeBtn}
                    aria-label="Close"
                    onClick={closeModal}
                  >
                    <CloseIcon />
                  </button>
                </div>
                <form className={shared.form} onSubmit={onSubmit} noValidate>
                  {formError ? <p className={shared.formError}>{formError}</p> : null}
                  <div className={shared.field}>
                    <label htmlFor="qc-name">Name *</label>
                    <input
                      id="qc-name"
                      className={inputClass("name")}
                      value={name}
                      onChange={(event) => {
                        setName(event.target.value);
                        clearFieldError("name");
                      }}
                      placeholder="e.g. Moisture"
                      maxLength={NAME_MAX}
                      aria-invalid={Boolean(fieldErrors.name)}
                      autoFocus
                    />
                    {fieldErrors.name ? (
                      <p className={styles.fieldError}>{fieldErrors.name}</p>
                    ) : null}
                  </div>
                  <div className={shared.field}>
                    <label htmlFor="qc-short-name">Short Name *</label>
                    <input
                      id="qc-short-name"
                      className={inputClass("short_name", styles.upperInput)}
                      value={shortName}
                      onChange={(event) => {
                        setShortName(event.target.value.toUpperCase());
                        clearFieldError("short_name");
                      }}
                      placeholder="e.g. MOIST"
                      maxLength={SHORT_NAME_MAX}
                      aria-invalid={Boolean(fieldErrors.short_name)}
                    />
                    {fieldErrors.short_name ? (
                      <p className={styles.fieldError}>{fieldErrors.short_name}</p>
                    ) : (
                      <p className={styles.fieldHint}>Saved in capital letters.</p>
                    )}
                  </div>
                  <div className={shared.field}>
                    <label htmlFor="qc-unit">Unit</label>
                    <input
                      id="qc-unit"
                      className={inputClass("unit")}
                      value={unit}
                      onChange={(event) => {
                        setUnit(event.target.value);
                        clearFieldError("unit");
                      }}
                      placeholder="Optional, e.g. %"
                      maxLength={UNIT_MAX}
                      aria-invalid={Boolean(fieldErrors.unit)}
                    />
                    <div className={styles.unitChips}>
                      {COMMON_UNITS.map((option) => (
                        <button
                          key={option}
                          type="button"
                          className={`${styles.unitChip} ${
                            unit.trim() === option ? styles.unitChipActive : ""
                          }`}
                          onClick={() => {
                            setUnit(unit.trim() === option ? "" : option);
                            clearFieldError("unit");
                          }}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                    {fieldErrors.unit ? (
                      <p className={styles.fieldError}>{fieldErrors.unit}</p>
                    ) : (
                      <p className={styles.fieldHint}>
                        Optional. Type any unit or pick a common one.
                      </p>
                    )}
                  </div>
                  <div className={shared.formActions}>
                    <button type="button" className={shared.secondaryBtn} onClick={closeModal}>
                      Cancel
                    </button>
                    <button type="submit" className={shared.primaryBtn} disabled={saving}>
                      {saving
                        ? "Saving…"
                        : modal === "create"
                          ? "Add QC Parameter"
                          : "Save Changes"}
                    </button>
                  </div>
                </form>
              </div>
            </>
          ) : null}

          {modal === "view" && selected ? (
            <>
              <button
                type="button"
                className={shared.backdrop}
                aria-label="Close"
                onClick={closeModal}
              />
              <div
                className={`${shared.modal} ${styles.viewModal}`}
                role="dialog"
                aria-modal="true"
                aria-labelledby="qc-view-title"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2 id="qc-view-title">{selected.name}</h2>
                    <p>QC Parameter details</p>
                  </div>
                  <button
                    type="button"
                    className={shared.closeBtn}
                    aria-label="Close"
                    onClick={closeModal}
                  >
                    <CloseIcon />
                  </button>
                </div>
                <div className={shared.detailGrid}>
                  <div className={shared.detailRow}>
                    <span>Name</span>
                    <strong>{selected.name}</strong>
                  </div>
                  <div className={shared.detailRow}>
                    <span>Short Name</span>
                    <strong>
                      <span className={styles.shortName}>{selected.short_name}</span>
                    </strong>
                  </div>
                  <div className={shared.detailRow}>
                    <span>Unit</span>
                    <strong>
                      {selected.unit || <span className={styles.muted}>Not specified</span>}
                    </strong>
                  </div>
                  <div className={shared.detailRow}>
                    <span>Status</span>
                    <strong>
                      <span
                        className={`${shared.badge} ${
                          selected.is_active ? shared.badgeActive : shared.badgeInactive
                        }`}
                      >
                        {selected.is_active ? "Active" : "Inactive"}
                      </span>
                    </strong>
                  </div>
                  <div className={shared.detailRow}>
                    <span>Created</span>
                    <strong className={styles.detailMeta}>
                      {auditLine(selected.created_at, selected.created_by)}
                    </strong>
                  </div>
                  <div className={shared.detailRow}>
                    <span>Last Updated</span>
                    <strong className={styles.detailMeta}>
                      {auditLine(selected.updated_at, selected.updated_by)}
                    </strong>
                  </div>
                </div>
                <div className={shared.formActions}>
                  {!canToggleActive ? null : selected.is_active ? (
                    <button
                      type="button"
                      className={shared.dangerBtn}
                      onClick={() => setConfirmRow(selected)}
                    >
                      Deactivate
                    </button>
                  ) : (
                    <button
                      type="button"
                      className={shared.secondaryBtn}
                      disabled={activateState.isLoading}
                      onClick={() => onActivate(selected)}
                    >
                      {activateState.isLoading ? "Activating…" : "Activate"}
                    </button>
                  )}
                  <button type="button" className={shared.secondaryBtn} onClick={closeModal}>
                    Close
                  </button>
                  {canEdit ? (
                    <button
                      type="button"
                      className={shared.primaryBtn}
                      onClick={() => openEdit(selected)}
                    >
                      Edit
                    </button>
                  ) : null}
                </div>
              </div>
            </>
          ) : null}

          {importFile ? (
            <QcParameterImportModal
              file={importFile}
              onClose={closeImport}
              onFinished={onImportFinished}
            />
          ) : null}

          {confirmRow ? (
            <>
              <button
                type="button"
                className={`${shared.backdrop} ${styles.confirmBackdrop}`}
                aria-label="Close"
                onClick={() => !deactivateState.isLoading && setConfirmRow(null)}
              />
              <div
                className={`${shared.modal} ${styles.confirmModal}`}
                role="dialog"
                aria-modal="true"
                data-layer="confirm"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2>Deactivate QC Parameter</h2>
                    <p>It will be marked inactive and can be activated again later.</p>
                  </div>
                  <button
                    type="button"
                    className={shared.closeBtn}
                    aria-label="Close"
                    disabled={deactivateState.isLoading}
                    onClick={() => setConfirmRow(null)}
                  >
                    <CloseIcon />
                  </button>
                </div>
                <p className={shared.confirmMessage}>
                  Deactivate <strong>&quot;{confirmRow.name}&quot;</strong> ({confirmRow.short_name}
                  )?
                </p>
                <div className={shared.formActions}>
                  <button
                    type="button"
                    className={shared.secondaryBtn}
                    disabled={deactivateState.isLoading}
                    onClick={() => setConfirmRow(null)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className={shared.dangerBtn}
                    disabled={deactivateState.isLoading}
                    onClick={onConfirmDeactivate}
                  >
                    {deactivateState.isLoading ? "Please wait…" : "Deactivate"}
                  </button>
                </div>
              </div>
            </>
          ) : null}

          {noticeDialog ? (
            <>
              <button
                type="button"
                className={`${shared.backdrop} ${styles.confirmBackdrop}`}
                aria-label="Close"
                onClick={() => setNoticeDialog(null)}
              />
              <div
                className={`${shared.modal} ${styles.confirmModal}`}
                role="dialog"
                aria-modal="true"
                data-layer="confirm"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2>{noticeDialog.title}</h2>
                    <p>{noticeDialog.message}</p>
                  </div>
                  <button
                    type="button"
                    className={shared.closeBtn}
                    aria-label="Close"
                    onClick={() => setNoticeDialog(null)}
                  >
                    <CloseIcon />
                  </button>
                </div>
                <div className={shared.formActions}>
                  <button
                    type="button"
                    className={shared.primaryBtn}
                    onClick={() => setNoticeDialog(null)}
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

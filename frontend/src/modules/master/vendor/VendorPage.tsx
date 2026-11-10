import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  downloadNameMasterTemplate,
  useActivateVendorMutation,
  useDeactivateVendorMutation,
  useGetVendorLocationsQuery,
  useGetVendorsQuery,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import {
  CloseIcon,
  MailIcon,
  MasterVendorIcon,
  MoreIcon,
  PlusIcon,
  SearchIcon,
} from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useMasterPermissions } from "@/hooks/useMasterPermissions";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import type {
  VendorListParams,
  VendorOrdering,
  VendorOrderingField,
  VendorRecord,
} from "@/types/vendor";
import { extractApiError } from "@/utils/extractApiError";
import { formatMobile } from "../employee/employeeFormat";
import {
  ChevronIcon,
  DownloadIcon,
  PhoneIcon,
  RefreshIcon,
  SortIcon,
  UploadIcon,
} from "../employee/employeeIcons";
import { VendorDetailsModal } from "./VendorDetailsModal";
import { VendorFormModal } from "./VendorFormModal";
import { VendorImportModal } from "./VendorImportModal";
import { telHref, vendorInitials } from "./vendorFormat";
import styles from "./VendorPage.module.css";

const PAGE_SIZES = [10, 25, 50, 100] as const;
const MENU_WIDTH = 168;
const MENU_HEIGHT = 124;

type StatusFilter = "all" | "active" | "inactive";
type Panel = { kind: "view"; record: VendorRecord } | { kind: "form"; record: VendorRecord | null };
type ActionMenuState = { row: VendorRecord; top: number; left: number };

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

export function VendorPage() {
  useDocumentTitle("Master · Vendor");
  const { canCreate, canEdit, canUpload, canToggleActive } = useMasterPermissions("vendor");
  const accessToken = useAppSelector(selectAccessToken);
  const fileRef = useRef<HTMLInputElement>(null);
  const actionMenuRef = useRef<HTMLDivElement>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [location, setLocation] = useState("");
  const [ordering, setOrdering] = useState<VendorOrdering>("vendor_name");
  const [pageSize, setPageSize] = useState<number>(25);
  const [page, setPage] = useState(1);

  const [panel, setPanel] = useState<Panel | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [actionMenu, setActionMenu] = useState<ActionMenuState | null>(null);
  const [confirm, setConfirm] = useState<VendorRecord | null>(null);
  const [notice, setNotice] = useState<{ title: string; message: string } | null>(null);
  const [templateBusy, setTemplateBusy] = useState(false);

  const queryArgs = useMemo<VendorListParams>(
    () => ({
      search,
      page,
      page_size: pageSize,
      ordering,
      is_active: status === "all" ? undefined : status === "active",
      location: location || undefined,
    }),
    [search, page, pageSize, ordering, status, location],
  );
  const { data, isLoading, isFetching, isError, refetch } = useGetVendorsQuery(queryArgs);
  const { data: locations = [] } = useGetVendorLocationsQuery();
  const [deactivateVendor, deactivateState] = useDeactivateVendorMutation();
  const [activateVendor, activateState] = useActivateVendorMutation();
  const statusBusy = deactivateState.isLoading || activateState.isLoading;

  const rows = useMemo(() => data?.results ?? [], [data]);
  const totalCount = data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const rangeFrom = totalCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const rangeTo = Math.min(page * pageSize, totalCount);
  const filtersActive = Boolean(search || status !== "all" || location);

  const viewRecord = useMemo(() => {
    if (panel?.kind !== "view") return null;
    const fresh = rows.find((row) => row.id === panel.record.id);
    return fresh && fresh.updated_at > panel.record.updated_at ? fresh : panel.record;
  }, [panel, rows]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setSearch(searchInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    if (page > totalPages && !isFetching) setPage(totalPages);
  }, [page, totalPages, isFetching]);

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

  useEffect(() => {
    if (!confirm && !notice) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.stopImmediatePropagation();
      if (notice) setNotice(null);
      else if (!statusBusy) setConfirm(null);
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [confirm, notice, statusBusy]);

  function resetFilters() {
    setSearchInput("");
    setSearch("");
    setStatus("all");
    setLocation("");
    setPage(1);
  }

  function toggleSort(key: VendorOrderingField) {
    setPage(1);
    setOrdering((current) => (current === key ? (`-${key}` as VendorOrdering) : key));
  }

  function toggleActionMenu(row: VendorRecord, button: HTMLButtonElement) {
    if (actionMenu?.row.id === row.id) {
      setActionMenu(null);
      return;
    }
    const rect = button.getBoundingClientRect();
    const left = Math.min(Math.max(8, rect.right - MENU_WIDTH), window.innerWidth - MENU_WIDTH - 8);
    const openUp = rect.bottom + 6 + MENU_HEIGHT > window.innerHeight;
    const top = openUp ? Math.max(8, rect.top - MENU_HEIGHT - 6) : rect.bottom + 6;
    setActionMenu({ row, top, left });
  }

  async function confirmDeactivate() {
    if (!confirm) return;
    try {
      await deactivateVendor(confirm.id).unwrap();
      setPanel((current) =>
        current?.kind === "view" && current.record.id === confirm.id
          ? { kind: "view", record: { ...current.record, is_active: false } }
          : current,
      );
    } catch (err) {
      setNotice({ title: "Action failed", message: extractApiError(err) });
    } finally {
      setConfirm(null);
    }
  }

  async function onActivate(record: VendorRecord) {
    try {
      const updated = await activateVendor(record.id).unwrap();
      setPanel((current) =>
        current?.kind === "view" && current.record.id === record.id
          ? { kind: "view", record: updated }
          : current,
      );
    } catch (err) {
      setNotice({ title: "Action failed", message: extractApiError(err) });
    }
  }

  async function onDownloadTemplate() {
    setTemplateBusy(true);
    try {
      await downloadNameMasterTemplate("vendors", "vendor_template.xlsx", accessToken);
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

  const sortHeader = (key: VendorOrderingField, label: string) => {
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

  const dash = <span className={styles.muted}>—</span>;

  return (
    <PageContainer>
      <div className={styles.page}>
        <header className={styles.header}>
          <div className={styles.titleBlock}>
            <span className={styles.titleIcon}>
              <MasterVendorIcon />
            </span>
            <div>
              <h1>Vendor Master</h1>
              <p>Manage procurement vendor records.</p>
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
                Add Vendor
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

        <section className={styles.filterCard}>
          <label className={styles.searchBox}>
            <SearchIcon />
            <input
              type="search"
              placeholder="Search by vendor, VEN ID, SAP ID, GSTIN, contact, email..."
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              aria-label="Search vendors"
            />
          </label>
          <select
            className={styles.filterSelect}
            value={status}
            aria-label="Filter by status"
            onChange={(event) => {
              setStatus(event.target.value as StatusFilter);
              setPage(1);
            }}
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <select
            className={styles.filterSelect}
            value={location}
            aria-label="Filter by location"
            onChange={(event) => {
              setLocation(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All Locations</option>
            {location && !locations.includes(location) ? (
              <option value={location}>{location}</option>
            ) : null}
            {locations.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          {filtersActive ? (
            <button
              type="button"
              className={`${shared.secondaryBtn} ${styles.iconBtnLabel}`}
              onClick={resetFilters}
            >
              <RefreshIcon />
              Reset
            </button>
          ) : null}
        </section>

        <section className={styles.tableCard}>
          {isLoading ? <p className={shared.loading}>Loading vendors…</p> : null}
          {isError ? (
            <p className={shared.error}>
              Unable to load vendors.{" "}
              <button type="button" className={shared.linkBtn} onClick={() => refetch()}>
                Retry
              </button>
            </p>
          ) : null}
          {!isLoading && !isError && data && rows.length === 0 ? (
            <p className={shared.empty}>
              {filtersActive
                ? "No vendors match the search or filters."
                : "No vendors yet. Add one or upload Excel."}
            </p>
          ) : null}

          {!isLoading && !isError && rows.length > 0 ? (
            <>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      {sortHeader("vendor_name", "Vendor")}
                      {sortHeader("sap_vendor_id", "SAP Vendor ID")}
                      {sortHeader("gstin", "GSTIN")}
                      <th>Contact</th>
                      {sortHeader("location", "Location")}
                      {sortHeader("status", "Status")}
                      <th className={styles.actionsHead}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr
                        key={row.id}
                        className={row.is_active ? undefined : styles.rowInactive}
                        onClick={() => setPanel({ kind: "view", record: row })}
                      >
                        <td>
                          <div className={styles.vendorCell}>
                            <span className={styles.tile} aria-hidden="true">
                              {vendorInitials(row.vendor_name)}
                            </span>
                            <div className={styles.stack}>
                              <strong title={row.vendor_name}>{row.vendor_name}</strong>
                              <span className={styles.mono}>{row.erp_vendor_id}</span>
                            </div>
                          </div>
                        </td>
                        <td className={styles.mono}>{row.sap_vendor_id || dash}</td>
                        <td className={styles.mono}>{row.gstin || dash}</td>
                        <td>
                          {row.contact_no || row.email ? (
                            <div className={styles.contact}>
                              {row.contact_no ? (
                                <a
                                  className={styles.contactLine}
                                  href={telHref(row.contact_no)}
                                  title={`Call ${row.contact_no}`}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <PhoneIcon size={13} />
                                  <span className={styles.contactPhone}>
                                    {formatMobile(row.contact_no)}
                                  </span>
                                </a>
                              ) : null}
                              {row.email ? (
                                <a
                                  className={styles.contactLine}
                                  href={`mailto:${row.email}`}
                                  title={row.email}
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <MailIcon size={13} />
                                  <span className={styles.contactText}>{row.email}</span>
                                </a>
                              ) : null}
                            </div>
                          ) : (
                            dash
                          )}
                        </td>
                        <td>
                          {row.location ? (
                            <span className={styles.location} title={row.location}>
                              {row.location}
                            </span>
                          ) : (
                            dash
                          )}
                        </td>
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
                          <button
                            type="button"
                            className={`${styles.iconBtn} ${
                              actionMenu?.row.id === row.id ? styles.iconBtnOpen : ""
                            }`}
                            data-action-trigger="true"
                            aria-label={`Actions for ${row.vendor_name}`}
                            aria-haspopup="menu"
                            aria-expanded={actionMenu?.row.id === row.id}
                            onClick={(event) => toggleActionMenu(row, event.currentTarget)}
                          >
                            <MoreIcon size={15} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <footer className={styles.footer}>
                <span className={styles.footerInfo}>
                  Showing {rangeFrom}–{rangeTo} of {totalCount} vendor
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
                  onChange={(event) => {
                    setPageSize(Number(event.target.value));
                    setPage(1);
                  }}
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
              <button
                type="button"
                className={shared.menuItem}
                role="menuitem"
                onClick={() => {
                  setActionMenu(null);
                  setPanel({ kind: "view", record: actionMenu.row });
                }}
              >
                View
              </button>
              {canEdit ? (
                <button
                  type="button"
                  className={shared.menuItem}
                  role="menuitem"
                  onClick={() => {
                    setActionMenu(null);
                    setPanel({ kind: "form", record: actionMenu.row });
                  }}
                >
                  Edit
                </button>
              ) : null}
              {!canToggleActive ? null : actionMenu.row.is_active ? (
                <button
                  type="button"
                  className={`${shared.menuItem} ${shared.menuItemDanger}`}
                  role="menuitem"
                  onClick={() => {
                    setActionMenu(null);
                    setConfirm(actionMenu.row);
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
                    void onActivate(actionMenu.row);
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
          {viewRecord ? (
            <VendorDetailsModal
              record={viewRecord}
              busy={statusBusy}
              onClose={() => setPanel(null)}
              onEdit={canEdit ? (record) => setPanel({ kind: "form", record }) : undefined}
              onDeactivate={canToggleActive ? (record) => setConfirm(record) : undefined}
              onActivate={canToggleActive ? (record) => void onActivate(record) : undefined}
            />
          ) : null}

          {panel?.kind === "form" ? (
            <VendorFormModal
              key={panel.record?.id ?? "new"}
              record={panel.record}
              locations={locations}
              onClose={() => setPanel(null)}
              onSaved={(record) => setPanel({ kind: "view", record })}
            />
          ) : null}

          {importFile ? (
            <VendorImportModal
              file={importFile}
              onClose={() => setImportFile(null)}
              onFinished={refetch}
            />
          ) : null}

          {confirm ? (
            <>
              <button
                type="button"
                className={`${shared.backdrop} ${styles.confirmBackdrop}`}
                aria-label="Close"
                onClick={() => !statusBusy && setConfirm(null)}
              />
              <div
                className={`${shared.modal} ${styles.confirmModal}`}
                role="dialog"
                aria-modal="true"
                data-layer="confirm"
                aria-labelledby="vendor-confirm-title"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2 id="vendor-confirm-title">Deactivate Vendor</h2>
                    <p>Deactivated vendors can be activated again later.</p>
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
                  Deactivate <strong>&quot;{confirm.vendor_name}&quot;</strong> (
                  {confirm.erp_vendor_id})?
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
                className={`${shared.backdrop} ${styles.confirmBackdrop}`}
                aria-label="Close"
                onClick={() => setNotice(null)}
              />
              <div
                className={`${shared.modal} ${styles.confirmModal}`}
                role="dialog"
                aria-modal="true"
                data-layer="confirm"
                aria-labelledby="vendor-notice-title"
              >
                <div className={shared.modalHeader}>
                  <div>
                    <h2 id="vendor-notice-title">{notice.title}</h2>
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

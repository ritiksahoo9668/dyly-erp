import { type ReactNode, useEffect, useRef } from "react";
import { CloseIcon } from "@/components/navigation/icons";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import {
  ClockIcon,
  IdCardIcon,
  LocationIcon,
  PencilIcon,
  PhoneIcon,
} from "../employee/employeeIcons";
import { formatDateTime, formatMobile, userName } from "../employee/employeeFormat";
import modal from "../employee/EmployeeDetailsModal.module.css";
import type { VendorRecord } from "@/types/vendor";
import { telHref, vendorInitials } from "./vendorFormat";
import styles from "./VendorPage.module.css";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className={modal.row}>
      <dt>{label}</dt>
      <dd>{value || <span className={modal.empty}>Not provided</span>}</dd>
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className={modal.card}>
      <h3 className={modal.cardTitle}>
        <span className={modal.cardIcon}>{icon}</span>
        {title}
      </h3>
      <dl className={modal.rows}>{children}</dl>
    </section>
  );
}

function TaxIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" />
      <path d="m9 14 6-6M9.5 8.5h.01M14.5 13.5h.01" />
    </svg>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className={`${modal.status} ${active ? modal.statusActive : modal.statusInactive}`}>
      <i aria-hidden="true" />
      {active ? "Active" : "Inactive"}
    </span>
  );
}

type Props = {
  record: VendorRecord;
  busy: boolean;
  onClose: () => void;
  onEdit?: (record: VendorRecord) => void;
  onDeactivate?: (record: VendorRecord) => void;
  onActivate?: (record: VendorRecord) => void;
};

export function VendorDetailsModal({
  record,
  busy,
  onClose,
  onEdit,
  onDeactivate,
  onActivate,
}: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (document.querySelector("[aria-modal='true'][data-layer='confirm']")) return;
      onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <>
      <button type="button" className={modal.backdrop} aria-label="Close" onClick={onClose} />
      <div
        className={`${modal.modal} ${styles.detailsModal}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="vendor-detail-title"
      >
        <header className={modal.hero}>
          <span className={styles.heroTile} aria-hidden="true">
            {vendorInitials(record.vendor_name)}
          </span>
          <div className={modal.heroText}>
            <div className={modal.heroTitle}>
              <h2 id="vendor-detail-title">{record.vendor_name}</h2>
              <StatusBadge active={record.is_active} />
            </div>
            <p className={modal.heroRole}>
              <span className={styles.mono}>{record.erp_vendor_id}</span>
              {record.sap_vendor_id ? (
                <>
                  <span aria-hidden="true">•</span>
                  SAP {record.sap_vendor_id}
                </>
              ) : null}
            </p>
            {record.location ? (
              <div className={modal.heroMeta}>
                <span>
                  <LocationIcon size={14} />
                  {record.location}
                </span>
              </div>
            ) : null}
          </div>
          <button
            ref={closeRef}
            type="button"
            className={modal.close}
            aria-label="Close"
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </header>

        <div className={modal.body}>
          <div className={modal.cardGrid}>
            <Card title="Basic Information" icon={<IdCardIcon size={15} />}>
              <Row
                label="ERP Vendor ID"
                value={<span className={styles.mono}>{record.erp_vendor_id}</span>}
              />
              <Row
                label="SAP Vendor ID"
                value={
                  record.sap_vendor_id ? (
                    <span className={styles.mono}>{record.sap_vendor_id}</span>
                  ) : (
                    ""
                  )
                }
              />
              <Row label="Vendor Name" value={record.vendor_name} />
              <Row label="Status" value={<StatusBadge active={record.is_active} />} />
            </Card>
            <Card title="Contact Information" icon={<PhoneIcon size={15} />}>
              <Row
                label="Email ID"
                value={
                  record.email ? (
                    <a className={styles.detailLink} href={`mailto:${record.email}`}>
                      {record.email}
                    </a>
                  ) : (
                    ""
                  )
                }
              />
              <Row
                label="Contact No."
                value={
                  record.contact_no ? (
                    <a className={styles.detailLink} href={telHref(record.contact_no)}>
                      {formatMobile(record.contact_no)}
                    </a>
                  ) : (
                    ""
                  )
                }
              />
              <Row label="Location" value={record.location} />
            </Card>
            <Card title="Tax Information" icon={<TaxIcon />}>
              <Row
                label="GSTIN"
                value={record.gstin ? <span className={styles.mono}>{record.gstin}</span> : ""}
              />
            </Card>
            <Card title="System Information" icon={<ClockIcon size={15} />}>
              <Row label="Created At" value={formatDateTime(record.created_at)} />
              <Row label="Updated At" value={formatDateTime(record.updated_at)} />
              <Row label="Created By" value={userName(record.created_by)} />
              <Row label="Updated By" value={userName(record.updated_by)} />
            </Card>
          </div>
        </div>

        <footer className={modal.footer}>
          {record.is_active && onDeactivate ? (
            <button
              type="button"
              className={modal.dangerLink}
              disabled={busy}
              onClick={() => onDeactivate(record)}
            >
              Deactivate Vendor
            </button>
          ) : null}
          {!record.is_active && onActivate ? (
            <button
              type="button"
              className={shared.secondaryBtn}
              disabled={busy}
              onClick={() => onActivate(record)}
            >
              {busy ? "Please wait…" : "Activate Vendor"}
            </button>
          ) : null}
          <span className={modal.spacer} />
          <button type="button" className={shared.secondaryBtn} onClick={onClose}>
            Close
          </button>
          {onEdit ? (
            <button
              type="button"
              className={`${shared.primaryBtn} ${modal.editBtn}`}
              onClick={() => onEdit(record)}
            >
              <PencilIcon size={15} />
              Edit Vendor
            </button>
          ) : null}
        </footer>
      </div>
    </>
  );
}

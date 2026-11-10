import { type ReactNode, useEffect, useRef } from "react";
import { CloseIcon, MailIcon } from "@/components/navigation/icons";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import type { EmployeeRecord } from "@/types/employee";
import {
  BriefcaseIcon,
  CalendarDayIcon,
  ClockIcon,
  IdCardIcon,
  LocationIcon,
  OrgIcon,
  PencilIcon,
  PhoneIcon,
} from "./employeeIcons";
import {
  avatarColor,
  formatDate,
  formatDateTime,
  formatMobile,
  formatTenure,
  initials,
  refName,
  userName,
} from "./employeeFormat";
import styles from "./EmployeeDetailsModal.module.css";

function Value({ children }: { children: ReactNode }) {
  return children ? <>{children}</> : <span className={styles.empty}>Not provided</span>;
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className={styles.row}>
      <dt>{label}</dt>
      <dd>
        <Value>{value}</Value>
      </dd>
    </div>
  );
}

function Card({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className={styles.card}>
      <h3 className={styles.cardTitle}>
        <span className={styles.cardIcon}>{icon}</span>
        {title}
      </h3>
      <dl className={styles.rows}>{children}</dl>
    </section>
  );
}

function QuickItem({
  icon,
  label,
  value,
  href,
  sub,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  href?: string;
  sub?: string;
}) {
  return (
    <div className={styles.quick}>
      <span className={styles.quickIcon}>{icon}</span>
      <div className={styles.quickText}>
        <span className={styles.quickLabel}>{label}</span>
        {value ? (
          href ? (
            <a className={styles.quickValue} href={href}>
              {value}
            </a>
          ) : (
            <strong className={styles.quickValue}>{value}</strong>
          )
        ) : (
          <span className={styles.empty}>Not provided</span>
        )}
        {sub ? <span className={styles.quickSub}>{sub}</span> : null}
      </div>
    </div>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className={`${styles.status} ${active ? styles.statusActive : styles.statusInactive}`}>
      <i aria-hidden="true" />
      {active ? "Active" : "Inactive"}
    </span>
  );
}

type Props = {
  record: EmployeeRecord | null;
  loading: boolean;
  error: string | null;
  busy: boolean;
  onClose: () => void;
  onEdit?: (record: EmployeeRecord) => void;
  onDeactivate?: (record: EmployeeRecord) => void;
  onActivate?: (record: EmployeeRecord) => void;
};

export function EmployeeDetailsModal({
  record,
  loading,
  error,
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

  const tenure = record ? formatTenure(record.date_of_joining) : "";

  return (
    <>
      <button type="button" className={styles.backdrop} aria-label="Close" onClick={onClose} />
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="employee-detail-title"
        aria-busy={loading}
      >
        <header className={styles.hero}>
          {record ? (
            <>
              <span
                className={styles.avatar}
                style={{ background: avatarColor(record.full_name) }}
                aria-hidden="true"
              >
                {initials(record.full_name)}
              </span>
              <div className={styles.heroText}>
                <div className={styles.heroTitle}>
                  <h2 id="employee-detail-title">{record.full_name}</h2>
                  <StatusBadge active={record.is_active} />
                </div>
                <p className={styles.heroRole}>
                  {refName(record.designation)}
                  <span aria-hidden="true">•</span>
                  {refName(record.department)}
                </p>
                <div className={styles.heroMeta}>
                  <span>
                    <OrgIcon size={14} />
                    {refName(record.company)}
                  </span>
                  <span>
                    <LocationIcon size={14} />
                    {record.location}
                  </span>
                  <span>{record.gender}</span>
                </div>
              </div>
            </>
          ) : (
            <div className={styles.heroText}>
              <h2 id="employee-detail-title">Employee Details</h2>
            </div>
          )}
          <button
            ref={closeRef}
            type="button"
            className={styles.close}
            aria-label="Close"
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </header>

        <div className={styles.body}>
          {loading ? (
            <div className={styles.skeleton} aria-label="Loading employee">
              <span />
              <span />
              <span />
            </div>
          ) : null}
          {error ? <p className={shared.formError}>{error}</p> : null}

          {record ? (
            <>
              <div className={styles.quickGrid}>
                <QuickItem
                  icon={<PhoneIcon size={16} />}
                  label="Mobile Number"
                  value={formatMobile(record.mobile_number)}
                  href={`tel:${record.mobile_number}`}
                />
                <QuickItem
                  icon={<CalendarDayIcon size={16} />}
                  label="Date Of Joining"
                  value={formatDate(record.date_of_joining)}
                  sub={tenure}
                />
                <QuickItem
                  icon={<MailIcon size={16} />}
                  label="Company Email"
                  value={record.company_email}
                  href={record.company_email ? `mailto:${record.company_email}` : undefined}
                />
                <QuickItem
                  icon={<MailIcon size={16} />}
                  label="Personal Email"
                  value={record.personal_email}
                  href={record.personal_email ? `mailto:${record.personal_email}` : undefined}
                />
              </div>

              <div className={styles.cardGrid}>
                <Card title="Employment" icon={<BriefcaseIcon size={15} />}>
                  <Row label="Department" value={refName(record.department)} />
                  <Row label="Vertical" value={refName(record.vertical)} />
                  <Row label="Designation" value={refName(record.designation)} />
                </Card>
                <Card title="Organization" icon={<OrgIcon size={15} />}>
                  <Row label="Company" value={refName(record.company)} />
                  <Row label="Division" value={refName(record.division)} />
                  <Row label="Facility" value={refName(record.facility)} />
                </Card>
                <Card title="Personal Information" icon={<IdCardIcon size={15} />}>
                  <Row label="Full Name" value={record.full_name} />
                  <Row label="Gender" value={record.gender} />
                  <Row label="Location" value={record.location} />
                </Card>
                <Card title="Record History" icon={<ClockIcon size={15} />}>
                  <Row label="Created" value={formatDateTime(record.created_at)} />
                  <Row label="Created By" value={userName(record.created_by)} />
                  <Row label="Last Updated" value={formatDateTime(record.updated_at)} />
                  <Row label="Updated By" value={userName(record.updated_by)} />
                </Card>
              </div>
            </>
          ) : null}
        </div>

        <footer className={styles.footer}>
          {record?.is_active && onDeactivate ? (
            <button
              type="button"
              className={styles.dangerLink}
              disabled={busy}
              onClick={() => onDeactivate(record)}
            >
              Deactivate Employee
            </button>
          ) : null}
          {record && !record.is_active && onActivate ? (
            <button
              type="button"
              className={shared.secondaryBtn}
              disabled={busy}
              onClick={() => onActivate(record)}
            >
              {busy ? "Please wait…" : "Activate Employee"}
            </button>
          ) : null}
          <span className={styles.spacer} />
          <button type="button" className={shared.secondaryBtn} onClick={onClose}>
            Close
          </button>
          {onEdit ? (
            <button
              type="button"
              className={`${shared.primaryBtn} ${styles.editBtn}`}
              disabled={!record}
              onClick={() => record && onEdit(record)}
            >
              <PencilIcon size={15} />
              Edit Employee
            </button>
          ) : null}
        </footer>
      </div>
    </>
  );
}

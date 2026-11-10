import { type ReactNode, useEffect, useRef, useState } from "react";
import { CloseIcon } from "@/components/navigation/icons";
import detailStyles from "@/modules/master/employee/EmployeeDetailsModal.module.css";
import { avatarColor, initials } from "@/modules/master/employee/employeeFormat";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import type { OnboardingAction, UserOnboardingDetail } from "@/types/userOnboarding";
import { AccessMatrix } from "./AccessMatrix";
import { Badge } from "./Badge";
import {
  ACTION_LABELS,
  DANGER_ACTIONS,
  accountStatus,
  eventValue,
  formatDateTime,
  invitationBadge,
  roleLabel,
  roleTone,
} from "./onboardingFormat";
import styles from "./UserOnboardingPage.module.css";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className={detailStyles.row}>
      <dt>{label}</dt>
      <dd>{value || <span className={detailStyles.empty}>—</span>}</dd>
    </div>
  );
}

function Card({
  title,
  children,
  wide,
}: {
  title: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <section className={`${detailStyles.card} ${wide ? styles.fullCard : ""}`}>
      <h3 className={detailStyles.cardTitle}>{title}</h3>
      {children}
    </section>
  );
}

type DetailTab = "overview" | "access" | "activity";

const DETAIL_TABS: [DetailTab, string][] = [
  ["overview", "Overview"],
  ["access", "Module Access"],
  ["activity", "Activity"],
];

type Props = {
  record: UserOnboardingDetail | undefined;
  loading: boolean;
  error: string | null;
  busy: boolean;
  onClose: () => void;
  onAction: (record: UserOnboardingDetail, action: OnboardingAction) => void;
};

export function OnboardingDetailsModal({ record, loading, error, busy, onClose, onAction }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const [tab, setTab] = useState<DetailTab>("overview");

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

  const actions = (record?.allowed_actions ?? []).filter((action) => action !== "view");
  const invite = record ? invitationBadge(record) : null;
  const account = record ? accountStatus(record) : null;

  return (
    <>
      <button type="button" className={detailStyles.backdrop} aria-label="Close" onClick={onClose} />
      <div
        className={detailStyles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-detail-title"
        aria-busy={loading}
      >
        <header className={detailStyles.hero}>
          {record ? (
            <>
              <span
                className={detailStyles.avatar}
                style={{ background: avatarColor(record.employee.full_name) }}
                aria-hidden="true"
              >
                {initials(record.employee.full_name)}
              </span>
              <div className={detailStyles.heroText}>
                <div className={detailStyles.heroTitle}>
                  <h2 id="onboarding-detail-title">{record.employee.full_name}</h2>
                  {invite ? <Badge label={invite.label} tone={invite.tone} dot /> : null}
                </div>
                <p className={detailStyles.heroRole}>
                  {record.onboarding_code}
                  <span aria-hidden="true">•</span>
                  {record.login_email}
                </p>
                <div className={detailStyles.heroMeta}>
                  <span>{record.employee.employee_code}</span>
                  <span>{roleLabel(record.role)}</span>
                  {record.employee.department ? <span>{record.employee.department.name}</span> : null}
                </div>
              </div>
            </>
          ) : (
            <div className={detailStyles.heroText}>
              <h2 id="onboarding-detail-title">Onboarding Details</h2>
            </div>
          )}
          <button
            ref={closeRef}
            type="button"
            className={detailStyles.close}
            aria-label="Close"
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </header>

        <div className={detailStyles.body}>
          {loading ? (
            <div className={detailStyles.skeleton} aria-label="Loading onboarding">
              <span />
              <span />
            </div>
          ) : null}
          {error ? <p className={shared.formError}>{error}</p> : null}

          {record ? (
            <div className={styles.tabs} role="tablist" aria-label="Onboarding details">
              {DETAIL_TABS.map(([key, label]) => (
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
          ) : null}

          {record && tab === "access" ? (
            <section className={detailStyles.card}>
              <h3 className={detailStyles.cardTitle}>Module Access</h3>
              {record.user === null && record.role !== "SUPERADMIN" ? (
                <p className={detailStyles.empty}>
                  Saved with the draft and applied to the account when the invitation is sent.
                </p>
              ) : null}
              <AccessMatrix value={record.access} role={record.role} readOnly />
            </section>
          ) : null}

          {record && tab === "activity" ? (
            <section className={detailStyles.card}>
              <h3 className={detailStyles.cardTitle}>Activity</h3>
              {record.events.length === 0 ? (
                <p className={detailStyles.empty}>No activity recorded yet.</p>
              ) : (
                <ol className={styles.timeline}>
                  {record.events.map((event) => (
                    <li key={event.id} className={styles.timelineItem}>
                      <strong>
                        {event.event_label}
                        {event.permission ? ` · ${event.permission}` : ""}
                      </strong>
                      <span>
                        {formatDateTime(event.created_at)}
                        {event.actor ? ` · ${event.actor.name}` : ""}
                        {event.from_value
                          ? ` · ${eventValue(event.from_value)} → ${eventValue(event.to_value)}`
                          : event.to_value
                            ? ` · ${eventValue(event.to_value)}`
                            : ""}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          ) : null}

          {record && tab === "overview" ? (
            <div className={detailStyles.cardGrid}>
              <Card title="Access">
                <dl className={detailStyles.rows}>
                  <Row label="Login Email" value={record.login_email} />
                  <Row
                    label="Role"
                    value={<Badge label={roleLabel(record.role)} tone={roleTone(record.role)} />}
                  />
                  <Row
                    label="Account"
                    value={account ? <Badge label={account.label} tone={account.tone} dot /> : null}
                  />
                  <Row label="Last Login" value={formatDateTime(record.user?.last_login)} />
                </dl>
              </Card>
              <Card title="Invitation">
                <dl className={detailStyles.rows}>
                  <Row label="First Sent" value={formatDateTime(record.invite_sent_at)} />
                  <Row label="Last Sent" value={formatDateTime(record.last_invite_sent_at)} />
                  <Row label="Expires" value={formatDateTime(record.invite_expires_at)} />
                  <Row label="Times Queued" value={String(record.invite_send_count)} />
                  <Row label="Activated" value={formatDateTime(record.activated_at)} />
                </dl>
              </Card>
              <Card title="Employee">
                <dl className={detailStyles.rows}>
                  <Row label="Designation" value={record.employee.designation?.name} />
                  <Row label="Company" value={record.employee.company?.name} />
                  <Row label="Unit" value={record.employee.unit?.name} />
                </dl>
              </Card>
              <Card title="Record">
                <dl className={detailStyles.rows}>
                  <Row label="Created" value={formatDateTime(record.created_at)} />
                  <Row label="Created By" value={record.created_by?.name} />
                  <Row label="Updated" value={formatDateTime(record.updated_at)} />
                  <Row label="Updated By" value={record.updated_by?.name} />
                </dl>
              </Card>
            </div>
          ) : null}
        </div>

        <footer className={detailStyles.footer}>
          {record
            ? actions.map((action) => (
                <button
                  key={action}
                  type="button"
                  className={
                    DANGER_ACTIONS.has(action) ? detailStyles.dangerLink : shared.secondaryBtn
                  }
                  disabled={busy}
                  onClick={() => onAction(record, action)}
                >
                  {ACTION_LABELS[action]}
                </button>
              ))
            : null}
          <span className={detailStyles.spacer} />
          <button type="button" className={shared.secondaryBtn} onClick={onClose}>
            Close
          </button>
        </footer>
      </div>
    </>
  );
}

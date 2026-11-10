import type { ReactNode } from "react";
import { CloseIcon } from "@/components/navigation/icons";
import shared from "@/modules/master/shared/NameMasterPage.module.css";

function Layer({
  id,
  title,
  subtitle,
  busy,
  onClose,
  children,
}: {
  id: string;
  title: string;
  subtitle?: string;
  busy?: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <>
      <button
        type="button"
        className={shared.backdrop}
        style={{ zIndex: 80 }}
        aria-label="Close"
        onClick={() => !busy && onClose()}
      />
      <div
        className={shared.modal}
        style={{ zIndex: 90 }}
        role="dialog"
        aria-modal="true"
        data-layer="confirm"
        aria-labelledby={id}
      >
        <div className={shared.modalHeader}>
          <div>
            <h2 id={id}>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          <button
            type="button"
            className={shared.closeBtn}
            aria-label="Close"
            disabled={busy}
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </div>
        {children}
      </div>
    </>
  );
}

export type ConfirmRequest = {
  title: string;
  message: ReactNode;
  subtitle?: string;
  confirmLabel: string;
  danger?: boolean;
  run: () => Promise<void>;
};

export function ConfirmDialog({
  request,
  busy,
  onCancel,
  onConfirm,
}: {
  request: ConfirmRequest;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Layer
      id="onboarding-confirm-title"
      title={request.title}
      subtitle={request.subtitle}
      busy={busy}
      onClose={onCancel}
    >
      <p className={shared.confirmMessage}>{request.message}</p>
      <div className={shared.formActions}>
        <button type="button" className={shared.secondaryBtn} disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className={request.danger ? shared.dangerBtn : shared.primaryBtn}
          disabled={busy}
          onClick={onConfirm}
        >
          {busy ? "Please wait…" : request.confirmLabel}
        </button>
      </div>
    </Layer>
  );
}

export type Notice = { title: string; message: string };

export function NoticeDialog({ notice, onClose }: { notice: Notice; onClose: () => void }) {
  return (
    <Layer id="onboarding-notice-title" title={notice.title} subtitle={notice.message} onClose={onClose}>
      <div className={shared.formActions}>
        <button type="button" className={shared.primaryBtn} onClick={onClose}>
          OK
        </button>
      </div>
    </Layer>
  );
}

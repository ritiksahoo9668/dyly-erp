import { useEffect, useRef, useState } from "react";
import {
  downloadImportJobErrors,
  useImportVendorsMutation,
  useLazyGetImportJobQuery,
  useValidateVendorsMutation,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { CloseIcon } from "@/components/navigation/icons";
import type { ImportJob } from "@/types/nameMaster";
import type { VendorImportPreview, VendorPreviewStatus } from "@/types/vendor";
import { extractApiError } from "@/utils/extractApiError";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import styles from "./VendorPage.module.css";

const TERMINAL_JOB_STATUSES = new Set(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]);

const STATUS_LABEL: Record<VendorPreviewStatus, string> = {
  valid: "Ready",
  existing: "Skipped Existing",
  duplicate: "Duplicate in File",
  failed: "Failed",
};

const STATUS_CLASS: Record<VendorPreviewStatus, string> = {
  valid: styles.pillValid,
  existing: styles.pillExisting,
  duplicate: styles.pillDuplicate,
  failed: styles.pillFailed,
};

type Props = {
  file: File;
  onClose: () => void;
  onFinished: () => void;
};

export function VendorImportModal({ file, onClose, onFinished }: Props) {
  const accessToken = useAppSelector(selectAccessToken);
  const [validateFile] = useValidateVendorsMutation();
  const [startImport] = useImportVendorsMutation();
  const [fetchImportJob] = useLazyGetImportJobQuery();
  const [preview, setPreview] = useState<VendorImportPreview | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [errorDownloadBusy, setErrorDownloadBusy] = useState(false);
  const onFinishedRef = useRef(onFinished);

  useEffect(() => {
    onFinishedRef.current = onFinished;
  }, [onFinished]);

  const jobDone = Boolean(job && TERMINAL_JOB_STATUSES.has(job.status));
  const busy = starting || Boolean(job && !jobDone);

  useEffect(() => {
    let cancelled = false;
    validateFile(file)
      .unwrap()
      .then((result) => {
        if (!cancelled) setPreview(result);
      })
      .catch((err) => {
        if (!cancelled) setError(extractApiError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [file, validateFile]);

  useEffect(() => {
    if (!job || TERMINAL_JOB_STATUSES.has(job.status)) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchImportJob(job.id).unwrap();
        if (cancelled) return;
        setJob(latest);
        if (TERMINAL_JOB_STATUSES.has(latest.status)) onFinishedRef.current();
      } catch {
        // keep polling
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job, fetchImportJob]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, onClose]);

  async function onConfirmImport() {
    setError(null);
    setStarting(true);
    try {
      setJob(await startImport(file).unwrap());
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setStarting(false);
    }
  }

  async function onDownloadErrors() {
    if (!job?.has_error_file) return;
    setErrorDownloadBusy(true);
    try {
      await downloadImportJobErrors(job.id, accessToken);
    } catch {
      setError("Unable to download error file.");
    } finally {
      setErrorDownloadBusy(false);
    }
  }

  const title = job
    ? jobDone
      ? job.status === "FAILED"
        ? "Import Failed"
        : "Import Completed"
      : "Importing Vendors"
    : "Review Excel Upload";
  const hiddenRows = preview ? preview.total - preview.rows.length : 0;
  const hasIssues = preview ? preview.duplicate + preview.failed > 0 : false;
  const dash = <span className={styles.muted}>—</span>;

  return (
    <>
      <button
        type="button"
        className={shared.backdrop}
        aria-label="Close"
        onClick={() => {
          if (!busy) onClose();
        }}
      />
      <div
        className={`${shared.modal} ${shared.importModal} ${styles.importModal}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="vendor-import-title"
      >
        <div className={shared.modalHeader}>
          <div>
            <h2 id="vendor-import-title">{title}</h2>
            <p>{job ? job.progress_label || file.name : file.name}</p>
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

        {error ? <p className={shared.formError}>{error}</p> : null}
        {!preview && !error ? <p className={shared.loading}>Checking file…</p> : null}

        {preview && !job ? (
          <>
            <div className={`${shared.summary} ${styles.summaryFive}`}>
              <div className={shared.summaryCard}>
                <span>Total Rows</span>
                <strong>{preview.total}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Ready</span>
                <strong>{preview.valid}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Existing</span>
                <strong>{preview.existing}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Duplicate</span>
                <strong>{preview.duplicate}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Failed</span>
                <strong>{preview.failed}</strong>
              </div>
            </div>

            {preview.total === 0 && preview.errors.length ? (
              <ul className={shared.errorList}>
                {preview.errors.map((item) => (
                  <li key={`${item.row}-${item.reason}`}>{item.reason}</li>
                ))}
              </ul>
            ) : null}

            {preview.rows.length ? (
              <div className={shared.previewTableWrap}>
                <table className={shared.previewTable}>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Vendor Name</th>
                      <th>SAP Vendor ID</th>
                      <th>GSTIN</th>
                      <th>Status</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row) => (
                      <tr key={row.row}>
                        <td>{row.row}</td>
                        <td>{row.vendor_name || dash}</td>
                        <td className={styles.mono}>{row.sap_vendor_id || dash}</td>
                        <td className={styles.mono}>{row.gstin || dash}</td>
                        <td>
                          <span className={`${styles.pill} ${STATUS_CLASS[row.status]}`}>
                            {STATUS_LABEL[row.status]}
                          </span>
                        </td>
                        <td className={styles.reason}>{row.reason || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {hiddenRows > 0 ? (
              <p className={shared.importDetail}>
                Showing {preview.rows.length} of {preview.total} rows. Rows with problems are listed
                first.
              </p>
            ) : null}
            {preview.total > 0 ? (
              <p className={shared.importDetail}>
                {preview.valid} new Vendor{preview.valid === 1 ? "" : "s"} will be created as
                Active, each with a new ERP Vendor ID.
                {preview.existing ? ` ${preview.existing} existing will be skipped.` : ""}
                {hasIssues ? " Rows with errors will not be imported." : ""}
              </p>
            ) : null}

            <div className={shared.formActions}>
              <button
                type="button"
                className={shared.secondaryBtn}
                disabled={starting}
                onClick={onClose}
              >
                Cancel
              </button>
              <button
                type="button"
                className={shared.primaryBtn}
                disabled={starting || preview.valid === 0}
                onClick={onConfirmImport}
              >
                {starting
                  ? "Starting…"
                  : `Import ${preview.valid} Vendor${preview.valid === 1 ? "" : "s"}`}
              </button>
            </div>
          </>
        ) : null}

        {job ? (
          <>
            <div className={shared.progressBlock}>
              <div className={shared.progressMeta}>
                <strong>{job.status.replaceAll("_", " ")}</strong>
                <span>{job.progress_percentage}%</span>
              </div>
              <div className={shared.progressTrack}>
                <div
                  className={shared.progressFill}
                  style={{ width: `${job.progress_percentage}%` }}
                />
              </div>
            </div>
            <div className={shared.summary}>
              <div className={shared.summaryCard}>
                <span>Total Rows</span>
                <strong>{job.total_rows}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Created</span>
                <strong>{job.created_rows}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Skipped Existing</span>
                <strong>{job.skipped_rows}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Failed</span>
                <strong>{job.failed_rows}</strong>
              </div>
            </div>
            {job.detail ? <p className={shared.importDetail}>{job.detail}</p> : null}
            <div className={shared.formActions}>
              {job.has_error_file ? (
                <button
                  type="button"
                  className={shared.secondaryBtn}
                  disabled={errorDownloadBusy}
                  onClick={onDownloadErrors}
                >
                  {errorDownloadBusy ? "Downloading…" : "Download Error Excel"}
                </button>
              ) : null}
              <button
                type="button"
                className={shared.primaryBtn}
                disabled={!jobDone}
                onClick={onClose}
              >
                {jobDone ? "Done" : "Running…"}
              </button>
            </div>
          </>
        ) : null}

        {error && !preview && !job ? (
          <div className={shared.formActions}>
            <button type="button" className={shared.primaryBtn} onClick={onClose}>
              Close
            </button>
          </div>
        ) : null}
      </div>
    </>
  );
}

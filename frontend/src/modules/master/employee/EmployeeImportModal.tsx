import { useEffect, useState } from "react";
import {
  downloadImportJobErrors,
  useImportEmployeesMutation,
  useLazyGetImportJobQuery,
  useValidateEmployeesMutation,
} from "@/app/store/api";
import { selectAccessToken } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { CloseIcon } from "@/components/navigation/icons";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import type { EmployeeImportPreview, EmployeePreviewRowStatus } from "@/types/employee";
import type { ImportJob } from "@/types/nameMaster";
import { extractApiError } from "@/utils/extractApiError";
import styles from "./EmployeePage.module.css";

const TERMINAL_JOB_STATUSES = new Set(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]);

const STATUS_LABEL: Record<EmployeePreviewRowStatus, string> = {
  valid: "Valid",
  existing: "Existing",
  possible_duplicate: "Possible Duplicate",
  failed: "Failed",
};

const STATUS_CLASS: Record<EmployeePreviewRowStatus, string> = {
  valid: styles.statusValid,
  existing: styles.statusExisting,
  possible_duplicate: styles.statusPossible,
  failed: styles.statusFailed,
};

type Props = {
  file: File;
  onClose: () => void;
  onFinished: () => void;
};

export function EmployeeImportModal({ file, onClose, onFinished }: Props) {
  const accessToken = useAppSelector(selectAccessToken);
  const [validateImport, validateState] = useValidateEmployeesMutation();
  const [importEmployees, importState] = useImportEmployeesMutation();
  const [fetchImportJob] = useLazyGetImportJobQuery();
  const [preview, setPreview] = useState<EmployeeImportPreview | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const running = Boolean(job && !TERMINAL_JOB_STATUSES.has(job.status));
  const finished = Boolean(job && TERMINAL_JOB_STATUSES.has(job.status));

  useEffect(() => {
    let cancelled = false;
    validateImport(file)
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
  }, [file, validateImport]);

  useEffect(() => {
    if (!job || TERMINAL_JOB_STATUSES.has(job.status)) return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const latest = await fetchImportJob(job.id).unwrap();
        if (cancelled) return;
        setJob(latest);
        if (TERMINAL_JOB_STATUSES.has(latest.status)) onFinished();
      } catch {
        // Keep polling; transient network errors should not close the dialog.
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job, fetchImportJob, onFinished]);

  async function onConfirm() {
    setError(null);
    try {
      setJob(await importEmployees(file).unwrap());
    } catch (err) {
      setError(extractApiError(err));
    }
  }

  async function onDownloadErrors() {
    if (!job?.has_error_file) return;
    setDownloading(true);
    try {
      await downloadImportJobErrors(job.id, accessToken);
    } catch {
      setError("Unable to download error file.");
    } finally {
      setDownloading(false);
    }
  }

  const title = finished
    ? job?.status === "FAILED"
      ? "Import Failed"
      : "Import Summary"
    : job
      ? "Importing Employees"
      : "Validate Import";

  return (
    <>
      <button
        type="button"
        className={shared.backdrop}
        aria-label="Close"
        onClick={() => !running && onClose()}
      />
      <div
        className={`${shared.modal} ${shared.importModal}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="employee-import-title"
      >
        <div className={shared.modalHeader}>
          <div>
            <h2 id="employee-import-title">{title}</h2>
            <p>
              {job
                ? job.detail || job.progress_label
                : preview
                  ? `${file.name} — review the dry run before importing.`
                  : `Validating ${file.name}…`}
            </p>
          </div>
          <button
            type="button"
            className={shared.closeBtn}
            aria-label="Close"
            disabled={running}
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </div>

        {validateState.isLoading ? (
          <p className={shared.loading}>Validating template and rows…</p>
        ) : null}
        {error ? <p className={shared.formError}>{error}</p> : null}

        {preview && !job ? (
          <>
            <div className={`${shared.summary} ${styles.summaryFive}`}>
              <div className={shared.summaryCard}>
                <span>Total Rows</span>
                <strong>{preview.total}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Valid</span>
                <strong>{preview.valid}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Possible Duplicates</span>
                <strong>{preview.possible_duplicates}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Existing</span>
                <strong>{preview.existing}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Failed</span>
                <strong>{preview.failed}</strong>
              </div>
            </div>
            <p className={shared.importDetail}>
              {preview.valid > 0
                ? `${preview.valid} employee(s) will be created as Active. Existing mobile numbers are skipped; possible duplicates and failed rows are not imported.`
                : "No new employees to create."}
            </p>
            {preview.rows.length > 0 ? (
              <div className={shared.previewTableWrap}>
                <table className={shared.previewTable}>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Full Name</th>
                      <th>Mobile</th>
                      <th>Status</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((row) => (
                      <tr key={row.row}>
                        <td>{row.row}</td>
                        <td>{row.full_name}</td>
                        <td>{row.mobile_number}</td>
                        <td>
                          <span className={`${styles.statusPill} ${STATUS_CLASS[row.status]}`}>
                            {STATUS_LABEL[row.status]}
                          </span>
                        </td>
                        <td>{row.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            <div className={shared.formActions}>
              <button type="button" className={shared.secondaryBtn} onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                className={shared.primaryBtn}
                disabled={importState.isLoading || preview.valid === 0}
                onClick={onConfirm}
              >
                {importState.isLoading ? "Starting import…" : "Confirm Import"}
              </button>
            </div>
          </>
        ) : null}

        {job ? (
          <>
            <div className={shared.progressBlock}>
              <div className={shared.progressMeta}>
                <strong>{job.status.replaceAll("_", " ")}</strong>
                <span>{job.progress_label}</span>
              </div>
              <div className={shared.progressTrack}>
                <div
                  className={shared.progressFill}
                  style={{ width: `${job.progress_percentage}%` }}
                />
              </div>
            </div>
            <div className={`${shared.summary} ${styles.summaryFive}`}>
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
                <span>Possible Duplicates</span>
                <strong>{job.warning_rows ?? 0}</strong>
              </div>
              <div className={shared.summaryCard}>
                <span>Failed</span>
                <strong>{job.failed_rows}</strong>
              </div>
            </div>
            <div className={shared.formActions}>
              {job.has_error_file ? (
                <button
                  type="button"
                  className={shared.secondaryBtn}
                  disabled={downloading}
                  onClick={onDownloadErrors}
                >
                  {downloading ? "Downloading…" : "Download Error Excel"}
                </button>
              ) : null}
              <button
                type="button"
                className={shared.primaryBtn}
                disabled={running}
                onClick={onClose}
              >
                {running ? "Running…" : "Done"}
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

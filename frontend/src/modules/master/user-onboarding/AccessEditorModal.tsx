import { useEffect, useRef, useState } from "react";
import { useGetUserAccessQuery, useUpdateUserAccessMutation } from "@/app/store/api";
import { CloseIcon } from "@/components/navigation/icons";
import detailStyles from "@/modules/master/employee/EmployeeDetailsModal.module.css";
import { parseEmployeeErrors } from "@/modules/master/employee/employeeErrors";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import type { AccessAssignment } from "@/types/access";
import type { UserRole } from "@/types/userOnboarding";
import { extractApiError } from "@/utils/extractApiError";
import { AccessMatrix } from "./AccessMatrix";

type Props = {
  userId: number;
  name: string;
  email: string;
  onClose: () => void;
};

/** Edit an ERP user's module access after onboarding (changes apply on the user's next request). */
export function AccessEditorModal({ userId, name, email, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const query = useGetUserAccessQuery(userId, { refetchOnMountOrArgChange: true });
  const [save, saveState] = useUpdateUserAccessMutation();
  const [draft, setDraft] = useState<AccessAssignment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const data = query.data;
  const value = draft ?? data?.access ?? {};
  const editable = Boolean(data?.editable);

  useEffect(() => {
    closeRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !saveState.isLoading) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, saveState.isLoading]);

  async function submit() {
    setError(null);
    try {
      await save({ id: userId, access: value }).unwrap();
      onClose();
    } catch (err) {
      const parsed = parseEmployeeErrors(err);
      setError(parsed.fields.access || parsed.message || extractApiError(err));
    }
  }

  return (
    <>
      <button
        type="button"
        className={detailStyles.backdrop}
        aria-label="Close"
        onClick={() => !saveState.isLoading && onClose()}
      />
      <div
        className={detailStyles.modal}
        role="dialog"
        aria-modal="true"
        data-layer="confirm"
        aria-labelledby="access-editor-title"
        aria-busy={query.isFetching}
      >
        <header className={detailStyles.hero}>
          <div className={detailStyles.heroText}>
            <h2 id="access-editor-title">Module Access</h2>
            <p className={detailStyles.heroRole}>
              {name}
              <span aria-hidden="true">•</span>
              {email}
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            className={detailStyles.close}
            aria-label="Close"
            disabled={saveState.isLoading}
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </header>

        <div className={detailStyles.body}>
          {query.isLoading ? <p className={shared.loading}>Loading access…</p> : null}
          {query.isError ? <p className={shared.formError}>{extractApiError(query.error)}</p> : null}
          {error ? <p className={shared.formError}>{error}</p> : null}
          {data ? (
            <>
              {!editable && !data.full_access ? (
                <p className={shared.formError}>
                  You can view this user&apos;s access but are not allowed to change it.
                </p>
              ) : null}
              <AccessMatrix
                value={value}
                role={data.role as UserRole}
                readOnly={!editable}
                onChange={setDraft}
              />
            </>
          ) : null}
        </div>

        <footer className={detailStyles.footer}>
          <span className={detailStyles.spacer} />
          <button
            type="button"
            className={shared.secondaryBtn}
            disabled={saveState.isLoading}
            onClick={onClose}
          >
            {editable ? "Cancel" : "Close"}
          </button>
          {editable ? (
            <button
              type="button"
              className={shared.primaryBtn}
              disabled={saveState.isLoading || draft === null}
              onClick={() => void submit()}
            >
              {saveState.isLoading ? "Saving…" : "Save Access"}
            </button>
          ) : null}
        </footer>
      </div>
    </>
  );
}

import { type FormEvent, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useResetPasswordMutation } from "@/app/store/api";
import { ArrowRightIcon, EyeIcon, EyeOffIcon, LockIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { AuthCardFooter, AuthField } from "./AuthShell";
import styles from "./AuthShell.module.css";

function extractError(error: unknown): string {
  if (!error || typeof error !== "object" || !("data" in error)) {
    return "Unable to reset password. Please try again.";
  }
  const data = (error as { data?: { detail?: unknown; error?: { detail?: unknown } } }).data;
  const detail = data?.detail ?? data?.error?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const values = Object.values(detail as Record<string, unknown>).flat();
    const first = values.find((value) => typeof value === "string");
    if (typeof first === "string") return first;
  }
  return "Unable to reset password. Please try again.";
}

export function ResetPasswordPage() {
  useDocumentTitle("Reset password");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = useMemo(() => params.get("token")?.trim() ?? "", [params]);
  const [resetPassword, { isLoading }] = useResetPasswordMutation();
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (!token) {
      setError("This reset link is missing a token.");
      return;
    }
    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      return;
    }
    try {
      const result = await resetPassword({
        token,
        password,
        password_confirm: passwordConfirm,
      }).unwrap();
      setSuccess(result.detail);
      window.setTimeout(() => navigate("/login", { replace: true }), 1200);
    } catch (err) {
      setError(extractError(err));
    }
  }

  return (
    <>
      <h1 className={styles.title}>Reset password</h1>
      <p className={styles.subtitle}>Choose a new password for your account.</p>
      {success ? <p className={styles.success}>{success}</p> : null}

      <form className={styles.form} onSubmit={onSubmit}>
        {error ? <p className={styles.error}>{error}</p> : null}

        <AuthField id="reset-password" label="New password">
          <div className={styles.inputWrap}>
            <span className={styles.inputIcon} aria-hidden="true">
              <LockIcon />
            </span>
            <input
              id="reset-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <button
              type="button"
              className={styles.toggleVisibility}
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? <EyeOffIcon /> : <EyeIcon />}
            </button>
          </div>
        </AuthField>

        <AuthField id="reset-password-confirm" label="Confirm password">
          <div className={styles.inputWrap}>
            <span className={styles.inputIcon} aria-hidden="true">
              <LockIcon />
            </span>
            <input
              id="reset-password-confirm"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={passwordConfirm}
              onChange={(event) => setPasswordConfirm(event.target.value)}
            />
          </div>
        </AuthField>

        <button className={styles.submit} type="submit" disabled={isLoading || !token}>
          {isLoading ? "Updating…" : "Update password"}
          {!isLoading ? <ArrowRightIcon /> : null}
        </button>
      </form>

      <Link className={styles.backLink} to="/login">
        Back to sign in
      </Link>
      <AuthCardFooter />
    </>
  );
}

import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useActivateAccountMutation, useValidateActivationTokenMutation } from "@/app/store/api";
import { ArrowRightIcon, EyeIcon, EyeOffIcon, LockIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { AuthCardFooter, AuthField } from "./AuthShell";
import styles from "./AuthShell.module.css";

type LinkState = "loading" | "valid" | "invalid" | "expired" | "success";

const EXPIRED_MESSAGE =
  "This invitation has expired. Please contact your ERP administrator for a new invitation.";
const INVALID_MESSAGE = "This invitation link is invalid or has already been used.";

type ApiFailure = { status?: number | string; data?: unknown };

function responseStatus(error: unknown): number | string | undefined {
  return (error as ApiFailure | null)?.status;
}

/** `"invalid"` / `"expired"` when the API rejected the link itself rather than the password. */
function linkStatus(error: unknown): string | undefined {
  const data = (error as ApiFailure | null)?.data as { status?: unknown } | undefined;
  return typeof data?.status === "string" ? data.status : undefined;
}

function firstMessage(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (Array.isArray(value)) return firstMessage(value[0]);
  if (value && typeof value === "object") {
    for (const item of Object.values(value as Record<string, unknown>)) {
      const message = firstMessage(item);
      if (message) return message;
    }
  }
  return null;
}

/** Messages for password validation errors (wrapped `{error: {detail}}` or plain `{detail}`). */
function formError(error: unknown): string {
  const data = (error as ApiFailure | null)?.data as
    | { detail?: unknown; error?: { detail?: unknown } }
    | undefined;
  return (
    firstMessage(data?.error?.detail) ??
    firstMessage(data?.detail) ??
    "Unable to activate the account. Please try again."
  );
}

export function ActivateAccountPage() {
  useDocumentTitle("Activate account");
  const { token = "" } = useParams<{ token: string }>();
  const [validate] = useValidateActivationTokenMutation();
  const [activate, { isLoading }] = useActivateAccountMutation();
  const [state, setState] = useState<LinkState>("loading");
  const [employeeName, setEmployeeName] = useState("");
  const [loginEmail, setLoginEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linkMessage, setLinkMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      if (!token.trim()) {
        setState("invalid");
        return;
      }
      try {
        const result = await validate({ token: token.trim() }).unwrap();
        if (cancelled) return;
        setEmployeeName(result.employee_name);
        setLoginEmail(result.login_email);
        setState("valid");
      } catch (err) {
        if (cancelled) return;
        const status = responseStatus(err);
        if (status === 429) {
          setLinkMessage("Too many attempts. Please wait a few minutes and try again.");
          setState("invalid");
        } else {
          setState(status === 410 ? "expired" : "invalid");
        }
      }
    }
    void check();
    return () => {
      cancelled = true;
    };
  }, [token, validate]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      return;
    }
    try {
      await activate({ token: token.trim(), password, password_confirm: passwordConfirm }).unwrap();
      setPassword("");
      setPasswordConfirm("");
      setState("success");
    } catch (err) {
      const status = responseStatus(err);
      if (status === 410) setState("expired");
      else if (linkStatus(err) === "invalid") setState("invalid");
      else setError(formError(err));
    }
  }

  if (state === "loading") {
    return (
      <>
        <h1 className={styles.title}>Activate your account</h1>
        <p className={styles.subtitle}>Checking your invitation link…</p>
      </>
    );
  }

  if (state === "expired" || state === "invalid") {
    return (
      <>
        <h1 className={styles.title}>
          {state === "expired" ? "Invitation expired" : "Invitation link not valid"}
        </h1>
        <p className={styles.error}>
          {linkMessage ?? (state === "expired" ? EXPIRED_MESSAGE : INVALID_MESSAGE)}
        </p>
        <Link className={styles.backLink} to="/login">
          Go to sign in
        </Link>
        <AuthCardFooter />
      </>
    );
  }

  if (state === "success") {
    return (
      <>
        <h1 className={styles.title}>Account Activated Successfully</h1>
        <p className={styles.success}>
          Your password has been set. You can now sign in with {loginEmail || "your login email"}.
        </p>
        <Link className={styles.submit} style={{ textDecoration: "none" }} to="/login" replace>
          Go to Login
          <ArrowRightIcon />
        </Link>
        <AuthCardFooter />
      </>
    );
  }

  return (
    <>
      <h1 className={styles.title}>Welcome, {employeeName}</h1>
      <p className={styles.subtitle}>
        Create a password to activate your DYLY ERP account for <strong>{loginEmail}</strong>.
      </p>

      <form className={styles.form} onSubmit={onSubmit}>
        {error ? <p className={styles.error}>{error}</p> : null}

        <AuthField id="activate-password" label="Create Password *">
          <div className={styles.inputWrap}>
            <span className={styles.inputIcon} aria-hidden="true">
              <LockIcon />
            </span>
            <input
              id="activate-password"
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

        <AuthField id="activate-password-confirm" label="Confirm Password *">
          <div className={styles.inputWrap}>
            <span className={styles.inputIcon} aria-hidden="true">
              <LockIcon />
            </span>
            <input
              id="activate-password-confirm"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              required
              minLength={8}
              value={passwordConfirm}
              onChange={(event) => setPasswordConfirm(event.target.value)}
            />
          </div>
        </AuthField>

        <p className={styles.subtitle}>
          Use at least 8 characters. Avoid common passwords and details like your name or email.
        </p>

        <button className={styles.submit} type="submit" disabled={isLoading}>
          {isLoading ? "Activating…" : "Activate Account"}
          {!isLoading ? <ArrowRightIcon /> : null}
        </button>
      </form>

      <AuthCardFooter />
    </>
  );
}

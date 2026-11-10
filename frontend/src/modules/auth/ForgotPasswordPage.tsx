import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useForgotPasswordMutation } from "@/app/store/api";
import { ArrowRightIcon, MailIcon } from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { AuthCardFooter, AuthField } from "./AuthShell";
import styles from "./AuthShell.module.css";

function extractError(error: unknown): string {
  if (!error || typeof error !== "object" || !("data" in error)) {
    return "Unable to process this request. Please try again.";
  }
  const data = (error as { data?: { detail?: unknown; error?: { detail?: unknown } } }).data;
  const detail = data?.detail ?? data?.error?.detail;
  if (typeof detail === "string") return detail;
  return "Unable to process this request. Please try again.";
}

export function ForgotPasswordPage() {
  useDocumentTitle("Forgot password");
  const [forgotPassword, { isLoading }] = useForgotPasswordMutation();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setDetail(null);
    try {
      const result = await forgotPassword({ email: email.trim() }).unwrap();
      setDetail(result.detail);
    } catch (err) {
      setError(extractError(err));
    }
  }

  return (
    <>
      <h1 className={styles.title}>Forgot password</h1>
      <p className={styles.subtitle}>
        Enter your account email. If a matching active account exists, we will email you a link to
        reset your password.
      </p>

      {detail ? <p className={styles.success}>{detail}</p> : null}

      <form className={styles.form} onSubmit={onSubmit}>
        {error ? <p className={styles.error}>{error}</p> : null}
        <AuthField id="forgot-email" label="Email">
          <div className={styles.inputWrap}>
            <span className={styles.inputIcon} aria-hidden="true">
              <MailIcon />
            </span>
            <input
              id="forgot-email"
              type="email"
              autoComplete="username"
              placeholder="you@company.com"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
        </AuthField>
        <button className={styles.submit} type="submit" disabled={isLoading}>
          {isLoading ? "Submitting…" : "Continue"}
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

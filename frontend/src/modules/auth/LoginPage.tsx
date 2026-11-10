import { type FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useLoginMutation } from "@/app/store/api";
import { selectIsAuthenticated, setCredentials } from "@/app/store/authSlice";
import { useAppDispatch, useAppSelector } from "@/app/store/hooks";
import {
  ArrowRightIcon,
  EyeIcon,
  EyeOffIcon,
  LockIcon,
  MailIcon,
} from "@/components/navigation/icons";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { AuthCardFooter, AuthField } from "./AuthShell";
import styles from "./AuthShell.module.css";

function extractError(error: unknown): string {
  if (!error || typeof error !== "object" || !("data" in error)) {
    return "Unable to sign in. Please try again.";
  }
  const data = (error as { data?: { detail?: unknown; error?: { detail?: unknown } } }).data;
  const detail = data?.detail ?? data?.error?.detail;
  if (typeof detail === "string") return detail;
  return "Unable to sign in. Please try again.";
}

export function LoginPage() {
  useDocumentTitle("Sign in");
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const isAuthenticated = useAppSelector(selectIsAuthenticated);
  const [login, { isLoading }] = useLoginMutation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from =
    (location.state as { from?: string } | null)?.from &&
    (location.state as { from: string }).from !== "/login"
      ? (location.state as { from: string }).from
      : "/";

  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      const result = await login({ email: email.trim(), password }).unwrap();
      dispatch(
        setCredentials({
          access: result.access,
          refresh: result.refresh,
          user: result.user,
          rememberMe,
        }),
      );
      navigate(from, { replace: true });
    } catch (err) {
      setError(extractError(err));
    }
  }

  return (
    <>
      <h1 className={styles.title}>Welcome Back</h1>
      <p className={styles.subtitle}>Sign in to your DYLY ERP account to continue.</p>

      <form className={styles.form} onSubmit={onSubmit}>
        {error ? <p className={styles.error}>{error}</p> : null}

        <AuthField id="login-email" label="Email">
          <div className={styles.inputWrap}>
            <span className={styles.inputIcon} aria-hidden="true">
              <MailIcon />
            </span>
            <input
              id="login-email"
              type="email"
              autoComplete="username"
              placeholder="you@company.com"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
        </AuthField>

        <AuthField id="login-password" label="Password">
          <div className={styles.inputWrap}>
            <span className={styles.inputIcon} aria-hidden="true">
              <LockIcon />
            </span>
            <input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Enter your password"
              required
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

        <div className={styles.rowBetween}>
          <label className={styles.remember}>
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
            />
            Keep me signed in
          </label>
          <Link className={styles.forgotLink} to="/forgot-password">
            Forgot password?
          </Link>
        </div>

        <button className={styles.submit} type="submit" disabled={isLoading}>
          {isLoading ? "Signing in…" : "Sign in"}
          {!isLoading ? <ArrowRightIcon /> : null}
        </button>
      </form>

      <AuthCardFooter />
    </>
  );
}

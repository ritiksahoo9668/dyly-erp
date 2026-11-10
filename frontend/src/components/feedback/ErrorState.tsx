import styles from "./feedback.module.css";

type ErrorStateProps = {
  message: string;
  compact?: boolean;
};

export function ErrorState({ message, compact = false }: ErrorStateProps) {
  return (
    <div className={compact ? styles.compactError : styles.panel} role="alert">
      <span className={styles.errorDot} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

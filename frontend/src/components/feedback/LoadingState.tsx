import styles from "./feedback.module.css";

type LoadingStateProps = {
  label?: string;
  compact?: boolean;
};

export function LoadingState({ label = "Loading", compact = false }: LoadingStateProps) {
  return (
    <div className={compact ? styles.compact : styles.panel} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

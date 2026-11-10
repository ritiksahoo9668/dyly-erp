import type { ReactNode } from "react";
import styles from "./KpiCard.module.css";

type KpiCardProps = {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
};

export function KpiCard({ label, value, detail, icon }: KpiCardProps) {
  return (
    <article className={styles.card}>
      <div className={styles.heading}>
        <h2>{label}</h2>
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      </div>
      <p className={styles.value}>{value}</p>
      <p className={styles.detail}>{detail}</p>
    </article>
  );
}

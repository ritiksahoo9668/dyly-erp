import type { NameMasterRecord } from "@/types/nameMaster";
import styles from "./CompanyUnits.module.css";

type CompanyUnitSummary = { id: number; name: string; is_active: boolean };

export function CompanyUnitsCell({ company }: { company: NameMasterRecord }) {
  const units = (company as NameMasterRecord & { units?: CompanyUnitSummary[] }).units ?? [];
  if (units.length === 0) return <span className={styles.muted}>No units</span>;
  return (
    <span className={styles.chips}>
      {units.map((unit) => (
        <span
          key={unit.id}
          className={`${styles.chip} ${unit.is_active ? "" : styles.chipInactive}`}
          title={unit.is_active ? unit.name : `${unit.name} (Inactive)`}
        >
          {unit.name}
        </span>
      ))}
    </span>
  );
}

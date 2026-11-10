import { skipToken } from "@reduxjs/toolkit/query";
import { useGetUnitsQuery } from "@/app/store/api";
import type { NameMasterRecord } from "@/types/nameMaster";
import styles from "./CompanyUnits.module.css";
import { UnitNamesInput } from "./UnitNamesInput";

type Props = {
  company: NameMasterRecord | null;
  onChange: (names: string[]) => void;
};

/** Units section of the Add/Edit Company form. Units are saved as Unit records linked to the Company. */
export function CompanyFormUnits({ company, onChange }: Props) {
  const { data } = useGetUnitsQuery(company ? { lookup: true, company: company.id, page_size: 500 } : skipToken);
  const existing = data?.results ?? [];
  const canAdd = !company || company.is_active;

  return (
    <div className={styles.formSection}>
      <div className={styles.header}>
        <label className={styles.title} htmlFor="company-unit-names">
          Units
        </label>
        {company ? <span className={styles.count}>{existing.length}</span> : null}
      </div>
      {existing.length > 0 ? (
        <div className={styles.chips}>
          {existing.map((unit) => (
            <span
              key={unit.id}
              className={`${styles.chip} ${unit.is_active ? "" : styles.chipInactive}`}
              title={unit.is_active ? undefined : "Inactive"}
            >
              {unit.name}
            </span>
          ))}
        </div>
      ) : null}
      {canAdd ? (
        <>
          <UnitNamesInput
            id="company-unit-names"
            existingNames={existing.map((unit) => unit.name)}
            onChange={onChange}
          />
          <p className={styles.muted}>Optional. Add one or more units for this company.</p>
        </>
      ) : (
        <p className={styles.muted}>Activate this company to add units.</p>
      )}
    </div>
  );
}

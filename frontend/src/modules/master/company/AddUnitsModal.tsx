import { type FormEvent, useCallback, useRef, useState } from "react";
import { useCreateUnitMutation, useGetUnitsQuery } from "@/app/store/api";
import { CloseIcon } from "@/components/navigation/icons";
import shared from "@/modules/master/shared/NameMasterPage.module.css";
import type { NameMasterRecord } from "@/types/nameMaster";
import styles from "./CompanyUnits.module.css";
import { createCompanyUnits } from "./createCompanyUnits";
import { UnitNamesInput } from "./UnitNamesInput";

type Props = {
  company: NameMasterRecord;
  onClose: () => void;
};

export function AddUnitsModal({ company, onClose }: Props) {
  const { data } = useGetUnitsQuery({ lookup: true, company: company.id, page_size: 500 });
  const [createUnit] = useCreateUnitMutation();
  const existing = data?.results ?? [];
  const namesRef = useRef<string[]>([]);
  const [inputKey, setInputKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const onNamesChange = useCallback((names: string[]) => {
    namesRef.current = names;
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const names = namesRef.current;
    if (!names.length) {
      setFormError("Enter at least one Unit Name.");
      return;
    }
    setSaving(true);
    setFormError(null);
    const error = await createCompanyUnits(createUnit, company.id, names);
    setSaving(false);
    if (error) {
      setFormError(error);
      setInputKey((value) => value + 1);
      return;
    }
    onClose();
  }

  return (
    <>
      <button
        type="button"
        className={shared.backdrop}
        aria-label="Close"
        onClick={() => !saving && onClose()}
      />
      <div className={shared.modal} role="dialog" aria-modal="true" aria-labelledby="add-units-title">
        <div className={shared.modalHeader}>
          <div>
            <h2 id="add-units-title">Add Unit</h2>
            <p>
              Units will be added under <strong>{company.name}</strong>.
            </p>
          </div>
          <button
            type="button"
            className={shared.closeBtn}
            aria-label="Close"
            disabled={saving}
            onClick={onClose}
          >
            <CloseIcon />
          </button>
        </div>
        <form className={shared.form} onSubmit={onSubmit}>
          {formError ? <p className={shared.formError}>{formError}</p> : null}
          {existing.length > 0 ? (
            <div className={styles.formSection}>
              <div className={styles.header}>
                <span className={styles.title}>Existing Units</span>
                <span className={styles.count}>{existing.length}</span>
              </div>
              <div className={styles.chips}>
                {existing.map((unit) => (
                  <span
                    key={unit.id}
                    className={`${styles.chip} ${unit.is_active ? "" : styles.chipInactive}`}
                  >
                    {unit.name}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          <div className={shared.field}>
            <label htmlFor="add-unit-names">Unit Name *</label>
            <UnitNamesInput
              key={inputKey}
              id="add-unit-names"
              existingNames={existing.map((unit) => unit.name)}
              onChange={onNamesChange}
              disabled={saving}
              autoFocus
            />
          </div>
          <div className={shared.formActions}>
            <button type="button" className={shared.secondaryBtn} disabled={saving} onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className={shared.primaryBtn} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </>
  );
}

import { type ClipboardEvent, type KeyboardEvent, useEffect, useState } from "react";
import styles from "./CompanyUnits.module.css";

const MAX_LENGTH = 150;

function normalize(value: string) {
  return value.trim().toLowerCase();
}

type Props = {
  id: string;
  existingNames: string[];
  onChange: (names: string[]) => void;
  disabled?: boolean;
  autoFocus?: boolean;
};

/**
 * Collects one or more Unit names. Names are added with Enter, comma or the Add button;
 * pasting multiple lines adds each line. Text still in the box counts as a pending name.
 */
export function UnitNamesInput({ id, existingNames, onChange, disabled, autoFocus }: Props) {
  const [names, setNames] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const pending = draft.trim();
    onChange(pending ? [...names, pending] : names);
  }, [names, draft, onChange]);

  function addNames(values: string[]) {
    const taken = new Set([...existingNames, ...names].map(normalize));
    const accepted: string[] = [];
    const problems: string[] = [];
    for (const raw of values) {
      const cleaned = raw.trim();
      if (!cleaned) continue;
      if (cleaned.length > MAX_LENGTH) {
        problems.push(`"${cleaned.slice(0, 30)}…" is longer than ${MAX_LENGTH} characters.`);
      } else if (taken.has(normalize(cleaned))) {
        problems.push(`"${cleaned}" already exists in this company.`);
      } else {
        taken.add(normalize(cleaned));
        accepted.push(cleaned);
      }
    }
    if (accepted.length) setNames((current) => [...current, ...accepted]);
    setError(problems.length ? problems.join(" ") : null);
    return problems.length === 0;
  }

  function commitDraft() {
    if (!draft.trim()) return;
    if (addNames([draft])) setDraft("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commitDraft();
    } else if (event.key === "Backspace" && !draft && names.length) {
      setNames((current) => current.slice(0, -1));
    }
  }

  function onPaste(event: ClipboardEvent<HTMLInputElement>) {
    const text = event.clipboardData.getData("text");
    if (!/[\n,]/.test(text)) return;
    event.preventDefault();
    addNames(text.split(/[\n,]/));
  }

  return (
    <div className={styles.namesField}>
      {names.length > 0 ? (
        <div className={styles.chips}>
          {names.map((unitName) => (
            <span key={unitName} className={styles.chip}>
              {unitName}
              <button
                type="button"
                className={styles.chipRemove}
                aria-label={`Remove ${unitName}`}
                disabled={disabled}
                onClick={() =>
                  setNames((current) => current.filter((value) => value !== unitName))
                }
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
      <div className={styles.inputRow}>
        <input
          id={id}
          className={styles.input}
          value={draft}
          placeholder="Type a unit name and press Enter"
          maxLength={MAX_LENGTH}
          disabled={disabled}
          autoFocus={autoFocus}
          onChange={(event) => {
            setDraft(event.target.value);
            setError(null);
          }}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
        />
        <button
          type="button"
          className={styles.addBtn}
          disabled={disabled || !draft.trim()}
          onClick={commitDraft}
        >
          Add
        </button>
      </div>
      {error ? <p className={styles.error}>{error}</p> : null}
    </div>
  );
}

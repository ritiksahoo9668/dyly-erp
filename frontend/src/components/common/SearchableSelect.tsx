import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import styles from "./SearchableSelect.module.css";

export type SearchableSelectOption = {
  value: number;
  label: string;
  hint?: string;
};

type SearchableSelectProps = {
  id?: string;
  value: number | "";
  options: SearchableSelectOption[];
  onChange: (value: number | "") => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  disabled?: boolean;
  invalid?: boolean;
  /** Shows a "Clear selection" action for optional fields. */
  clearable?: boolean;
};

export function SearchableSelect({
  id,
  value,
  options,
  onChange,
  placeholder = "Select",
  searchPlaceholder = "Search…",
  emptyText = "No matches found.",
  disabled = false,
  invalid = false,
  clearable = false,
}: SearchableSelectProps) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);

  const selected = options.find((option) => option.value === value) ?? null;

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((option) => option.label.toLowerCase().includes(needle));
  }, [options, query]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  function openMenu() {
    setQuery("");
    const index = options.findIndex((option) => option.value === value);
    setHighlight(index >= 0 ? index : 0);
    setOpen(true);
    window.requestAnimationFrame(() => searchRef.current?.focus());
  }

  useEffect(() => {
    if (!open) return;
    const item = listRef.current?.children[highlight] as HTMLElement | undefined;
    item?.scrollIntoView({ block: "nearest" });
  }, [highlight, open]);

  function choose(option: SearchableSelectOption) {
    onChange(option.value);
    setOpen(false);
  }

  function onSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlight((current) => Math.min(current + 1, Math.max(filtered.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlight((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const option = filtered[highlight];
      if (option) choose(option);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        id={id}
        type="button"
        className={`${styles.trigger} ${open ? styles.triggerOpen : ""} ${
          invalid ? styles.triggerInvalid : ""
        }`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : openMenu())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" && !open) {
            event.preventDefault();
            openMenu();
          }
        }}
      >
        <span className={selected ? styles.value : styles.placeholder}>
          {selected ? selected.label : placeholder}
        </span>
        <span className={styles.chevron} aria-hidden="true" />
      </button>

      {open ? (
        <div className={styles.panel}>
          <input
            ref={searchRef}
            className={styles.search}
            type="text"
            value={query}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            aria-controls={listId}
            onChange={(event) => {
              setQuery(event.target.value);
              setHighlight(0);
            }}
            onKeyDown={onSearchKeyDown}
          />
          {clearable && value !== "" ? (
            <button
              type="button"
              className={styles.clear}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              Clear selection
            </button>
          ) : null}
          {filtered.length === 0 ? (
            <p className={styles.empty}>{emptyText}</p>
          ) : (
            <ul id={listId} ref={listRef} className={styles.list} role="listbox">
              {filtered.map((option, index) => (
                <li
                  key={option.value}
                  role="option"
                  aria-selected={option.value === value}
                  className={`${styles.option} ${index === highlight ? styles.optionActive : ""} ${
                    option.value === value ? styles.optionSelected : ""
                  }`}
                  onMouseEnter={() => setHighlight(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(option)}
                >
                  <span>{option.label}</span>
                  {option.hint ? <span className={styles.hint}>{option.hint}</span> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

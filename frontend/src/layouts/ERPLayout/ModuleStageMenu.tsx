import { type ComponentType, type ReactNode, useMemo, useState } from "react";
import { ChevronRightIcon, CloseIcon, SearchIcon } from "@/components/navigation/icons";
import type { ModuleStage, StageAccent } from "@/types/navigation";
import styles from "./ERPLayout.module.css";

const accentClass: Record<StageAccent, string> = {
  blue: styles.accentBlue,
  green: styles.accentGreen,
  purple: styles.accentPurple,
  orange: styles.accentOrange,
  teal: styles.accentTeal,
  indigo: styles.accentIndigo,
  red: styles.accentRed,
  amber: styles.accentAmber,
};

type StageIcon = ComponentType<{ size?: number }>;

type ModuleStageMenuProps = {
  title: string;
  subtitle?: string;
  badgeIcon: ReactNode;
  stages: ModuleStage[];
  icons: Record<string, StageIcon>;
  onClose: () => void;
  onSelect?: (stage: ModuleStage) => void;
  /** Shows a search box that filters stages by label and description. */
  searchable?: boolean;
  searchPlaceholder?: string;
};

/**
 * Shared submodule popup template used by Procurement, Production, and future modules.
 */
export function ModuleStageMenu({
  title,
  subtitle = "Select a stage to continue",
  badgeIcon,
  stages,
  icons,
  onClose,
  onSelect,
  searchable = false,
  searchPlaceholder,
}: ModuleStageMenuProps) {
  const [query, setQuery] = useState("");

  const visibleStages = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!searchable || !needle) return stages;
    return stages.filter((stage) =>
      `${stage.label} ${stage.description}`.toLowerCase().includes(needle),
    );
  }, [stages, query, searchable]);

  function selectStage(stage: ModuleStage) {
    if (onSelect && stage.to) onSelect(stage);
  }

  return (
    <section className={styles.menu} aria-label={`${title} modules`} role="dialog" aria-modal="true">
      <header className={styles.menuHeader}>
        <div className={styles.menuTitle}>
          <span className={`${styles.menuBadge} ${styles.accentBlue}`} aria-hidden="true">
            {badgeIcon}
          </span>
          <span>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </span>
        </div>
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
          <CloseIcon />
        </button>
      </header>
      {searchable ? (
        <div className={styles.stageSearch}>
          <SearchIcon />
          <input
            type="search"
            value={query}
            placeholder={searchPlaceholder ?? `Search ${title.toLowerCase()}...`}
            aria-label={`Search ${title} modules`}
            autoFocus
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                const first = visibleStages.find((stage) => stage.to);
                if (first) selectStage(first);
              }
            }}
          />
          {query ? (
            <button
              type="button"
              className={styles.stageSearchClear}
              aria-label="Clear search"
              onClick={() => setQuery("")}
            >
              <CloseIcon />
            </button>
          ) : null}
        </div>
      ) : null}
      <div className={styles.menuBody}>
        {visibleStages.length === 0 ? (
          <p className={styles.stageEmpty}>No matches for &quot;{query.trim()}&quot;.</p>
        ) : (
          <div className={styles.stageGrid}>
            {visibleStages.map((stage) => {
              const Icon = icons[stage.id];
              return (
                <button
                  key={stage.id}
                  type="button"
                  className={styles.stage}
                  title={stage.to ? undefined : "Available in a later phase"}
                  onClick={(event) => {
                    if (!onSelect || !stage.to) {
                      event.preventDefault();
                      return;
                    }
                    onSelect(stage);
                  }}
                >
                  <span
                    className={`${styles.stageIcon} ${accentClass[stage.accent]}`}
                    aria-hidden="true"
                  >
                    {Icon ? <Icon /> : null}
                  </span>
                  <span className={styles.stageCopy}>
                    <strong>{stage.label}</strong>
                    <span>{stage.description}</span>
                  </span>
                  <ChevronRightIcon />
                </button>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

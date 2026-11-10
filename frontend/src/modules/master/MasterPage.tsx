import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useGetMasterSummaryQuery } from "@/app/store/api";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import { ChevronRightIcon, MasterIcon, SearchIcon } from "@/components/navigation/icons";
import { visibleMasterStages } from "@/config/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import type { MasterCount, MasterRecentImport } from "@/types/masterSummary";
import type { ModuleStage, StageAccent } from "@/types/navigation";
import { masterStageIcons } from "./masterStageIcons";
import styles from "./MasterPage.module.css";

type MasterGroup = {
  id: string;
  title: string;
  description: string;
  stageIds: string[];
};

const MASTER_GROUPS: MasterGroup[] = [
  {
    id: "organization",
    title: "Organization",
    description: "Company structure and business units.",
    stageIds: ["company", "unit", "division", "vertical", "facility"],
  },
  {
    id: "people",
    title: "People",
    description: "Employees and their roles.",
    stageIds: ["employee", "department", "designation", "user-onboarding"],
  },
  {
    id: "materials",
    title: "Materials",
    description: "Items, classification and units of measure.",
    stageIds: [
      "material-item",
      "material-category",
      "material-sub-category",
      "material-group",
      "material-type",
      "uom",
    ],
  },
  {
    id: "procurement",
    title: "Procurement & Logistics",
    description: "SAP mappings, suppliers and yard operations.",
    stageIds: ["purchasing-group", "plant", "vendor", "stock-yard", "weighbridge"],
  },
  {
    id: "quality",
    title: "Quality",
    description: "Quality check definitions.",
    stageIds: ["qc-parameter"],
  },
];

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

const IMPORT_STATUS: Record<string, { label: string; className: string }> = {
  COMPLETED: { label: "Completed", className: styles.statusDone },
  COMPLETED_WITH_ERRORS: { label: "With errors", className: styles.statusWarn },
  FAILED: { label: "Failed", className: styles.statusFailed },
};

const numberFormat = new Intl.NumberFormat("en-IN");

function timeAgo(value: string) {
  const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
  if (Number.isNaN(seconds)) return "";
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

function groupStages(stages: ModuleStage[]) {
  const byId = new Map(stages.map((stage) => [stage.id, stage]));
  const used = new Set<string>();
  const groups = MASTER_GROUPS.map((group) => {
    const items = group.stageIds.flatMap((id) => {
      const stage = byId.get(id);
      if (!stage) return [];
      used.add(id);
      return [stage];
    });
    return { ...group, items };
  });
  const others = stages.filter((stage) => !used.has(stage.id));
  if (others.length) {
    groups.push({
      id: "other",
      title: "Other",
      description: "Additional masters.",
      stageIds: others.map((stage) => stage.id),
      items: others,
    });
  }
  return groups;
}

function MasterCard({
  stage,
  count,
  loading,
}: {
  stage: ModuleStage;
  count: MasterCount | undefined;
  loading: boolean;
}) {
  const Icon = masterStageIcons[stage.id];
  const inactive = count ? count.total - count.active : 0;
  const body = (
    <>
      <span className={`${styles.cardIcon} ${accentClass[stage.accent]}`} aria-hidden="true">
        {Icon ? <Icon /> : null}
      </span>
      <span className={styles.cardCopy}>
        <strong>{stage.label}</strong>
        <small>{stage.description}</small>
      </span>
      <span className={styles.cardFoot}>
        {!stage.to ? (
          <span className={`${styles.chip} ${styles.chipSoon}`}>Coming soon</span>
        ) : loading ? (
          <span className={styles.skeleton} />
        ) : count ? (
          <>
            <span className={styles.cardCount}>
              <b>{numberFormat.format(count.total)}</b> {count.total === 1 ? "record" : "records"}
            </span>
            {count.total === 0 ? (
              <span className={`${styles.chip} ${styles.chipEmpty}`}>Empty</span>
            ) : inactive > 0 ? (
              <span className={`${styles.chip} ${styles.chipInactive}`}>
                {numberFormat.format(inactive)} inactive
              </span>
            ) : (
              <span className={`${styles.chip} ${styles.chipActive}`}>All active</span>
            )}
          </>
        ) : (
          <span className={styles.cardCount}>Open master</span>
        )}
      </span>
      {stage.to ? (
        <span className={styles.cardArrow} aria-hidden="true">
          <ChevronRightIcon />
        </span>
      ) : null}
    </>
  );

  if (!stage.to) {
    return (
      <div className={`${styles.card} ${styles.cardDisabled}`} aria-disabled="true">
        {body}
      </div>
    );
  }
  return (
    <Link to={stage.to} className={styles.card}>
      {body}
    </Link>
  );
}

function RecentImport({ item }: { item: MasterRecentImport }) {
  const status = IMPORT_STATUS[item.status] ?? {
    label: "Running",
    className: styles.statusRunning,
  };
  const parts = [
    `${numberFormat.format(item.created_rows)} created`,
    item.skipped_rows ? `${numberFormat.format(item.skipped_rows)} skipped` : null,
    item.failed_rows ? `${numberFormat.format(item.failed_rows)} failed` : null,
  ].filter(Boolean);

  return (
    <li className={styles.importItem}>
      <div className={styles.importHead}>
        <strong>{item.master_label}</strong>
        <span className={`${styles.status} ${status.className}`}>{status.label}</span>
      </div>
      {item.original_filename ? (
        <span className={styles.importFile} title={item.original_filename}>
          {item.original_filename}
        </span>
      ) : null}
      <span className={styles.importMeta}>
        {parts.join(" · ")}
        <span aria-hidden="true"> · </span>
        {timeAgo(item.created_at)}
        {item.uploaded_by ? ` · ${item.uploaded_by}` : ""}
      </span>
    </li>
  );
}

export function MasterPage() {
  useDocumentTitle("Master");
  const [query, setQuery] = useState("");
  const { data, isLoading, isError, refetch } = useGetMasterSummaryQuery(undefined, {
    refetchOnMountOrArgChange: true,
  });

  const user = useAppSelector(selectAuthUser);
  const stages = useMemo(() => visibleMasterStages(user), [user]);
  const groups = useMemo(() => groupStages(stages), [stages]);
  const term = query.trim().toLowerCase();
  const visibleGroups = useMemo(
    () =>
      groups
        .map((group) => ({
          ...group,
          items: term
            ? group.items.filter((stage) =>
                `${stage.label} ${stage.description} ${group.title}`.toLowerCase().includes(term),
              )
            : group.items,
        }))
        .filter((group) => group.items.length > 0),
    [groups, term],
  );

  const totals = useMemo(() => {
    const counts = Object.values(data?.masters ?? {});
    const total = counts.reduce((sum, item) => sum + item.total, 0);
    const active = counts.reduce((sum, item) => sum + item.active, 0);
    return { total, active, inactive: total - active };
  }, [data]);
  const liveMasters = stages.filter((stage) => stage.to).length;

  const kpis = [
    {
      id: "masters",
      label: "Masters",
      value: numberFormat.format(liveMasters),
      hint: "Available to manage",
      accent: styles.accentBlue,
    },
    {
      id: "records",
      label: "Total Records",
      value: data ? numberFormat.format(totals.total) : "—",
      hint: "Across all masters",
      accent: styles.accentIndigo,
    },
    {
      id: "active",
      label: "Active",
      value: data ? numberFormat.format(totals.active) : "—",
      hint: "Available for use",
      accent: styles.accentGreen,
    },
    {
      id: "inactive",
      label: "Inactive",
      value: data ? numberFormat.format(totals.inactive) : "—",
      hint: "Hidden from selection",
      accent: styles.accentAmber,
    },
  ];

  return (
    <PageContainer>
      <section className={styles.hero}>
        <div className={styles.heroTitle}>
          <span className={styles.heroBadge} aria-hidden="true">
            <MasterIcon size={20} />
          </span>
          <div>
            <h1>Master</h1>
            <p>Reference data shared across Procurement, Production, Sales and HR.</p>
          </div>
        </div>
        <label className={styles.search}>
          <SearchIcon />
          <input
            type="search"
            placeholder="Find a master..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Find a master"
          />
        </label>
      </section>

      <section className={styles.kpis} aria-label="Master data summary">
        {kpis.map((kpi) => (
          <article key={kpi.id} className={styles.kpi}>
            <span className={`${styles.kpiDot} ${kpi.accent}`} aria-hidden="true" />
            <div>
              <p className={styles.kpiLabel}>{kpi.label}</p>
              <p className={styles.kpiValue}>
                {isLoading && kpi.id !== "masters" ? (
                  <span className={styles.skeleton} />
                ) : (
                  kpi.value
                )}
              </p>
              <p className={styles.kpiHint}>{kpi.hint}</p>
            </div>
          </article>
        ))}
      </section>

      {isError ? (
        <p className={styles.notice}>
          Record counts are unavailable right now.{" "}
          <button type="button" onClick={() => refetch()}>
            Retry
          </button>
        </p>
      ) : null}

      <div className={styles.layout}>
        <div className={styles.groups}>
          {visibleGroups.length === 0 ? (
            <p className={styles.empty}>No masters match &quot;{query.trim()}&quot;.</p>
          ) : null}
          {visibleGroups.map((group) => (
            <section key={group.id} className={styles.group} aria-labelledby={`group-${group.id}`}>
              <header className={styles.groupHead}>
                <div>
                  <h2 id={`group-${group.id}`}>{group.title}</h2>
                  <p>{group.description}</p>
                </div>
                <span className={styles.groupCount}>
                  {group.items.length} {group.items.length === 1 ? "master" : "masters"}
                </span>
              </header>
              <div className={styles.cards}>
                {group.items.map((stage) => (
                  <MasterCard
                    key={stage.id}
                    stage={stage}
                    count={data?.masters[stage.id]}
                    loading={isLoading}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>

        <aside className={styles.panel} aria-labelledby="recent-imports">
          <header className={styles.panelHead}>
            <h2 id="recent-imports">Recent Excel Imports</h2>
            <p>Latest uploads across all masters.</p>
          </header>
          {isLoading ? (
            <ul className={styles.importList}>
              {[0, 1, 2].map((index) => (
                <li key={index} className={styles.importItem}>
                  <span className={styles.skeleton} />
                  <span className={`${styles.skeleton} ${styles.skeletonWide}`} />
                </li>
              ))}
            </ul>
          ) : data && data.recent_imports.length ? (
            <ul className={styles.importList}>
              {data.recent_imports.map((item) => (
                <RecentImport key={item.id} item={item} />
              ))}
            </ul>
          ) : (
            <p className={styles.panelEmpty}>
              No Excel imports yet. Use Upload Excel on any master page.
            </p>
          )}
        </aside>
      </div>
    </PageContainer>
  );
}

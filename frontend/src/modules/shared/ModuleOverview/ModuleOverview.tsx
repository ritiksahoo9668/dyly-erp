import { PageContainer } from "@/components/common/PageContainer";
import { ChevronDownIcon, EyeIcon, PlusIcon, SalesIcon } from "@/components/navigation/icons";
import styles from "./ModuleOverview.module.css";
import type { ModuleOverviewConfig, TrendTone } from "./types";

function Sparkline({ values, tone }: { values: number[]; tone: TrendTone }) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 48;
      const y = 14 - ((value - min) / (max - min || 1)) * 10;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg className={styles.spark} viewBox="0 0 48 16" aria-hidden="true">
      <polyline
        fill="none"
        stroke={tone === "up" ? "#16a34a" : "#ef4444"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l2.5 1.5" />
    </svg>
  );
}

type ModuleOverviewProps = {
  config: ModuleOverviewConfig;
};

/**
 * Shared ERP module/submodule overview template.
 * Every module and submodule should reuse this shell and supply its own config.
 */
export function ModuleOverview({ config }: ModuleOverviewProps) {
  const maxTrend = Math.max(...config.trend.map((item) => item.value), 1);

  return (
    <PageContainer>
      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.heroTitleRow}>
            <span className={styles.heroBadge} aria-hidden="true">
              {config.badgeIcon}
            </span>
            <div>
              <h1>{config.title}</h1>
              <p>{config.description}</p>
            </div>
          </div>
          <div className={styles.heroActions}>
            {config.actions.map((action) => (
              <button
                key={action.id}
                type="button"
                className={action.primary ? styles.actionPrimary : styles.actionSecondary}
              >
                {action.primary ? <PlusIcon /> : action.icon}
                {action.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.kpis}>
        {config.kpis.map((kpi) => (
          <article key={kpi.id} className={styles.kpiCard}>
            <div className={styles.kpiHead}>
              <span className={`${styles.kpiIcon} ${styles[kpi.accent]}`}>{kpi.icon}</span>
              <Sparkline values={kpi.spark} tone={kpi.tone} />
            </div>
            <p className={styles.kpiLabel}>{kpi.label}</p>
            <div className={styles.kpiFoot}>
              <p className={styles.kpiValue}>{kpi.value}</p>
              <p className={kpi.tone === "up" ? styles.trendUp : styles.trendDown}>
                {kpi.tone === "up" ? "↑" : "↓"} {kpi.trend}
              </p>
            </div>
          </article>
        ))}
      </section>

      <section className={styles.grid}>
        <article className={styles.panel}>
          <header className={styles.panelHead}>
            <div className={styles.panelTitle}>
              <span className={styles.panelIcon} aria-hidden="true">
                <ClockIcon />
              </span>
              <h2>{config.activitiesTitle}</h2>
            </div>
            <button type="button" className={styles.linkButton}>
              View All →
            </button>
          </header>
          <div className={styles.table}>
            <div className={styles.tableHead}>
              <span>#</span>
              <span>Activity</span>
              <span>Module</span>
              <span>Time</span>
              <span>Status</span>
              <span>Action</span>
            </div>
            {config.activities.map((item, index) => (
              <div key={item.id} className={styles.tableRow}>
                <span className={styles.muted}>{index + 1}</span>
                <span>
                  <strong>{item.code}</strong>
                  <small>{item.label}</small>
                </span>
                <span className={`${styles.tag} ${styles[item.moduleTone]}`}>{item.module}</span>
                <span className={styles.muted}>{item.time}</span>
                <span className={`${styles.status} ${styles[item.statusTone]}`}>{item.status}</span>
                <button type="button" className={styles.viewButton} aria-label={`View ${item.code}`}>
                  <EyeIcon />
                </button>
              </div>
            ))}
          </div>
        </article>

        <article className={styles.panel}>
          <header className={styles.panelHead}>
            <div className={styles.panelTitle}>
              <span className={styles.panelIcon} aria-hidden="true">
                <SalesIcon />
              </span>
              <h2>{config.trendTitle}</h2>
            </div>
            <button type="button" className={styles.rangeButton}>
              {config.trendRangeLabel ?? "Last 6 Months"}
              <ChevronDownIcon />
            </button>
          </header>
          <div className={styles.bars}>
            {config.trend.map((item) => (
              <div key={item.month} className={styles.barItem}>
                <div className={styles.barTrack}>
                  <div
                    className={styles.barFill}
                    style={{ height: `${(item.value / maxTrend) * 100}%` }}
                    title={`${item.month}: ${item.value}`}
                  />
                </div>
                <span>{item.month}</span>
              </div>
            ))}
          </div>
          <div className={styles.trendSummary}>
            {config.trendSummary.map((item) => (
              <div key={item.id} className={styles.summaryItem}>
                <small>{item.label}</small>
                <strong>{item.value}</strong>
                <span className={item.tone === "up" ? styles.trendUp : styles.trendDown}>
                  {item.tone === "up" ? "↑" : "↓"} {item.trend}
                </span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </PageContainer>
  );
}

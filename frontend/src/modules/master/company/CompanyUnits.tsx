import { Link } from "react-router-dom";
import { useGetUnitsQuery } from "@/app/store/api";
import styles from "./CompanyUnits.module.css";

export function CompanyUnits({ companyId }: { companyId: number }) {
  const { data, isLoading, isFetching, isError, refetch } = useGetUnitsQuery({
    lookup: true,
    company: companyId,
    page_size: 500,
  });
  const units = data?.results ?? [];
  const count = data?.count ?? 0;

  return (
    <section className={styles.section} aria-label="Associated Units">
      <div className={styles.header}>
        <span className={styles.title}>Associated Units</span>
        {data ? <span className={styles.count}>{count}</span> : null}
        {isFetching && data ? <span className={styles.muted}>Refreshing…</span> : null}
      </div>

      {isLoading ? <p className={styles.muted}>Loading units…</p> : null}
      {isError ? (
        <p className={styles.error}>
          Unable to load units.{" "}
          <button type="button" className={styles.linkBtn} onClick={() => refetch()}>
            Retry
          </button>
        </p>
      ) : null}
      {data && units.length === 0 ? (
        <p className={styles.muted}>
          No units linked to this company yet. <Link to="/master/unit">Add one in Unit Master</Link>.
        </p>
      ) : null}
      {units.length > 0 ? (
        <ul className={styles.list}>
          {units.map((unit) => (
            <li key={unit.id} className={styles.item}>
              <span>{unit.name}</span>
              {unit.is_active ? null : <span className={styles.inactive}>Inactive</span>}
            </li>
          ))}
        </ul>
      ) : null}
      {count > units.length ? (
        <p className={styles.muted}>
          Showing {units.length} of {count}. See Unit Master for the full list.
        </p>
      ) : null}
    </section>
  );
}

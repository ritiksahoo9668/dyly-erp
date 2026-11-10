import { useGetHealthQuery } from "@/services";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import styles from "./ServiceStatus.module.css";

export function ServiceStatus() {
  const { data, isLoading, isError } = useGetHealthQuery();

  if (isLoading) {
    return <LoadingState compact label="Checking services" />;
  }

  if (isError || !data || data.status !== "ok") {
    return <ErrorState compact message="Services unavailable" />;
  }

  return (
    <span className={styles.online}>
      <span className={styles.dot} aria-hidden="true" />
      Services online
    </span>
  );
}

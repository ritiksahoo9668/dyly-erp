import type { ReactNode } from "react";
import styles from "./PageContainer.module.css";

type PageContainerProps = {
  children: ReactNode;
};

export function PageContainer({ children }: PageContainerProps) {
  return <section className={styles.container}>{children}</section>;
}

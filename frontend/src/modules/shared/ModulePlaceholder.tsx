import { PageContainer } from "@/components/common/PageContainer";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import styles from "./ModulePlaceholder.module.css";

type ModulePlaceholderProps = {
  title: string;
};

export function ModulePlaceholder({ title }: ModulePlaceholderProps) {
  useDocumentTitle(title);

  return (
    <PageContainer>
      <article className={styles.card} aria-label={title} />
    </PageContainer>
  );
}

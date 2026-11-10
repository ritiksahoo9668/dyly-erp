import { Link } from "react-router-dom";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { PageContainer } from "@/components/common/PageContainer";
import { homePath } from "@/config/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import styles from "./AccessDenied.module.css";

/** 403 page for routes outside the signed-in user's module access. */
export function AccessDenied() {
  useDocumentTitle("Access denied");
  const home = homePath(useAppSelector(selectAuthUser));

  return (
    <PageContainer>
      <section className={styles.card} role="alert" aria-labelledby="access-denied-title">
        <span className={styles.code}>403</span>
        <h1 id="access-denied-title">Access denied</h1>
        <p>
          You do not have access to this page. Ask your ERP administrator if you need it for your
          work.
        </p>
        {home ? (
          <Link to={home} className={styles.action}>
            Go to my home page
          </Link>
        ) : (
          <p className={styles.hint}>No modules are assigned to your account yet.</p>
        )}
      </section>
    </PageContainer>
  );
}

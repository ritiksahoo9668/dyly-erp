import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  BoltIcon,
  ChartBarsIcon,
  DylyLogo,
  ShieldCheckIcon,
  TeamIcon,
} from "@/components/navigation/icons";
import { appConfig } from "@/config/app";
import styles from "./AuthShell.module.css";

const FEATURES = [
  {
    title: "Integrated Operations",
    description: "All your business processes in one place",
    icon: <ChartBarsIcon size={18} />,
    tone: "blue" as const,
  },
  {
    title: "Secure & Reliable",
    description: "Enterprise-grade security for your data",
    icon: <ShieldCheckIcon size={18} />,
    tone: "green" as const,
  },
  {
    title: "Team Collaboration",
    description: "Work together, stay informed",
    icon: <TeamIcon size={18} />,
    tone: "orange" as const,
  },
  {
    title: "Real-time Insights",
    description: "Make faster, better decisions",
    icon: <BoltIcon size={18} />,
    tone: "purple" as const,
  },
];

export function AuthShell() {
  return (
    <div className={styles.shell}>
      <div className={styles.blobLeft} aria-hidden="true" />
      <div className={styles.blobRight} aria-hidden="true" />

      <div className={styles.layout}>
        <aside className={styles.marketing}>
          <div className={styles.brand}>
            <DylyLogo size={48} />
            <div>
              <strong>{appConfig.productName}</strong>
              <p>Secure access for your operations team</p>
            </div>
          </div>

          <div className={styles.pitch}>
            <h1>Simplify. Manage. Grow.</h1>
            <p>
              A unified ERP platform to streamline your procurement, production, sales, projects and
              operations.
            </p>
          </div>

          <ul className={styles.features}>
            {FEATURES.map((feature) => (
              <li key={feature.title} className={styles.feature}>
                <span className={`${styles.featureIcon} ${styles[feature.tone]}`} aria-hidden="true">
                  {feature.icon}
                </span>
                <div>
                  <strong>{feature.title}</strong>
                  <p>{feature.description}</p>
                </div>
              </li>
            ))}
          </ul>
        </aside>

        <section className={styles.stage}>
          <div className={styles.card}>
            <Outlet />
          </div>
        </section>
      </div>
    </div>
  );
}

type AuthCardFooterProps = {
  supportHref?: string;
};

export function AuthCardFooter({ supportHref = "mailto:support@demil.in" }: AuthCardFooterProps) {
  return (
    <div className={styles.cardFooter}>
      <div className={styles.orDivider} role="separator">
        <span>OR</span>
      </div>
      <div className={styles.footerLinks}>
        <NavLink to="/login" className={({ isActive }) => (isActive ? styles.footerActive : undefined)}>
          Sign in
        </NavLink>
        <span aria-hidden="true">|</span>
        <a href={supportHref}>Contact support</a>
      </div>
    </div>
  );
}

export function AuthField({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.field}>
      <label htmlFor={id}>{label}</label>
      {children}
    </div>
  );
}

import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import styles from "./NavItem.module.css";

type NavItemProps = {
  to: string;
  label: string;
  icon: ReactNode;
  onNavigate?: () => void;
};

export function NavItem({ to, label, icon, onNavigate }: NavItemProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => (isActive ? `${styles.link} ${styles.active}` : styles.link)}
      onClick={onNavigate}
    >
      <span className={styles.icon} aria-hidden="true">
        {icon}
      </span>
      <span className={styles.label}>{label}</span>
    </NavLink>
  );
}

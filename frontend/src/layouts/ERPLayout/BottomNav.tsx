import { useLocation, useNavigate } from "react-router-dom";
import { NavItem } from "@/components/navigation/NavItem";
import {
  DashboardIcon,
  HrIcon,
  MasterIcon,
  MoreIcon,
  ProcurementIcon,
  ProductionIcon,
  SalesIcon,
} from "@/components/navigation/icons";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { visibleNavigation } from "@/config/navigation";
import styles from "./ERPLayout.module.css";

const icons = {
  dashboard: DashboardIcon,
  procurement: ProcurementIcon,
  production: ProductionIcon,
  sales: SalesIcon,
  hr: HrIcon,
  master: MasterIcon,
} as const;

type BottomNavProps = {
  procurementOpen: boolean;
  productionOpen: boolean;
  salesOpen: boolean;
  masterOpen: boolean;
  moreOpen: boolean;
  onToggleProcurement: () => void;
  onToggleProduction: () => void;
  onToggleSales: () => void;
  onToggleMaster: () => void;
  onToggleMore: () => void;
  onNavigate: () => void;
};

export function BottomNav({
  procurementOpen,
  productionOpen,
  salesOpen,
  masterOpen,
  moreOpen,
  onToggleProcurement,
  onToggleProduction,
  onToggleSales,
  onToggleMaster,
  onToggleMore,
  onNavigate,
}: BottomNavProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAppSelector(selectAuthUser);
  const onProcurementRoute = location.pathname.startsWith("/procurement");
  const onProductionRoute =
    location.pathname === "/production" || location.pathname.startsWith("/production/");
  const onSalesRoute = location.pathname === "/sales" || location.pathname.startsWith("/sales/");
  const onMasterRoute = location.pathname.startsWith("/master");
  const procurementHighlighted = onProcurementRoute || procurementOpen;
  const productionHighlighted = onProductionRoute || productionOpen;
  const salesHighlighted = onSalesRoute || salesOpen;
  const masterHighlighted = onMasterRoute || masterOpen;

  return (
    <nav className={styles.bottomNav} aria-label="Primary">
      {visibleNavigation(user).map((item) => {
        const Icon = icons[item.id as keyof typeof icons];

        if (item.id === "procurement" && item.opensMenu) {
          return (
            <button
              key={item.id}
              type="button"
              className={
                procurementHighlighted
                  ? `${styles.navButton} ${styles.navButtonActive}`
                  : styles.navButton
              }
              aria-expanded={procurementOpen}
              aria-label={item.label}
              onClick={() => {
                if (!onProcurementRoute) {
                  navigate(item.to);
                  return;
                }
                onToggleProcurement();
              }}
            >
              <Icon />
              <span className={styles.navLabel}>{item.label}</span>
            </button>
          );
        }

        if (item.id === "production" && item.opensMenu) {
          return (
            <button
              key={item.id}
              type="button"
              className={
                productionHighlighted
                  ? `${styles.navButton} ${styles.navButtonActive}`
                  : styles.navButton
              }
              aria-expanded={productionOpen}
              aria-label={item.label}
              onClick={() => {
                if (!onProductionRoute) {
                  navigate(item.to);
                  return;
                }
                onToggleProduction();
              }}
            >
              <Icon />
              <span className={styles.navLabel}>{item.label}</span>
            </button>
          );
        }

        if (item.id === "sales" && item.opensMenu) {
          return (
            <button
              key={item.id}
              type="button"
              className={
                salesHighlighted
                  ? `${styles.navButton} ${styles.navButtonActive}`
                  : styles.navButton
              }
              aria-expanded={salesOpen}
              aria-label={item.label}
              onClick={() => {
                if (!onSalesRoute) {
                  navigate(item.to);
                  return;
                }
                onToggleSales();
              }}
            >
              <Icon />
              <span className={styles.navLabel}>{item.label}</span>
            </button>
          );
        }

        if (item.id === "master" && item.opensMenu) {
          return (
            <button
              key={item.id}
              type="button"
              className={
                masterHighlighted
                  ? `${styles.navButton} ${styles.navButtonActive}`
                  : styles.navButton
              }
              aria-expanded={masterOpen}
              aria-label={item.label}
              onClick={() => {
                if (!onMasterRoute) {
                  navigate(item.to);
                  return;
                }
                onToggleMaster();
              }}
            >
              <Icon />
              <span className={styles.navLabel}>{item.label}</span>
            </button>
          );
        }

        return (
          <NavItem
            key={item.id}
            to={item.to}
            label={item.label}
            icon={<Icon />}
            onNavigate={onNavigate}
          />
        );
      })}
      <div className={styles.moreWrap}>
        <button
          type="button"
          className={moreOpen ? `${styles.navButton} ${styles.navButtonActive}` : styles.navButton}
          aria-expanded={moreOpen}
          aria-label="More"
          onClick={onToggleMore}
        >
          <MoreIcon />
          <span className={styles.navLabel}>More</span>
        </button>
        {moreOpen ? (
          <p className={styles.moreNote} role="status">
            More modules will be added in a later phase.
          </p>
        ) : null}
      </div>
    </nav>
  );
}

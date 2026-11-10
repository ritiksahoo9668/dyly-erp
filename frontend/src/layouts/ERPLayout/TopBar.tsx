import { useEffect, useId, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { logout, selectAuthUser } from "@/app/store/authSlice";
import { useAppDispatch, useAppSelector } from "@/app/store/hooks";
import { ServiceStatus } from "@/components/feedback/ServiceStatus";
import {
  BellIcon,
  CalendarIcon,
  ChevronDownIcon,
  DylyLogo,
  SearchIcon,
} from "@/components/navigation/icons";
import { appConfig } from "@/config/app";
import { formatDisplayDate } from "@/utils/formatDate";
import styles from "./ERPLayout.module.css";

export function TopBar() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const user = useAppSelector(selectAuthUser);
  const today = formatDisplayDate(new Date());
  const menuId = useId();
  const menuRef = useRef<HTMLDivElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const displayName = user?.display_name ?? appConfig.user.name;
  const roleLabel = user?.role_label ?? appConfig.user.role;
  const initials = user?.initials ?? appConfig.user.initials;
  const email = user?.email;

  useEffect(() => {
    if (!menuOpen) return;

    function onPointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  function handleLogout() {
    setMenuOpen(false);
    dispatch(logout());
    navigate("/login", { replace: true });
  }

  return (
    <header className={styles.topbar}>
      <div className={styles.brand}>
        <DylyLogo size={30} />
        <strong>{appConfig.productName}</strong>
      </div>

      <form className={styles.search} role="search" onSubmit={(event) => event.preventDefault()}>
        <SearchIcon />
        <input
          type="search"
          placeholder="Search ERP modules, documents, or anything..."
          aria-label="Search ERP"
        />
        <kbd className={styles.shortcut}>Ctrl + K</kbd>
      </form>

      <div className={styles.meta}>
        <ServiceStatus />
        <span className={styles.date}>
          <CalendarIcon />
          {today}
        </span>
        <button type="button" className={styles.bell} aria-label="Notifications">
          <BellIcon />
          <span className={styles.bellDot} aria-hidden="true" />
        </button>

        <div className={styles.userMenu} ref={menuRef}>
          <button
            type="button"
            className={`${styles.user} ${menuOpen ? styles.userOpen : ""}`}
            aria-label="User menu"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-controls={menuId}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className={styles.avatar} aria-hidden="true">
              {initials}
            </span>
            <span className={styles.userText}>
              <strong>{displayName}</strong>
              <small>{roleLabel}</small>
            </span>
            <span className={`${styles.chevron} ${menuOpen ? styles.chevronOpen : ""}`}>
              <ChevronDownIcon />
            </span>
          </button>

          {menuOpen ? (
            <div className={styles.userDropdown} id={menuId} role="menu">
              <div className={styles.userDropdownHeader}>
                <span className={styles.avatar} aria-hidden="true">
                  {initials}
                </span>
                <div>
                  <strong>{displayName}</strong>
                  {email ? <small>{email}</small> : <small>{roleLabel}</small>}
                </div>
              </div>
              <div className={styles.userDropdownDivider} />
              <button
                type="button"
                className={styles.userDropdownItem}
                role="menuitem"
                onClick={handleLogout}
              >
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

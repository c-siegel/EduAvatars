import { useEffect, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { LayoutDashboard, BarChart3, KeyRound, Settings2, Menu, X, LogOut, type LucideIcon } from "lucide-react";
import { NavItem } from "@/components/NavItem";
import { Scrim } from "@/components/Drawer";
import { Wordmark } from "@/components/Wordmark";
import { Avatar } from "@/components/Avatar";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { toAbsoluteAvatarUrl } from "@/lib/avatarUrl";
import styles from "./DashboardShell.module.css";

interface NavConfigItem {
  labelKey: string;
  href: string;
  icon: LucideIcon;
  isActive: (pathname: string) => boolean;
}

const NAV_ITEMS: NavConfigItem[] = [
  { labelKey: "nav.overview", href: "/dashboard", icon: LayoutDashboard, isActive: (p) => p === "/dashboard" },
  {
    labelKey: "nav.analytics",
    href: "/dashboard/analytics",
    icon: BarChart3,
    isActive: (p) => p.startsWith("/dashboard/analytics"),
  },
  {
    labelKey: "nav.apiDashboard",
    href: "/dashboard/api",
    icon: KeyRound,
    isActive: (p) => p.startsWith("/dashboard/api"),
  },
  {
    labelKey: "nav.profile",
    href: "/dashboard/profile",
    icon: Settings2,
    isActive: (p) => p.startsWith("/dashboard/profile"),
  },
];

// Layout für 1c–1h — Sidebar (Desktop) bzw. Hamburger + Overlay-Drawer (<1024px) + Content-Bereich
export function DashboardShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { data: user, error } = useCurrentUser();

  // Auth guard: only a confirmed 401 sends teachers back to /login. A network/5xx error
  // (e.g. backend not running yet during frontend-only work) just falls back to "…" below,
  // instead of bouncing the user away from a page they were legitimately allowed to see.
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      navigate("/login", { replace: true });
    }
  }, [error, navigate]);

  // Close the mobile drawer on every route change (e.g. after tapping a nav item).
  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  const activeItem = NAV_ITEMS.find((item) => item.isActive(location.pathname));
  const activeLabel = activeItem ? t(activeItem.labelKey) : t("nav.dashboardFallback");

  async function handleLogout() {
    await authApi.logout().catch(() => undefined);
    queryClient.removeQueries({ queryKey: ["auth", "me"] });
    navigate("/login");
  }

  const sidebar = (
    <aside className={`${styles.sidebar} ${mobileNavOpen ? styles.sidebarOpen : ""}`}>
      <div className={styles.sidebarHeader}>
        <Wordmark />
      </div>
      <nav className={styles.nav} aria-label={t("nav.dashboardNavAriaLabel")}>
        {NAV_ITEMS.map((item) => (
          <NavItem key={item.labelKey} to={item.href} icon={item.icon} active={item.isActive(location.pathname)}>
            {t(item.labelKey)}
          </NavItem>
        ))}
      </nav>
      <div className={styles.sidebarFooter}>
        <div className={styles.userRow}>
          <Avatar name={user?.name ?? ""} src={toAbsoluteAvatarUrl(user?.avatarUrl)} size="sm" />
          <div className={styles.userInfo}>
            <span className={styles.userName}>{user?.name ?? "…"}</span>
            <span className={styles.userSchool}>{user?.school ?? ""}</span>
          </div>
        </div>
        <div className={styles.languageSwitcherRow}>
          <LanguageSwitcher />
        </div>
        <button className={styles.logoutButton} onClick={handleLogout}>
          <LogOut size={16} strokeWidth={2} />
          {t("nav.logout")}
        </button>
      </div>
    </aside>
  );

  return (
    <div className={styles.shell}>
      <header className={styles.mobileTopbar}>
        <button
          className={styles.menuButton}
          aria-label={mobileNavOpen ? t("nav.closeMenu") : t("nav.openMenu")}
          aria-expanded={mobileNavOpen}
          onClick={() => setMobileNavOpen((open) => !open)}
        >
          {mobileNavOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <h3 className={styles.mobileTitle}>{activeLabel}</h3>
        <Avatar name={user?.name ?? ""} size="sm" />
      </header>

      {mobileNavOpen && <Scrim onClick={() => setMobileNavOpen(false)} />}

      {sidebar}

      <main className={styles.content}>{children}</main>
    </div>
  );
}

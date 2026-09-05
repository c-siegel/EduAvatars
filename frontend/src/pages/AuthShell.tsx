import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Card } from "@/components/Card";
import { Callout } from "@/components/Callout";
import { Wordmark } from "@/components/Wordmark";
import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./AuthShell.module.css";

interface AuthShellProps {
  active: "login" | "register" | "none";
  subtitle: string;
  error?: string | null;
  children: ReactNode;
  footer: ReactNode;
}

// Shared card chrome for Screen 1b (Login/Registrierung) — wordmark, the
// Anmelden/Registrieren segmented control, and the error callout slot.
// The actual form fields are supplied by each page via `children`.
export function AuthShell({ active, subtitle, error, children, footer }: AuthShellProps) {
  const { t } = useTranslation();
  return (
    <PublicLayout>
      <div className={styles.wrapper}>
        <Card className={styles.card}>
          <div className={styles.brand}>
            <Wordmark />
            <p className={styles.subtitle}>{subtitle}</p>
          </div>

          {active !== "none" && (
            <nav className={styles.tabs} aria-label={t("auth.tabsAriaLabel")}>
              <Link
                to="/login"
                className={`${styles.tab} ${active === "login" ? styles.tabActive : ""}`}
                aria-current={active === "login" ? "page" : undefined}
              >
                {t("common.login")}
              </Link>
              <Link
                to="/register"
                className={`${styles.tab} ${active === "register" ? styles.tabActive : ""}`}
                aria-current={active === "register" ? "page" : undefined}
              >
                {t("common.register")}
              </Link>
            </nav>
          )}

          {error && <Callout variant="danger">{error}</Callout>}

          {children}

          <p className={styles.footerNote}>{footer}</p>
        </Card>
      </div>
    </PublicLayout>
  );
}

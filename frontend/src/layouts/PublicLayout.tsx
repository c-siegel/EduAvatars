import type { ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import styles from "./PublicLayout.module.css";

interface PublicLayoutProps {
  children: ReactNode;
  // Landing has its own header (nav links + Sign in/Sign up) that already fills the top-right
  // corner, so it renders its own inline LanguageSwitcher instead and opts out of this one.
  showLanguageSwitcher?: boolean;
}

// Layout for 1a/1b — public pages without a sidebar; the page content (header/hero/card) lives in
// each page, since the header structure differs a lot between landing (nav) and login/register
// (centered card).
export function PublicLayout({ children, showLanguageSwitcher = true }: PublicLayoutProps) {
  return (
    <div className={styles.page}>
      {showLanguageSwitcher && (
        <div className={styles.languageSwitcher}>
          <LanguageSwitcher />
        </div>
      )}
      {children}
    </div>
  );
}

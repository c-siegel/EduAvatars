import type { ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import styles from "./PublicLayout.module.css";

interface PublicLayoutProps {
  children: ReactNode;
  // Landing has its own header (nav links + Sign in/Sign up) that already fills the top-right
  // corner, so it renders its own inline LanguageSwitcher instead and opts out of this one.
  showLanguageSwitcher?: boolean;
}

// Layout für 1a/1b — öffentliche Seiten ohne Sidebar; Seiteninhalt (Header/Hero/Card) liegt in der jeweiligen Page,
// da sich Header-Aufbau zwischen Landing (Nav) und Login/Register (zentrierte Card) stark unterscheidet.
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

import type { ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import styles from "./PublicChatLayout.module.css";

interface PublicChatLayoutProps {
  children: ReactNode;
  // The chat stage has its own header (end-chat/info buttons) that already fills the top-right
  // corner, so it renders its own inline LanguageSwitcher instead and opts out of this one —
  // same pattern as PublicLayout's showLanguageSwitcher.
  showLanguageSwitcher?: boolean;
}

// Layout für 1i — unabhängig von DashboardShell/Auth, mobile-first
export function PublicChatLayout({ children, showLanguageSwitcher = true }: PublicChatLayoutProps) {
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

import type { ReactNode } from "react";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import styles from "./PublicChatLayout.module.css";

// Layout für 1i — unabhängig von DashboardShell/Auth, mobile-first
export function PublicChatLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.page}>
      <div className={styles.languageSwitcher}>
        <LanguageSwitcher />
      </div>
      {children}
    </div>
  );
}

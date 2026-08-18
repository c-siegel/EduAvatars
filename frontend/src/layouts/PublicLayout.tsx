import type { ReactNode } from "react";
import styles from "./PublicLayout.module.css";

// Layout für 1a/1b — öffentliche Seiten ohne Sidebar; Seiteninhalt (Header/Hero/Card) liegt in der jeweiligen Page,
// da sich Header-Aufbau zwischen Landing (Nav) und Login/Register (zentrierte Card) stark unterscheidet.
export function PublicLayout({ children }: { children: ReactNode }) {
  return <div className={styles.page}>{children}</div>;
}

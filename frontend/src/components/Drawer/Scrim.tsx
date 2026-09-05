import { useTranslation } from "react-i18next";
import styles from "./Scrim.module.css";

// Backdrop behind the mobile sidebar drawer (Screen 1c) — a <button> so it's
// keyboard/click accessible as a "close" affordance, not just a decorative div.
export function Scrim({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();
  return <button className={styles.scrim} aria-label={t("nav.closeMenu")} onClick={onClick} />;
}

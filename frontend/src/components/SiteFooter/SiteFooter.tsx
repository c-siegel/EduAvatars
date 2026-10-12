import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import styles from "./SiteFooter.module.css";

const DOCS_URL = import.meta.env.VITE_DOCS_URL;

// "0.1.0 (a1b2c3d)"; the commit is empty when the build had neither APP_COMMIT nor a git checkout.
const VERSION = __APP_COMMIT__ ? `${__APP_VERSION__} (${__APP_COMMIT__})` : __APP_VERSION__;

// Footer of the public pages (landing, login, register, ...): legal links, the documentation link
// and the build version, so support requests can name the exact build.
export function SiteFooter() {
  const { t } = useTranslation();
  return (
    <footer className={styles.footer}>
      <span>© EduAvatars</span>
      {/* Link, not <a href>, for the in-app routes: a plain anchor would reload the whole SPA. */}
      <nav className={styles.links} aria-label={t("siteFooter.navAriaLabel")}>
        <Link to="/datenschutz">{t("landing.footer.privacy")}</Link>
        <Link to="/impressum">{t("landing.footer.imprint")}</Link>
        <Link to="/credits">{t("landing.footer.credits")}</Link>
        {DOCS_URL ? (
          <a href={DOCS_URL} target="_blank" rel="noopener noreferrer">
            {t("siteFooter.docs")}
          </a>
        ) : (
          <span className={styles.soon}>{t("siteFooter.docsSoon")}</span>
        )}
      </nav>
      <span className={styles.version}>{t("siteFooter.version", { version: VERSION })}</span>
    </footer>
  );
}

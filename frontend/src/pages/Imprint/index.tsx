import { useTranslation } from "react-i18next";
import { numberLocale } from "@/lib/format";
import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Imprint.module.css";

// Screen — Impressum (Legal Notice)
export function ImprintPage() {
  const { t } = useTranslation();
  return (
    <PublicLayout>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1>{t("imprint.title")}</h1>
          <p className={styles.subtitle}>{t("imprint.subtitle")}</p>
        </header>

        <section className={styles.section}>
          <h2>{t("imprint.provider.title")}</h2>
          <div className={styles.content}>
            <p>
              <strong>{t("imprint.provider.name")}</strong> {t("imprint.placeholder")}
            </p>
            <p>
              <strong>{t("imprint.provider.street")}</strong> {t("imprint.placeholder")}
            </p>
            <p>
              <strong>{t("imprint.provider.city")}</strong> {t("imprint.placeholder")}
            </p>
            <p>
              <strong>{t("imprint.provider.country")}</strong> {t("imprint.provider.countryValue")}
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("imprint.contact.title")}</h2>
          <div className={styles.content}>
            <p>
              <strong>{t("imprint.contact.email")}</strong>
              {t("imprint.placeholder")}
              <a href="mailto:kontakt@beispiel.de">noch ändern@beispiel.de</a>
            </p>
            <p>
              <strong>{t("imprint.contact.phone")}</strong> {t("imprint.contact.phonePlaceholder")}
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("imprint.responsible.title")}</h2>
          <div className={styles.content}>
            <p>
              <strong>{t("imprint.provider.name")}</strong> {t("imprint.placeholder")}
            </p>
            <p>
              <strong>{t("imprint.contact.email")}</strong>
              {t("imprint.placeholder")}
              <a href="mailto:kontakt@beispiel.de">noch ändern@beispiel.de</a>
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("imprint.liability.contentTitle")}</h2>
          <div className={styles.content}>
            <p>{t("imprint.liability.contentP1")}</p>
            <p>{t("imprint.liability.contentP2")}</p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("imprint.liability.linksTitle")}</h2>
          <div className={styles.content}>
            <p>{t("imprint.liability.linksP1")}</p>
            <p>{t("imprint.liability.linksP2")}</p>
          </div>
        </section>

        <footer className={styles.footer}>
          <p>{t("imprint.asOf", { date: new Date().toLocaleDateString(numberLocale()) })}</p>
        </footer>
      </div>
    </PublicLayout>
  );
}

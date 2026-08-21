import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { settingsApi } from "@/api/settings";
import { numberLocale } from "@/lib/format";
import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Privacy.module.css";

/** Screen — Datenschutzerklärung (privacy policy), required before any student data is processed. */
export function PrivacyPage() {
  const { t } = useTranslation();
  // The controller's contact details come from the same admin-editable site settings as the
  // imprint, so an operator fills them in once and both pages are correct.
  const settingsQuery = useQuery({ queryKey: ["settings", "public"], queryFn: settingsApi.getPublic });
  const settings = settingsQuery.data;
  const placeholder = t("imprint.placeholder");

  return (
    <PublicLayout>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1>{t("privacy.title")}</h1>
          <p className={styles.subtitle}>{t("privacy.subtitle")}</p>
        </header>

        <section className={styles.section}>
          <h2>{t("privacy.controller.title")}</h2>
          <div className={styles.content}>
            <p>{t("privacy.controller.text")}</p>
            <p>
              {settings?.providerName || placeholder}
              <br />
              {settings?.providerStreet || placeholder}
              <br />
              {settings?.providerCity || placeholder}
              <br />
              {settings?.providerCountry || placeholder}
            </p>
            <p>
              <strong>{t("imprint.contact.email")}</strong>{" "}
              {settings?.contactEmail ? (
                <a href={`mailto:${settings.contactEmail}`}>{settings.contactEmail}</a>
              ) : (
                placeholder
              )}
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("privacy.teachers.title")}</h2>
          <div className={styles.content}>
            <p>{t("privacy.teachers.text")}</p>
            <p>{t("privacy.teachers.legalBasis")}</p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("privacy.students.title")}</h2>
          <div className={styles.content}>
            <p>{t("privacy.students.noAccount")}</p>
            <p>{t("privacy.students.cookie")}</p>
            <p>{t("privacy.students.recording")}</p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("privacy.ai.title")}</h2>
          <div className={styles.content}>
            <p>{t("privacy.ai.text")}</p>
            <p>{t("privacy.ai.speech")}</p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("privacy.retention.title")}</h2>
          <div className={styles.content}>
            <p>{t("privacy.retention.text")}</p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("privacy.rights.title")}</h2>
          <div className={styles.content}>
            <p>{t("privacy.rights.text")}</p>
            <p>{t("privacy.rights.students")}</p>
            <p>{t("privacy.rights.complaint")}</p>
          </div>
        </section>

        <footer className={styles.footer}>
          <p>{t("imprint.asOf", { date: new Date().toLocaleDateString(numberLocale()) })}</p>
          <p>
            <Link to="/impressum">{t("landing.footer.imprint")}</Link>
          </p>
        </footer>
      </div>
    </PublicLayout>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { settingsApi } from "@/api/settings";
import { numberLocale } from "@/lib/format";
import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Imprint.module.css";

// Screen — Impressum (Legal Notice)
export function ImprintPage() {
  const { t } = useTranslation();
  // Every value here is admin-editable (Dashboard → Admin → Site settings) rather than hardcoded,
  // so a self-hoster can produce a valid imprint without touching the source. Anything not filled
  // in yet falls back to the "[noch ändern]" placeholder instead of rendering blank.
  const settingsQuery = useQuery({ queryKey: ["settings", "public"], queryFn: settingsApi.getPublic });
  const settings = settingsQuery.data;
  const placeholder = t("imprint.placeholder");

  const contactEmailValue = settings?.contactEmail ? (
    <a href={`mailto:${settings.contactEmail}`}>{settings.contactEmail}</a>
  ) : (
    placeholder
  );

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
              <strong>{t("imprint.provider.name")}</strong> {settings?.providerName || placeholder}
            </p>
            <p>
              <strong>{t("imprint.provider.street")}</strong> {settings?.providerStreet || placeholder}
            </p>
            <p>
              <strong>{t("imprint.provider.city")}</strong> {settings?.providerCity || placeholder}
            </p>
            <p>
              <strong>{t("imprint.provider.country")}</strong>{" "}
              {settings?.providerCountry || t("imprint.provider.countryValue")}
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("imprint.contact.title")}</h2>
          <div className={styles.content}>
            <p>
              <strong>{t("imprint.contact.email")}</strong> {contactEmailValue}
            </p>
            <p>
              <strong>{t("imprint.contact.phone")}</strong>{" "}
              {settings?.contactPhone || t("imprint.contact.phonePlaceholder")}
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("imprint.responsible.title")}</h2>
          <div className={styles.content}>
            <p>
              <strong>{t("imprint.provider.name")}</strong> {settings?.providerName || placeholder}
            </p>
            <p>
              <strong>{t("imprint.contact.email")}</strong> {contactEmailValue}
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
          <p>
            <Link to="/datenschutz">{t("landing.footer.privacy")}</Link>
          </p>
        </footer>
      </div>
    </PublicLayout>
  );
}

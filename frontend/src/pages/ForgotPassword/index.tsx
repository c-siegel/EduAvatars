import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Callout } from "@/components/Callout";
import { authApi } from "@/api/auth";
import { AuthShell } from "@/pages/AuthShell";
import styles from "@/pages/AuthShell.module.css";

// Screen 1b (Erweiterung) — Passwort-vergessen-Formular. Antwortet immer mit derselben Meldung,
// egal ob die E-Mail existiert (siehe backend/app/services/password_reset_service.py) — verhindert
// Enumeration registrierter Konten, deshalb gibt es hier bewusst keinen Fehlerzustand für "unbekannte E-Mail".
export function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await authApi.forgotPassword(email);
    } finally {
      setSubmitting(false);
      setSent(true);
    }
  }

  return (
    <AuthShell
      active="none"
      subtitle={t("auth.forgotPassword.subtitle")}
      footer={
        <>
          {t("auth.forgotPassword.remembered")} <Link to="/login">{t("common.login")}</Link>
        </>
      }
    >
      {sent ? (
        <Callout variant="info">{t("auth.forgotPassword.sentNotice")}</Callout>
      ) : (
        <form className={styles.form} onSubmit={handleSubmit}>
          <Input
            label={t("auth.emailLabel")}
            type="email"
            name="email"
            placeholder={t("auth.emailPlaceholder")}
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" variant="accent" fullWidth disabled={submitting}>
            {t("auth.forgotPassword.submit")}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}

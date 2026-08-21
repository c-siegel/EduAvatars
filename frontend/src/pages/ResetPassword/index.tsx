import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Callout } from "@/components/Callout";
import { authApi } from "@/api/auth";
import { AuthShell } from "@/pages/AuthShell";
import styles from "@/pages/AuthShell.module.css";

const MIN_PASSWORD_LENGTH = 10;

// Screen 1b (Erweiterung) — Ziel des Links aus der Passwort-Reset-E-Mail (?token=...).
export function ResetPasswordPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (password.length < MIN_PASSWORD_LENGTH || !/\d/.test(password)) {
      setError(t("auth.resetPassword.errorTooShort", { min: MIN_PASSWORD_LENGTH }));
      return;
    }
    if (password !== confirm) {
      setError(t("auth.resetPassword.errorMismatch"));
      return;
    }

    setSubmitting(true);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch {
      setError(t("auth.resetPassword.errorInvalidLink"));
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthShell active="none" subtitle={t("auth.resetPassword.subtitle")} footer={<Link to="/login">{t("auth.backToLogin")}</Link>}>
        <Callout variant="danger">
          {t("auth.resetPassword.noValidLinkPrefix")}{" "}
          <Link to="/forgot-password">{t("auth.forgotPassword.subtitle")}</Link>
          {t("auth.resetPassword.noValidLinkSuffix")}
        </Callout>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell active="none" subtitle={t("auth.resetPassword.doneSubtitle")} footer={null}>
        <Callout variant="info">{t("auth.resetPassword.doneNotice")}</Callout>
        <Button variant="accent" fullWidth onClick={() => navigate("/login")}>
          {t("auth.resetPassword.loginNow")}
        </Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      active="none"
      subtitle={t("auth.resetPassword.formSubtitle")}
      error={error}
      footer={<Link to="/login">{t("auth.backToLogin")}</Link>}
    >
      <form className={styles.form} onSubmit={handleSubmit}>
        <Input
          label={t("auth.resetPassword.newPasswordLabel")}
          type="password"
          name="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Input
          label={t("auth.resetPassword.repeatLabel")}
          type="password"
          name="confirm"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <p className={styles.hint}>{t("auth.resetPassword.hint", { min: MIN_PASSWORD_LENGTH })}</p>
        <Button type="submit" variant="accent" fullWidth disabled={submitting}>
          {t("auth.resetPassword.submit")}
        </Button>
      </form>
    </AuthShell>
  );
}

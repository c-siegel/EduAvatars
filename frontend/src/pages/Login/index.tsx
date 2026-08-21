import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { AuthShell } from "@/pages/AuthShell";
import styles from "@/pages/AuthShell.module.css";

// Screen 1b — Login
export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await authApi.login(email, password);
      navigate("/dashboard");
    } catch (err) {
      // Same message regardless of viewport — the wireframe shows a shorter
      // variant on mobile ("Login fehlgeschlagen"), but a real error message
      // shouldn't change wording depending on screen size.
      if (err instanceof ApiError && err.status === 401) {
        setError(t("errors.INVALID_CREDENTIALS"));
      } else {
        setError(t("auth.login.errorGeneric"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      active="login"
      subtitle={t("auth.login.subtitle")}
      error={error}
      footer={
        <>
          {t("auth.login.noAccount")} <Link to="/register">{t("common.register")}</Link>
        </>
      }
    >
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
        <Input
          label={t("auth.passwordLabel")}
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div className={styles.row}>
          <label className={styles.checkboxLabel}>
            <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
            {t("auth.login.rememberMe")}
          </label>
          <Link to="/forgot-password">{t("auth.login.forgotPassword")}</Link>
        </div>
        <Button type="submit" variant="accent" fullWidth disabled={submitting}>
          {t("common.login")}
        </Button>
      </form>
    </AuthShell>
  );
}

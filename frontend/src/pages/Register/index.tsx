import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Callout } from "@/components/Callout";
import { authApi } from "@/api/auth";
import { errorMessage } from "@/api/client";
import { AuthShell } from "@/pages/AuthShell";
import styles from "@/pages/AuthShell.module.css";

// Screen 1b — registration (same card as login, plus a name field + consent checkbox, see the
// wireframe annotation on 1b)
export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Config switch for the internal launch phase (see REGISTRATION_ENABLED in
  // backend/app/core/config.py) — while closed, render no form (no flicker) but show the notice
  // right away.
  const { data: registrationStatus, isLoading: statusLoading } = useQuery({
    queryKey: ["auth", "registration-status"],
    queryFn: authApi.registrationStatus,
  });
  const registrationDisabled = !statusLoading && registrationStatus?.enabled === false;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await authApi.register(name, email, password);
      navigate("/dashboard");
    } catch (err) {
      // errorMessage() surfaces the backend's actual code (duplicate email, weak password,
      // rate-limited, registration disabled, ...) when there is one, instead of collapsing
      // everything but a disabled-registration 403 into one generic message.
      setError(errorMessage(err, t("auth.register.errorGeneric")));
    } finally {
      setSubmitting(false);
    }
  }

  if (statusLoading) {
    return (
      <AuthShell active="register" subtitle={t("auth.register.subtitle")} footer={null}>
        {null}
      </AuthShell>
    );
  }

  if (registrationDisabled) {
    return (
      <AuthShell
        active="register"
        subtitle={t("common.register")}
        footer={
          <>
            {t("auth.register.hasAccount")} <Link to="/login">{t("common.login")}</Link>
          </>
        }
      >
        <Callout variant="info">{t("auth.register.disabledNotice")}</Callout>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      active="register"
      subtitle={t("auth.register.subtitle")}
      error={error}
      footer={
        <>
          {t("auth.register.hasAccount")} <Link to="/login">{t("common.login")}</Link>
        </>
      }
    >
      <form className={styles.form} onSubmit={handleSubmit}>
        <Input
          label={t("auth.nameLabel")}
          type="text"
          name="name"
          autoComplete="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
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
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <label className={styles.checkboxLabel}>
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />
          {t("auth.register.terms")}
        </label>
        <Button type="submit" variant="accent" fullWidth disabled={submitting || !agreed}>
          {t("auth.register.submit")}
        </Button>
      </form>
    </AuthShell>
  );
}

import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Callout } from "@/components/Callout";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { AuthShell } from "@/pages/AuthShell";
import styles from "@/pages/AuthShell.module.css";

// Screen 1b — Registrierung (gleiche Card wie Login, plus Namensfeld + Zustimmungs-Checkbox,
// siehe Wireframe-Annotation zu 1b)
export function RegisterPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Config-Schalter für den internen Startbetrieb (siehe REGISTRATION_ENABLED in backend/app/core/config.py) —
  // solange offen, kein Formular rendern (kein Flackern), sondern gleich den Hinweis zeigen.
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
      if (err instanceof ApiError && err.status === 403) {
        setError("Registrierung ist aktuell nicht möglich.");
      } else {
        setError("Registrierung fehlgeschlagen. Bitte überprüfe deine Angaben.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (statusLoading) {
    return (
      <AuthShell active="register" subtitle="Erstelle dein kostenloses Konto" footer={null}>
        {null}
      </AuthShell>
    );
  }

  if (registrationDisabled) {
    return (
      <AuthShell
        active="register"
        subtitle="Registrierung"
        footer={
          <>
            Bereits ein Konto? <Link to="/login">Anmelden</Link>
          </>
        }
      >
        <Callout variant="info">
          Registrierung ist aktuell nicht möglich. Diese Instanz von EduAvatars ist derzeit nur für
          den internen Gebrauch freigeschaltet. Bitte wende dich an deine Institution, falls du ein
          Konto benötigst.
        </Callout>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      active="register"
      subtitle="Erstelle dein kostenloses Konto"
      error={error}
      footer={
        <>
          Bereits ein Konto? <Link to="/login">Anmelden</Link>
        </>
      }
    >
      <form className={styles.form} onSubmit={handleSubmit}>
        <Input
          label="Name"
          type="text"
          name="name"
          autoComplete="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          label="E-Mail"
          type="email"
          name="email"
          placeholder="lehrkraft@schule.de"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          label="Passwort"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <label className={styles.checkboxLabel}>
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} required />
          Ich stimme den Nutzungsbedingungen und der Datenschutzerklärung zu.
        </label>
        <Button type="submit" variant="accent" fullWidth disabled={submitting || !agreed}>
          Konto erstellen
        </Button>
      </form>
    </AuthShell>
  );
}

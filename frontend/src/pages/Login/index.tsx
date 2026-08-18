import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { authApi } from "@/api/auth";
import { ApiError } from "@/api/client";
import { AuthShell } from "@/pages/AuthShell";
import styles from "@/pages/AuthShell.module.css";

// Screen 1b — Login
export function LoginPage() {
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
        setError("E-Mail oder Passwort ist falsch.");
      } else {
        setError("Anmeldung fehlgeschlagen. Bitte versuche es später erneut.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      active="login"
      subtitle="Willkommen zurück"
      error={error}
      footer={
        <>
          Noch kein Konto? <Link to="/register">Registrieren</Link>
        </>
      }
    >
      <form className={styles.form} onSubmit={handleSubmit}>
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
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div className={styles.row}>
          <label className={styles.checkboxLabel}>
            <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
            Angemeldet bleiben
          </label>
          <Link to="/forgot-password">Passwort vergessen?</Link>
        </div>
        <Button type="submit" variant="accent" fullWidth disabled={submitting}>
          Anmelden
        </Button>
      </form>
    </AuthShell>
  );
}

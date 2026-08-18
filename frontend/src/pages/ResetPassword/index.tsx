import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Callout } from "@/components/Callout";
import { authApi } from "@/api/auth";
import { AuthShell } from "@/pages/AuthShell";
import styles from "@/pages/AuthShell.module.css";

const MIN_PASSWORD_LENGTH = 10;

// Screen 1b (Erweiterung) — Ziel des Links aus der Passwort-Reset-E-Mail (?token=...).
export function ResetPasswordPage() {
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
      setError(`Neues Passwort braucht mind. ${MIN_PASSWORD_LENGTH} Zeichen und eine Zahl.`);
      return;
    }
    if (password !== confirm) {
      setError("Die Wiederholung stimmt nicht mit dem neuen Passwort überein.");
      return;
    }

    setSubmitting(true);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch {
      setError("Link ist ungültig oder abgelaufen. Bitte fordere einen neuen Link an.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <AuthShell active="none" subtitle="Passwort zurücksetzen" footer={<Link to="/login">Zur Anmeldung</Link>}>
        <Callout variant="danger">
          Kein gültiger Link. Bitte fordere über <Link to="/forgot-password">Passwort vergessen</Link> einen
          neuen Link an.
        </Callout>
      </AuthShell>
    );
  }

  if (done) {
    return (
      <AuthShell active="none" subtitle="Passwort zurückgesetzt" footer={null}>
        <Callout variant="info">Dein Passwort wurde geändert.</Callout>
        <Button variant="accent" fullWidth onClick={() => navigate("/login")}>
          Jetzt anmelden
        </Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell active="none" subtitle="Neues Passwort festlegen" error={error} footer={<Link to="/login">Zur Anmeldung</Link>}>
      <form className={styles.form} onSubmit={handleSubmit}>
        <Input
          label="Neues Passwort"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Input
          label="Wiederholen"
          type="password"
          name="confirm"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <p className={styles.hint}>Mind. {MIN_PASSWORD_LENGTH} Zeichen, eine Zahl</p>
        <Button type="submit" variant="accent" fullWidth disabled={submitting}>
          Passwort speichern
        </Button>
      </form>
    </AuthShell>
  );
}

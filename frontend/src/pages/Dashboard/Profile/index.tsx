import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { Input } from "@/components/Input";
import { Toast } from "@/components/Toast";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useToast } from "@/hooks/useToast";
import { profileApi } from "@/api/profile";
import { toAbsoluteAvatarUrl } from "@/lib/avatarUrl";
import styles from "./Profile.module.css";

const PICTURE_ACCEPT = "image/png,image/jpeg,image/webp";

const MIN_PASSWORD_LENGTH = 10;

// Screen 1h — Tab Profileinstellungen
export function ProfilePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data: user } = useCurrentUser();

  const [account, setAccount] = useState({ name: "", school: "", email: "" });
  const [accountLoaded, setAccountLoaded] = useState(false);

  useEffect(() => {
    if (user && !accountLoaded) {
      setAccount({ name: user.name, school: user.school ?? "", email: user.email });
      setAccountLoaded(true);
    }
  }, [user, accountLoaded]);

  const accountMutation = useMutation({
    mutationFn: () => profileApi.update(account),
    onSuccess: (updated) => {
      queryClient.setQueryData(["auth", "me"], updated);
      toast.show("Profil gespeichert.");
    },
  });

  const pictureInputRef = useRef<HTMLInputElement>(null);
  const [pictureError, setPictureError] = useState<string | null>(null);

  const uploadPictureMutation = useMutation({
    mutationFn: profileApi.uploadPicture,
    onSuccess: (updated) => {
      queryClient.setQueryData(["auth", "me"], updated);
      toast.show("Profilbild aktualisiert.");
    },
    onError: () => setPictureError("Bild konnte nicht hochgeladen werden (max. 5 MB, PNG/JPEG/WebP)."),
  });

  const deletePictureMutation = useMutation({
    mutationFn: profileApi.deletePicture,
    onSuccess: (updated) => {
      queryClient.setQueryData(["auth", "me"], updated);
      toast.show("Profilbild entfernt.");
    },
  });

  function handlePictureChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // erlaubt erneute Auswahl derselben Datei nach einem Fehler
    if (!file) return;
    setPictureError(null);
    uploadPictureMutation.mutate(file);
  }

  const [passwords, setPasswords] = useState({ current: "", next: "", confirm: "" });
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const passwordMutation = useMutation({
    mutationFn: () => profileApi.changePassword(passwords.current, passwords.next),
    onSuccess: () => {
      setPasswords({ current: "", next: "", confirm: "" });
      toast.show("Passwort aktualisiert.");
    },
    onError: () => setPasswordError("Aktuelles Passwort ist falsch oder die Anfrage ist fehlgeschlagen."),
  });

  function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);

    if (passwords.next.length < MIN_PASSWORD_LENGTH || !/\d/.test(passwords.next)) {
      setPasswordError(`Neues Passwort braucht mind. ${MIN_PASSWORD_LENGTH} Zeichen und eine Zahl.`);
      return;
    }
    if (passwords.next !== passwords.confirm) {
      setPasswordError("Die Wiederholung stimmt nicht mit dem neuen Passwort überein.");
      return;
    }
    passwordMutation.mutate();
  }

  const logoutEverywhereMutation = useMutation({
    mutationFn: profileApi.logoutEverywhere,
    onSuccess: () => toast.show("Alle anderen Sitzungen wurden abgemeldet."),
  });

  function handleLogoutEverywhere() {
    if (window.confirm("Auf allen anderen Geräten/Browsern abmelden? Diese Sitzung bleibt aktiv.")) {
      logoutEverywhereMutation.mutate();
    }
  }

  const deleteMutation = useMutation({
    mutationFn: profileApi.deleteAccount,
    onSuccess: () => {
      queryClient.clear();
      navigate("/");
    },
  });

  function handleDeleteAccount() {
    if (
      window.confirm(
        "Alle Projekte und Links werden dauerhaft entfernt. Konto wirklich unwiderruflich löschen?",
      )
    ) {
      deleteMutation.mutate();
    }
  }

  return (
    <div className={styles.page}>
      <form
        className={styles.card}
        onSubmit={(e) => {
          e.preventDefault();
          accountMutation.mutate();
        }}
      >
        <h3>Konto</h3>

        <div className={styles.avatarRow}>
          <Avatar name={account.name} src={toAbsoluteAvatarUrl(user?.avatarUrl)} size="lg" />
          <div className={styles.avatarActions}>
            <input
              ref={pictureInputRef}
              type="file"
              accept={PICTURE_ACCEPT}
              onChange={handlePictureChange}
              hidden
            />
            <Button
              type="button"
              size="sm"
              onClick={() => pictureInputRef.current?.click()}
              disabled={uploadPictureMutation.isPending}
            >
              Bild ändern
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => deletePictureMutation.mutate()}
              disabled={!user?.avatarUrl || deletePictureMutation.isPending}
            >
              Entfernen
            </Button>
          </div>
        </div>
        {pictureError && <Callout variant="danger">{pictureError}</Callout>}

        <div className={styles.fieldRow}>
          <Input
            label="Vor- & Nachname"
            value={account.name}
            onChange={(e) => setAccount((a) => ({ ...a, name: e.target.value }))}
            required
          />
          <Input
            label="Schule"
            value={account.school}
            onChange={(e) => setAccount((a) => ({ ...a, school: e.target.value }))}
          />
        </div>

        <Input
          label="E-Mail"
          type="email"
          value={account.email}
          onChange={(e) => setAccount((a) => ({ ...a, email: e.target.value }))}
          required
        />

        {accountMutation.isError && (
          <Callout variant="danger">Speichern fehlgeschlagen. Bitte erneut versuchen.</Callout>
        )}

        <Button type="submit" variant="accent" disabled={accountMutation.isPending}>
          Änderungen speichern
        </Button>
      </form>

      <form className={styles.card} onSubmit={handlePasswordSubmit}>
        <h3>Passwort ändern</h3>

        <Input
          label="Aktuelles Passwort"
          type="password"
          autoComplete="current-password"
          value={passwords.current}
          onChange={(e) => setPasswords((p) => ({ ...p, current: e.target.value }))}
          required
        />

        <div className={styles.fieldRow}>
          <Input
            label="Neues Passwort"
            type="password"
            autoComplete="new-password"
            value={passwords.next}
            onChange={(e) => setPasswords((p) => ({ ...p, next: e.target.value }))}
            required
          />
          <Input
            label="Wiederholen"
            type="password"
            autoComplete="new-password"
            value={passwords.confirm}
            onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))}
            required
          />
        </div>

        <p className={styles.hint}>Mind. {MIN_PASSWORD_LENGTH} Zeichen, eine Zahl</p>

        {passwordError && <Callout variant="danger">{passwordError}</Callout>}

        <Button type="submit" variant="accent" disabled={passwordMutation.isPending}>
          Passwort aktualisieren
        </Button>
      </form>

      <div className={styles.card}>
        <h3>Sitzungen</h3>
        <p className={styles.dangerText}>
          Falls du den Verdacht hast, dass dein Konto auf einem anderen Gerät angemeldet ist: alle
          anderen Sitzungen sofort beenden. Diese Sitzung hier bleibt aktiv.
        </p>
        <Button
          variant="default"
          onClick={handleLogoutEverywhere}
          disabled={logoutEverywhereMutation.isPending}
        >
          Auf allen anderen Geräten abmelden
        </Button>
      </div>

      <div className={styles.card}>
        <h3>Konto löschen</h3>
        <p className={styles.dangerText}>Alle Projekte und Links werden dauerhaft entfernt.</p>
        <Button variant="danger" onClick={handleDeleteAccount} disabled={deleteMutation.isPending}>
          Konto löschen
        </Button>
      </div>

      {toast.message && <Toast message={toast.message} onDismiss={toast.dismiss} />}
    </div>
  );
}

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
      toast.show(t("profile.savedToast"));
    },
  });

  const pictureInputRef = useRef<HTMLInputElement>(null);
  const [pictureError, setPictureError] = useState<string | null>(null);

  const uploadPictureMutation = useMutation({
    mutationFn: profileApi.uploadPicture,
    onSuccess: (updated) => {
      queryClient.setQueryData(["auth", "me"], updated);
      toast.show(t("profile.pictureUpdatedToast"));
    },
    onError: () => setPictureError(t("profile.pictureUploadError")),
  });

  const deletePictureMutation = useMutation({
    mutationFn: profileApi.deletePicture,
    onSuccess: (updated) => {
      queryClient.setQueryData(["auth", "me"], updated);
      toast.show(t("profile.pictureRemovedToast"));
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
      toast.show(t("profile.passwordUpdatedToast"));
    },
    onError: () => setPasswordError(t("profile.passwordChangeError")),
  });

  function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);

    if (passwords.next.length < MIN_PASSWORD_LENGTH || !/\d/.test(passwords.next)) {
      setPasswordError(t("auth.resetPassword.errorTooShort", { min: MIN_PASSWORD_LENGTH }));
      return;
    }
    if (passwords.next !== passwords.confirm) {
      setPasswordError(t("auth.resetPassword.errorMismatch"));
      return;
    }
    passwordMutation.mutate();
  }

  const logoutEverywhereMutation = useMutation({
    mutationFn: profileApi.logoutEverywhere,
    onSuccess: () => toast.show(t("profile.loggedOutEverywhereToast")),
  });

  function handleLogoutEverywhere() {
    if (window.confirm(t("profile.confirmLogoutEverywhere"))) {
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
    if (window.confirm(t("profile.confirmDeleteAccount"))) {
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
        <h3>{t("profile.account")}</h3>

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
              {t("profile.changePicture")}
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => deletePictureMutation.mutate()}
              disabled={!user?.avatarUrl || deletePictureMutation.isPending}
            >
              {t("apiDashboard.remove")}
            </Button>
          </div>
        </div>
        {pictureError && <Callout variant="danger">{pictureError}</Callout>}

        <div className={styles.fieldRow}>
          <Input
            label={t("profile.fullName")}
            value={account.name}
            onChange={(e) => setAccount((a) => ({ ...a, name: e.target.value }))}
            required
          />
          <Input
            label={t("profile.school")}
            value={account.school}
            onChange={(e) => setAccount((a) => ({ ...a, school: e.target.value }))}
          />
        </div>

        <Input
          label={t("auth.emailLabel")}
          type="email"
          value={account.email}
          onChange={(e) => setAccount((a) => ({ ...a, email: e.target.value }))}
          required
        />

        {accountMutation.isError && <Callout variant="danger">{t("profile.saveError")}</Callout>}

        <Button type="submit" variant="accent" disabled={accountMutation.isPending}>
          {t("profile.saveChanges")}
        </Button>
      </form>

      <form className={styles.card} onSubmit={handlePasswordSubmit}>
        <h3>{t("profile.changePassword")}</h3>

        <Input
          label={t("profile.currentPassword")}
          type="password"
          autoComplete="current-password"
          value={passwords.current}
          onChange={(e) => setPasswords((p) => ({ ...p, current: e.target.value }))}
          required
        />

        <div className={styles.fieldRow}>
          <Input
            label={t("auth.resetPassword.newPasswordLabel")}
            type="password"
            autoComplete="new-password"
            value={passwords.next}
            onChange={(e) => setPasswords((p) => ({ ...p, next: e.target.value }))}
            required
          />
          <Input
            label={t("auth.resetPassword.repeatLabel")}
            type="password"
            autoComplete="new-password"
            value={passwords.confirm}
            onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))}
            required
          />
        </div>

        <p className={styles.hint}>{t("auth.resetPassword.hint", { min: MIN_PASSWORD_LENGTH })}</p>

        {passwordError && <Callout variant="danger">{passwordError}</Callout>}

        <Button type="submit" variant="accent" disabled={passwordMutation.isPending}>
          {t("profile.updatePassword")}
        </Button>
      </form>

      <div className={styles.card}>
        <h3>{t("profile.sessions")}</h3>
        <p className={styles.dangerText}>{t("profile.sessionsText")}</p>
        <Button
          variant="default"
          onClick={handleLogoutEverywhere}
          disabled={logoutEverywhereMutation.isPending}
        >
          {t("profile.logoutOtherDevices")}
        </Button>
      </div>

      <div className={styles.card}>
        <h3>{t("profile.deleteAccount")}</h3>
        <p className={styles.dangerText}>{t("profile.deleteAccountText")}</p>
        <Button variant="danger" onClick={handleDeleteAccount} disabled={deleteMutation.isPending}>
          {t("profile.deleteAccount")}
        </Button>
      </div>

      {toast.message && <Toast message={toast.message} onDismiss={toast.dismiss} />}
    </div>
  );
}

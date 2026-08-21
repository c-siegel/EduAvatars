import { useTranslation } from "react-i18next";
import { numberLocale } from "@/lib/format";
import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Credits.module.css";

// Screen — Credits
export function CreditsPage() {
  const { t } = useTranslation();
  return (
    <PublicLayout>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1>{t("credits.title")}</h1>
          <p className={styles.subtitle}>{t("credits.subtitle")}</p>
        </header>

        <section className={styles.section}>
          <h2>{t("credits.avatar.title")}</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>TalkingHead & HeadTTS</h3>
              <p className={styles.author}>{t("credits.byAuthor", { name: "Mika Suominen" })}</p>
              <p className={styles.description}>{t("credits.avatar.talkingHead.description")}</p>
              <div className={styles.links}>
                <a href="https://github.com/met4citizen/TalkingHead" target="_blank" rel="noopener noreferrer">
                  {t("credits.onGithub", { name: "TalkingHead" })}
                </a>
                <a href="https://github.com/met4citizen/HeadTTS" target="_blank" rel="noopener noreferrer">
                  {t("credits.onGithub", { name: "HeadTTS" })}
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>HeadAudio</h3>
              <p className={styles.author}>{t("credits.byAuthor", { name: "Mika Suominen" })}</p>
              <p className={styles.description}>{t("credits.avatar.headAudio.description")}</p>
              <div className={styles.links}>
                <a href="https://github.com/met4citizen/HeadAudio" target="_blank" rel="noopener noreferrer">
                  {t("credits.onGithub", { name: "HeadAudio" })}
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
              <div className={styles.note}>
                <strong>{t("credits.noteLabel")}</strong> {t("credits.avatar.headAudio.note")}
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("credits.fonts.title")}</h2>
          <div className={styles.content}>
            <p className={styles.intro}>{t("credits.fonts.intro")}</p>

            <div className={styles.creditItem}>
              <h3>Inter</h3>
              <p className={styles.author}>The Inter Project Authors</p>
              <p className={styles.description}>{t("credits.fonts.inter.description")}</p>
              <div className={styles.links}>
                <a href="https://github.com/rsms/inter" target="_blank" rel="noopener noreferrer">
                  {t("credits.onGithub", { name: "Inter" })}
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> SIL Open Font License 1.1
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Plus Jakarta Sans</h3>
              <p className={styles.author}>The Plus Jakarta Sans Project Authors</p>
              <p className={styles.description}>{t("credits.fonts.plusJakartaSans.description")}</p>
              <div className={styles.links}>
                <a href="https://github.com/tokotype/PlusJakartaSans" target="_blank" rel="noopener noreferrer">
                  {t("credits.onGithub", { name: "Plus Jakarta Sans" })}
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> SIL Open Font License 1.1
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>JetBrains Mono</h3>
              <p className={styles.author}>The JetBrains Mono Project Authors</p>
              <p className={styles.description}>{t("credits.fonts.jetBrainsMono.description")}</p>
              <div className={styles.links}>
                <a href="https://github.com/JetBrains/JetBrainsMono" target="_blank" rel="noopener noreferrer">
                  {t("credits.onGithub", { name: "JetBrains Mono" })}
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> SIL Open Font License 1.1
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("credits.frontend.title")}</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>React</h3>
              <p className={styles.author}>Meta (Facebook)</p>
              <p className={styles.description}>{t("credits.frontend.react.description")}</p>
              <div className={styles.links}>
                <a href="https://react.dev" target="_blank" rel="noopener noreferrer">
                  react.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>React Router</h3>
              <p className={styles.author}>Remix Software</p>
              <p className={styles.description}>{t("credits.frontend.reactRouter.description")}</p>
              <div className={styles.links}>
                <a href="https://reactrouter.com" target="_blank" rel="noopener noreferrer">
                  reactrouter.com
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Lucide React</h3>
              <p className={styles.author}>Lucide Contributors</p>
              <p className={styles.description}>{t("credits.frontend.lucideReact.description")}</p>
              <div className={styles.links}>
                <a href="https://lucide.dev" target="_blank" rel="noopener noreferrer">
                  lucide.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> ISC License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Vite</h3>
              <p className={styles.author}>Evan You & Vite Contributors</p>
              <p className={styles.description}>{t("credits.frontend.vite.description")}</p>
              <div className={styles.links}>
                <a href="https://vitejs.dev" target="_blank" rel="noopener noreferrer">
                  vitejs.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("credits.backend.title")}</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>FastAPI</h3>
              <p className={styles.author}>Sebastián Ramírez</p>
              <p className={styles.description}>{t("credits.backend.fastapi.description")}</p>
              <div className={styles.links}>
                <a href="https://fastapi.tiangolo.com" target="_blank" rel="noopener noreferrer">
                  fastapi.tiangolo.com
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>SQLModel</h3>
              <p className={styles.author}>Tiangolo</p>
              <p className={styles.description}>{t("credits.backend.sqlmodel.description")}</p>
              <div className={styles.links}>
                <a href="https://sqlmodel.tiangolo.com" target="_blank" rel="noopener noreferrer">
                  sqlmodel.tiangolo.com
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>faster-whisper</h3>
              <p className={styles.author}>Guillaume Klein</p>
              <p className={styles.description}>{t("credits.backend.fasterWhisper.description")}</p>
              <div className={styles.links}>
                <a href="https://github.com/SYSTRAN/faster-whisper" target="_blank" rel="noopener noreferrer">
                  {t("credits.onGithub", { name: "faster-whisper" })}
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Pydantic</h3>
              <p className={styles.author}>Pydantic Contributors</p>
              <p className={styles.description}>{t("credits.backend.pydantic.description")}</p>
              <div className={styles.links}>
                <a href="https://docs.pydantic.dev" target="_blank" rel="noopener noreferrer">
                  docs.pydantic.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>{t("credits.licenseLabel")}</strong> MIT License
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>{t("credits.privacy.title")}</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>Self-Hosting</h3>
              <p className={styles.description}>{t("credits.privacy.selfHosting.description")}</p>
            </div>
          </div>
        </section>

        <footer className={styles.footer}>
          <p>{t("credits.footer.thanks")}</p>
          <p className={styles.stand}>{t("imprint.asOf", { date: new Date().toLocaleDateString(numberLocale()) })}</p>
        </footer>
      </div>
    </PublicLayout>
  );
}

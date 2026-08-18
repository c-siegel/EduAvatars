import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Credits.module.css";

// Screen — Credits
export function CreditsPage() {
  return (
    <PublicLayout>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1>Credits & Lizenzen</h1>
          <p className={styles.subtitle}>
            Danksagung an alle Projekte und Bibliotheken, die EduAvatars möglich machen
          </p>
        </header>

        <section className={styles.section}>
          <h2>Avatar-Modell & Animation</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>TalkingHead & HeadTTS</h3>
              <p className={styles.author}>von Mika Suominen</p>
              <p className={styles.description}>
                3D-Avatar-Rendering und Audio-basiertes Lipsync für echtzeitfähige Animationen
              </p>
              <div className={styles.links}>
                <a
                  href="https://github.com/met4citizen/TalkingHead"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  TalkingHead auf GitHub
                </a>
                <a
                  href="https://github.com/met4citizen/HeadTTS"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  HeadTTS auf GitHub
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>HeadAudio</h3>
              <p className={styles.author}>von Mika Suominen</p>
              <p className={styles.description}>
                Echtzeitfähige, audio-basierte Viseme-Erkennung für präzises Lipsync
              </p>
              <div className={styles.links}>
                <a
                  href="https://github.com/met4citizen/HeadAudio"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  HeadAudio auf GitHub
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
              <div className={styles.note}>
                <strong>Hinweis:</strong> Das Modell wurde auf englischen Stimmen trainiert. Für
                deutschsprachiges Audio ist die Erkennungsqualität unverifiziert.
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Schriften</h2>
          <div className={styles.content}>
            <p className={styles.intro}>
              Alle Schriften werden selbst gehostet (statt über Google Fonts CDN) aus Datenschutzgründen.
            </p>

            <div className={styles.creditItem}>
              <h3>Inter</h3>
              <p className={styles.author}>The Inter Project Authors</p>
              <p className={styles.description}>
                Variable Font (Gewicht 100–900) für UI-Text und Überschriften
              </p>
              <div className={styles.links}>
                <a
                  href="https://github.com/rsms/inter"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Inter auf GitHub
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> SIL Open Font License 1.1
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Plus Jakarta Sans</h3>
              <p className={styles.author}>The Plus Jakarta Sans Project Authors</p>
              <p className={styles.description}>
                Variable Font (Gewicht 200–800) für moderne Typografie
              </p>
              <div className={styles.links}>
                <a
                  href="https://github.com/tokotype/PlusJakartaSans"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Plus Jakarta Sans auf GitHub
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> SIL Open Font License 1.1
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>JetBrains Mono</h3>
              <p className={styles.author}>The JetBrains Mono Project Authors</p>
              <p className={styles.description}>
                Variable Font (Gewicht 400–800) für Code und technische Inhalte
              </p>
              <div className={styles.links}>
                <a
                  href="https://github.com/JetBrains/JetBrainsMono"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  JetBrains Mono auf GitHub
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> SIL Open Font License 1.1
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Frontend-Frameworks & Bibliotheken</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>React</h3>
              <p className={styles.author}>Meta (Facebook)</p>
              <p className={styles.description}>
                JavaScript-Bibliothek für Benutzeroberflächen
              </p>
              <div className={styles.links}>
                <a href="https://react.dev" target="_blank" rel="noopener noreferrer">
                  react.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>React Router</h3>
              <p className={styles.author}>Remix Software</p>
              <p className={styles.description}>
                Routing-Bibliothek für Single-Page-Anwendungen
              </p>
              <div className={styles.links}>
                <a href="https://reactrouter.com" target="_blank" rel="noopener noreferrer">
                  reactrouter.com
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Lucide React</h3>
              <p className={styles.author}>Lucide Contributors</p>
              <p className={styles.description}>Sammlung von konsistenten, anpassbaren Icons</p>
              <div className={styles.links}>
                <a href="https://lucide.dev" target="_blank" rel="noopener noreferrer">
                  lucide.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> ISC License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Vite</h3>
              <p className={styles.author}>Evan You & Vite Contributors</p>
              <p className={styles.description}>
                Next-Generation Frontend Tooling für schnelles Development
              </p>
              <div className={styles.links}>
                <a href="https://vitejs.dev" target="_blank" rel="noopener noreferrer">
                  vitejs.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Backend-Frameworks & Bibliotheken</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>FastAPI</h3>
              <p className={styles.author}>Sebastián Ramírez</p>
              <p className={styles.description}>
                Modernes, schnelles Web-Framework für APIs mit Python
              </p>
              <div className={styles.links}>
                <a href="https://fastapi.tiangolo.com" target="_blank" rel="noopener noreferrer">
                  fastapi.tiangolo.com
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>SQLModel</h3>
              <p className={styles.author}>Tiangolo</p>
              <p className={styles.description}>
                SQL-Bibliothek für Python, basierend auf Pydantic und SQLAlchemy
              </p>
              <div className={styles.links}>
                <a href="https://sqlmodel.tiangolo.com" target="_blank" rel="noopener noreferrer">
                  sqlmodel.tiangolo.com
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>faster-whisper</h3>
              <p className={styles.author}>Guillaume Klein</p>
              <p className={styles.description}>
                Schnelle Implementierung von OpenAI Whisper für Spracherkennung
              </p>
              <div className={styles.links}>
                <a
                  href="https://github.com/SYSTRAN/faster-whisper"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  faster-whisper auf GitHub
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>

            <div className={styles.creditItem}>
              <h3>Pydantic</h3>
              <p className={styles.author}>Pydantic Contributors</p>
              <p className={styles.description}>
                Datenvalidierung mit Python Type Annotations
              </p>
              <div className={styles.links}>
                <a href="https://docs.pydantic.dev" target="_blank" rel="noopener noreferrer">
                  docs.pydantic.dev
                </a>
              </div>
              <div className={styles.license}>
                <strong>Lizenz:</strong> MIT License
              </div>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Datenschutz & Hosting</h2>
          <div className={styles.content}>
            <div className={styles.creditItem}>
              <h3>Self-Hosting</h3>
              <p className={styles.description}>
                Alle externen Ressourcen (Schriften, Avatare, Audio-Module) werden selbst gehostet,
                um die Privatsphäre der Nutzer zu schützen und keine Daten an externe CDNs zu senden.
              </p>
            </div>
          </div>
        </section>

        <footer className={styles.footer}>
          <p>
            Vielen Dank an alle Entwickler und Communities, die diese großartigen Open-Source-Projekte
            erstellt haben!
          </p>
          <p className={styles.stand}>Stand: {new Date().toLocaleDateString("de-DE")}</p>
        </footer>
      </div>
    </PublicLayout>
  );
}
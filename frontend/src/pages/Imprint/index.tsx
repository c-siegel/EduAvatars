import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Imprint.module.css";

// Screen — Impressum (Legal Notice)
export function ImprintPage() {
  return (
    <PublicLayout>
      <div className={styles.container}>
        <header className={styles.header}>
          <h1>Impressum</h1>
          <p className={styles.subtitle}>Rechtliche Angaben gemäß § 5 TMG</p>
        </header>

        <section className={styles.section}>
          <h2>Anbieter</h2>
          <div className={styles.content}>
            <p>
              <strong>Name:</strong> [noch ändern]
            </p>
            <p>
              <strong>Straße und Hausnummer:</strong> [noch ändern]
            </p>
            <p>
              <strong>PLZ, Ort:</strong> [noch ändern]
            </p>
            <p>
              <strong>Land:</strong> Deutschland
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Kontakt</h2>
          <div className={styles.content}>
            <p>
              <strong>E-Mail:</strong>{"noch ändern"}
              <a href="mailto:kontakt@beispiel.de">noch ändern@beispiel.de</a>
            </p>
            <p>
              <strong>Telefon:</strong> [+noch ändern]
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Verantwortlich für den Inhalt</h2>
          <div className={styles.content}>
            <p>
              <strong>Name:</strong> [noch ändern]
            </p>
            <p>
              <strong>E-Mail:</strong>{"noch ändern"}
              <a href="mailto:kontakt@beispiel.de">noch ändern@beispiel.de</a>
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Haftung für Inhalte</h2>
          <div className={styles.content}>
            <p>
              Als Diensteanbieter sind wir gemäß § 7 Abs.1 TMG für eigene Inhalte auf diesen Seiten nach den
              allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis 10 TMG sind wir als Diensteanbieter jedoch nicht
              verpflichtet, übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu
              forschen, die auf eine rechtswidrige Tätigkeit hinweisen.
            </p>
            <p>
              Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen nach den allgemeinen Gesetzen
              bleiben hiervon unberührt. Eine diesbezügliche Haftung ist jedoch erst ab dem Zeitpunkt der Kenntnis einer
              konkreten Rechtsverletzung möglich. Bei Bekanntwerden von entsprechenden Rechtsverletzungen werden wir
              diese Inhalte umgehend entfernen.
            </p>
          </div>
        </section>

        <section className={styles.section}>
          <h2>Haftung für Links</h2>
          <div className={styles.content}>
            <p>
              Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen Einfluss haben.
              Deshalb können wir für diese fremden Inhalte auch keine Gewähr übernehmen. Für die Inhalte der verlinkten
              Seiten ist stets der jeweilige Anbieter oder Betreiber der Seiten verantwortlich. Die verlinkten Seiten
              wurden zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstöße überprüft. Rechtswidrige Inhalte waren zum
              Zeitpunkt der Verlinkung nicht erkennbar.
            </p>
            <p>
              Eine permanente inhaltliche Kontrolle der verlinkten Seiten ist jedoch ohne konkrete Anhaltspunkte einer
              Rechtsverletzung nicht zumutbar. Bei Bekanntwerden von Rechtsverletzungen werden wir derartige Links umgehend
              entfernen.
            </p>
          </div>
        </section>
        
        <footer className={styles.footer}>
          <p>Stand: {new Date().toLocaleDateString("de-DE")}</p>
        </footer>
      </div>
    </PublicLayout>
  );
}
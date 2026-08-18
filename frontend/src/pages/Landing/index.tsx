import { useState } from "react";
import { UserCog, Share2, SlidersHorizontal } from "lucide-react";
import { ButtonLink } from "@/components/Button";
import { Badge } from "@/components/Badge";
import { Wordmark } from "@/components/Wordmark";
import { TalkingHeadAvatar } from "@/components/TalkingHeadAvatar";
import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Landing.module.css";

// Shared between the desktop nav and the mobile drawer so both stay in sync.
const NAV_ITEMS = [
  //{ label: "Features", href: "#" },
  { label: "Quellcode", href: "https://github.com/c-siegel/avatarhub2" },
];

// `full`/`short` give the two title variants shown at different breakpoints
// (see .featureTitleFull/.featureTitleShort in Landing.module.css).
const FEATURES = [
  {
    icon: UserCog,
    full: "Avatar konfigurieren",
    short: "Konfigurieren",
    text: "Wähle einen Avatar, formuliere seine Rolle, sein Aussehen und sein Verhalten.",
  },
  {
    icon: Share2,
    full: "Projekt publizieren",
    short: "Publizieren",
    text: "Ein Klick erzeugt einen Link, den deine Klasse ohne Login öffnen kann.",
  },
  {
    icon: SlidersHorizontal,
    full: "Volle Flexibilität",
    short: "API-Kontrolle",
    text: "Alle üblichen LLMs und Sprach-APIs sind flexibel nutzbar.",
  },
];

export function LandingPage() {
  // Controls the mobile nav drawer only; the desktop nav is always visible and
  // hidden/shown purely via the @media query in Landing.module.css.
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <PublicLayout>
      {/* Header: wordmark + desktop nav (hidden below 860px) + hamburger toggle (shown below 860px) */}
      <header className={styles.header}>
        <Wordmark />
        <nav className={styles.nav} aria-label="Hauptnavigation">
          <ul className={styles.navLinks}>
            {NAV_ITEMS.map((item) => (
              <li key={item.label}>
                <a href={item.href} {...(item.href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
          <div className={styles.headerActions}>
            <ButtonLink to="/login">Anmelden</ButtonLink>
            <ButtonLink to="/register" variant="accent">
              Kostenlos starten
            </ButtonLink>
          </div>
        </nav>
        {/* Hamburger button, CSS-only hidden on desktop; toggles the drawer below */}
        <button
          className={styles.menuButton}
          aria-label="Menü öffnen"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span />
          <span />
          <span />
        </button>
      </header>

      {/* Mobile nav drawer: same links/CTAs as the desktop nav, rendered only when toggled open */}
      {menuOpen && (
        <nav className={`${styles.mobileNav} ${styles.open}`} aria-label="Mobile Navigation">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.label}
              href={item.href}
              {...(item.href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            >
              {item.label}
            </a>
          ))}
          <ButtonLink to="/login">Anmelden</ButtonLink>
          <ButtonLink to="/register" variant="accent" fullWidth>
            Kostenlos starten
          </ButtonLink>
        </nav>
      )}

      {/* Hero: two-column on desktop (copy + image placeholder), stacked on mobile via CSS grid */}
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <Badge variant="accent">Für Lehrkräfte</Badge>
          <h1>
            {/* Two copy variants: the full headline on desktop, a shorter one on mobile
                (toggled purely via CSS display, see .headingFull/.headingShort) */}
            <span className={styles.headingFull}>Flexibel KI-Avatare erstellen.</span>
            <span className={styles.headingShort}>Flexible KI-Avatare.</span>
          </h1>
          <p>
            Erstelle einen KI-gestützten Lernavatar, formuliere seine Rolle in eigenen Worten und
            teile ihn per Link — ganz bequem ohne Programmierkenntnisse.
          </p>
          <div className={styles.heroActions}>
            <ButtonLink to="/register" variant="accent">
              Kostenlos starten
            </ButtonLink>
            <ButtonLink to="/login">Anmelden</ButtonLink>
          </div>
        </div>
        {/* 3D-Avatar (met4citizen/TalkingHead) statt eines statischen Bild-Mockups; zeigt den
            textuellen Platzhalter, solange das Modell lädt bzw. bei reduced-motion/Fehlern. */}
        <div className={styles.heroImage} aria-hidden="true">
          <TalkingHeadAvatar fallback="Avatar wird geladen..." />
        </div>
      </section>

      {/* Feature row: 3 cards, stacked on mobile; icon + title (long/short) + one-line description */}
      <section className={styles.features}>
        <div className={styles.featureGrid}>
          {FEATURES.map((feature) => (
            <div className={styles.featureCard} key={feature.full}>
              <div className={styles.featureIcon} aria-hidden="true">
                <feature.icon size={20} strokeWidth={2} />
              </div>
              <h3>
                <span className={styles.featureTitleFull}>{feature.full}</span>
                <span className={styles.featureTitleShort}>{feature.short}</span>
              </h3>
              <p>{feature.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer: copyright + legal links; "Kontakt" is dropped on mobile to save space */}
      <footer className={styles.footer}>
        <span>© EduAvatars</span>
        <nav className={styles.footerLinks} aria-label="Rechtliches">
          <a href="/datenschutz">Datenschutz</a>
          <span aria-hidden="true">·</span>
          <a href="/impressum">Impressum</a>
          <span aria-hidden="true" className={styles.footerLinksFull}>
            ·
          </span>
          <a href="/credits" className={styles.footerLinksFull}>
            Credits
          </a>
        </nav>
      </footer>
    </PublicLayout>
  );
}
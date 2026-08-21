import { useState } from "react";
import { useTranslation } from "react-i18next";
import { UserCog, Share2, SlidersHorizontal } from "lucide-react";
import { ButtonLink } from "@/components/Button";
import { Badge } from "@/components/Badge";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Wordmark } from "@/components/Wordmark";
import { TalkingHeadAvatar } from "@/components/TalkingHeadAvatar";
import { PublicLayout } from "@/layouts/PublicLayout";
import styles from "./Landing.module.css";

// Shared between the desktop nav and the mobile drawer so both stay in sync.
const NAV_ITEMS = [
  //{ labelKey: "landing.nav.features", href: "#" },
  { labelKey: "landing.nav.sourceCode", href: "https://github.com/c-siegel/EduAvatars" },
];

// `full`/`short` give the two title variants shown at different breakpoints
// (see .featureTitleFull/.featureTitleShort in Landing.module.css).
const FEATURES = [
  { icon: UserCog, key: "configure" },
  { icon: Share2, key: "publish" },
  { icon: SlidersHorizontal, key: "flexibility" },
] as const;

export function LandingPage() {
  const { t } = useTranslation();
  // Controls the mobile nav drawer only; the desktop nav is always visible and
  // hidden/shown purely via the @media query in Landing.module.css.
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <PublicLayout showLanguageSwitcher={false}>
      {/* Header: wordmark + desktop nav (hidden below 860px) + hamburger toggle (shown below 860px) */}
      <header className={styles.header}>
        <Wordmark />
        <nav className={styles.nav} aria-label={t("landing.nav.mainAriaLabel")}>
          <ul className={styles.navLinks}>
            {NAV_ITEMS.map((item) => (
              <li key={item.labelKey}>
                <a href={item.href} {...(item.href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
                  {t(item.labelKey)}
                </a>
              </li>
            ))}
          </ul>
          <div className={styles.headerActions}>
            <LanguageSwitcher />
            <ButtonLink to="/login">{t("common.login")}</ButtonLink>
            <ButtonLink to="/register" variant="accent">
              {t("landing.getStarted")}
            </ButtonLink>
          </div>
        </nav>
        {/* Hamburger button, CSS-only hidden on desktop; toggles the drawer below */}
        <button
          className={styles.menuButton}
          aria-label={t("landing.nav.openMenu")}
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
        <nav className={`${styles.mobileNav} ${styles.open}`} aria-label={t("landing.nav.mobileAriaLabel")}>
          {NAV_ITEMS.map((item) => (
            <a
              key={item.labelKey}
              href={item.href}
              {...(item.href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            >
              {t(item.labelKey)}
            </a>
          ))}
          <LanguageSwitcher />
          <ButtonLink to="/login">{t("common.login")}</ButtonLink>
          <ButtonLink to="/register" variant="accent" fullWidth>
            {t("landing.getStarted")}
          </ButtonLink>
        </nav>
      )}

      {/* Hero: two-column on desktop (copy + image placeholder), stacked on mobile via CSS grid */}
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <Badge variant="accent">{t("landing.badge")}</Badge>
          <h1>
            {/* Two copy variants: the full headline on desktop, a shorter one on mobile
                (toggled purely via CSS display, see .headingFull/.headingShort) */}
            <span className={styles.headingFull}>{t("landing.headingFull")}</span>
            <span className={styles.headingShort}>{t("landing.headingShort")}</span>
          </h1>
          <p>{t("landing.heroText")}</p>
          <div className={styles.heroActions}>
            <ButtonLink to="/register" variant="accent">
              {t("landing.getStarted")}
            </ButtonLink>
            <ButtonLink to="/login">{t("common.login")}</ButtonLink>
          </div>
        </div>
        {/* 3D-Avatar (met4citizen/TalkingHead) statt eines statischen Bild-Mockups; zeigt den
            textuellen Platzhalter, solange das Modell lädt bzw. bei reduced-motion/Fehlern. */}
        <div className={styles.heroImage} aria-hidden="true">
          <TalkingHeadAvatar fallback={t("landing.avatarLoading")} />
        </div>
      </section>

      {/* Feature row: 3 cards, stacked on mobile; icon + title (long/short) + one-line description */}
      <section className={styles.features}>
        <div className={styles.featureGrid}>
          {FEATURES.map((feature) => (
            <div className={styles.featureCard} key={feature.key}>
              <div className={styles.featureIcon} aria-hidden="true">
                <feature.icon size={20} strokeWidth={2} />
              </div>
              <h3>
                <span className={styles.featureTitleFull}>{t(`landing.features.${feature.key}.full`)}</span>
                <span className={styles.featureTitleShort}>{t(`landing.features.${feature.key}.short`)}</span>
              </h3>
              <p>{t(`landing.features.${feature.key}.text`)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer: copyright + legal links; "Kontakt" is dropped on mobile to save space */}
      <footer className={styles.footer}>
        <span>© EduAvatars</span>
        <nav className={styles.footerLinks} aria-label={t("landing.footer.legalAriaLabel")}>
          <a href="/datenschutz">{t("landing.footer.privacy")}</a>
          <span aria-hidden="true">·</span>
          <a href="/impressum">{t("landing.footer.imprint")}</a>
          <span aria-hidden="true" className={styles.footerLinksFull}>
            ·
          </span>
          <a href="/credits" className={styles.footerLinksFull}>
            {t("landing.footer.credits")}
          </a>
        </nav>
      </footer>
    </PublicLayout>
  );
}
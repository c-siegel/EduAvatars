import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Pencil, Link2, MoreHorizontal } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Badge } from "@/components/Badge";
import type { Project } from "@/types/project";
import { formatRelativeDate } from "@/lib/time";
import styles from "./ProjectCard.module.css";

export function ProjectCard({ project }: { project: Project }) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close the mobile "…" menu on outside click.
  useEffect(() => {
    if (!menuOpen) return;
    function handleClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  const shareUrl = project.shareSlug ? `${window.location.origin}/c/${project.shareSlug}` : null;

  function copyLink() {
    if (shareUrl) navigator.clipboard.writeText(shareUrl);
    setMenuOpen(false);
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <Avatar name={project.title} size="md" />
        <Badge variant={project.published ? "accent" : "default"}>
          {project.published ? t("overview.card.published") : t("overview.card.draft")}
        </Badge>
      </div>

      <div>
        <h3 className={styles.title}>{project.title}</h3>
        <p className={styles.modelHint}>{project.llmModel ?? t("overview.card.noModel")}</p>
      </div>

      <div className={styles.footer}>
        <span className={styles.lastActive}>
          {t("overview.card.lastActive", { relative: formatRelativeDate(project.createdAt) })}
        </span>

        {/* Desktop: both actions visible directly, plus a "…" reserved for future actions (e.g. Löschen) */}
        <div className={styles.actionsDesktop}>
          <Link
            className={styles.iconButton}
            to={`/dashboard/projects/${project.id}`}
            aria-label={t("overview.card.edit")}
            title={t("overview.card.edit")}
          >
            <Pencil size={16} />
          </Link>
          <button
            className={styles.iconButton}
            onClick={copyLink}
            disabled={!shareUrl}
            aria-label={t("overview.card.copyLink")}
            title={shareUrl ? t("overview.card.copyLink") : t("overview.card.notPublishedYet")}
          >
            <Link2 size={16} />
          </button>
          <button
            className={styles.iconButton}
            disabled
            aria-label={t("overview.card.moreActions")}
            title={t("overview.card.comingSoon")}
          >
            <MoreHorizontal size={16} />
          </button>
        </div>

        {/* Mobile: same two actions condensed behind a single working "…" menu */}
        <div className={styles.menuWrapper} ref={menuRef}>
          <button
            className={styles.iconButton}
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={t("overview.card.moreActions")}
            aria-expanded={menuOpen}
          >
            <MoreHorizontal size={16} />
          </button>
          {menuOpen && (
            <div className={styles.menu} role="menu">
              <Link className={styles.menuItem} to={`/dashboard/projects/${project.id}`} role="menuitem">
                <Pencil size={14} /> {t("overview.card.edit")}
              </Link>
              <button className={styles.menuItem} onClick={copyLink} disabled={!shareUrl} role="menuitem">
                <Link2 size={14} /> {t("overview.card.copyLink")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Tile } from "@/components/Tile";
import { Callout } from "@/components/Callout";
import { projectsApi } from "@/api/projects";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { ProjectCard } from "./ProjectCard";
import styles from "./Overview.module.css";

type Filter = "all" | "draft" | "published";

// Screen 1d — Tab Übersicht
export function OverviewPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const statsQuery = useQuery({ queryKey: ["projects", "stats"], queryFn: projectsApi.stats });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const [filter, setFilter] = useState<Filter>("all");

  const createProject = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/dashboard/projects/${project.id}`);
    },
  });

  const projects = projectsQuery.data ?? [];
  const filteredProjects = projects.filter((project) => {
    if (filter === "draft") return !project.published;
    if (filter === "published") return project.published;
    return true;
  });

  return (
    <div className={styles.page}>
      <div className={styles.greetingRow}>
        <div>
          {/* Wireframe zeigt "Hallo Frau Berger 👋" — ohne Anrede-/Geschlechtsfeld im User-Modell
              verwenden wir hier schlicht den registrierten Namen. */}
          <h1>{t("overview.greeting", { name: user?.name ?? "…" })}</h1>
          <p className={styles.subtitle}>
            {statsQuery.data
              ? t("overview.subtitle", {
                  total: statsQuery.data.totalProjects,
                  published: statsQuery.data.publishedProjects,
                })
              : "…"}
          </p>
        </div>
        <Button variant="accent" onClick={() => createProject.mutate()} disabled={createProject.isPending}>
          {t("overview.newProject")}
        </Button>
      </div>

      {createProject.isError && <Callout variant="danger">{t("overview.createError")}</Callout>}

      <div className={styles.statGrid}>
        <Tile label={t("overview.stats.projects")} value={statsQuery.data?.totalProjects ?? "–"} />
        <Tile label={t("overview.stats.published")} value={statsQuery.data?.publishedProjects ?? "–"} />
        <Tile label={t("overview.stats.sessions7d")} value={statsQuery.data?.sessionsLast7Days ?? "–"} />
        <Tile label={t("overview.stats.messages")} value={statsQuery.data?.messagesLast7Days ?? "–"} />
      </div>

      <div>
        <div className={styles.sectionHeader}>
          <h2>{t("overview.myProjects")}</h2>
          <div className={styles.filters}>
            <button
              className={`${styles.filterButton} ${filter === "all" ? styles.filterActive : ""}`}
              onClick={() => setFilter("all")}
            >
              {t("overview.filters.all")}
            </button>
            <span aria-hidden="true">·</span>
            <button
              className={`${styles.filterButton} ${filter === "draft" ? styles.filterActive : ""}`}
              onClick={() => setFilter("draft")}
            >
              {t("overview.filters.draft")}
            </button>
            <span aria-hidden="true">·</span>
            <button
              className={`${styles.filterButton} ${filter === "published" ? styles.filterActive : ""}`}
              onClick={() => setFilter("published")}
            >
              {t("overview.filters.published")}
            </button>
          </div>
        </div>

        <div className={styles.projectGrid}>
          {filteredProjects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
          <button className={styles.newProjectTile} onClick={() => createProject.mutate()}>
            {t("overview.newProject")}
          </button>
        </div>
      </div>
    </div>
  );
}

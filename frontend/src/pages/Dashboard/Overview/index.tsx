import { useRef, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Upload } from "lucide-react";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { projectsApi } from "@/api/projects";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { ProjectRow } from "./ProjectRow";
import styles from "./Overview.module.css";

type Filter = "all" | "draft" | "published";

const TABS: { id: Filter; labelKey: string }[] = [
  { id: "all", labelKey: "overview.filters.all" },
  { id: "published", labelKey: "overview.filters.published" },
  { id: "draft", labelKey: "overview.filters.draft" },
];

// Screen 1d — overview tab
export function OverviewPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: user } = useCurrentUser();
  const statsQuery = useQuery({ queryKey: ["projects", "stats"], queryFn: projectsApi.stats });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const [filter, setFilter] = useState<Filter>("all");
  const importInputRef = useRef<HTMLInputElement>(null);

  const createProject = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/dashboard/projects/${project.id}`);
    },
  });

  const importProject = useMutation({
    mutationFn: (file: File) => projectsApi.importYaml(file),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/dashboard/projects/${project.id}`);
    },
  });

  function handleImportFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Reset right away so picking the same file again (e.g. after fixing it) still fires onChange.
    event.target.value = "";
    if (file) importProject.mutate(file);
  }

  const projects = projectsQuery.data ?? [];
  const filteredProjects = projects.filter((project) => {
    if (filter === "draft") return !project.published;
    if (filter === "published") return project.published;
    return true;
  });

  const counts: Record<Filter, number> = {
    all: projects.length,
    published: projects.filter((project) => project.published).length,
    draft: projects.filter((project) => !project.published).length,
  };

  return (
    <div className={styles.page}>
      <div className={styles.greetingRow}>
        <div>
          {/* The wireframe shows "Hallo Frau Berger 👋" — without a salutation/gender field in the
              user model we simply use the registered name here. */}
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
        <div className={styles.headerActions}>
          <Button
            onClick={() => importInputRef.current?.click()}
            disabled={importProject.isPending}
          >
            <Upload size={16} /> {t("overview.importProject")}
          </Button>
          <input
            ref={importInputRef}
            type="file"
            accept=".yml,.yaml"
            hidden
            onChange={handleImportFileChange}
          />
          <Button variant="accent" onClick={() => createProject.mutate()} disabled={createProject.isPending}>
            {t("overview.newProject")}
          </Button>
        </div>
      </div>

      {createProject.isError && <Callout variant="danger">{t("overview.createError")}</Callout>}
      {importProject.isError && <Callout variant="danger">{t("overview.importError")}</Callout>}

      <div className={styles.activityStrip}>
        <span>
          {t("overview.stats.sessions7d")}: <strong>{statsQuery.data?.sessionsLast7Days ?? "–"}</strong>
        </span>
        <span>
          {t("overview.stats.messages")}: <strong>{statsQuery.data?.messagesLast7Days ?? "–"}</strong>
        </span>
      </div>

      <div className={styles.projects}>
        <div className={styles.tabs} role="tablist" aria-label={t("overview.myProjects")}>
          {TABS.map(({ id, labelKey }) => (
            <button
              key={id}
              role="tab"
              id={`overview-tab-${id}`}
              aria-selected={filter === id}
              aria-controls="overview-projects-panel"
              className={`${styles.tab} ${filter === id ? styles.tabActive : ""}`}
              onClick={() => setFilter(id)}
            >
              {t(labelKey)} <span className={styles.tabCount}>{counts[id]}</span>
            </button>
          ))}
        </div>

        <div
          className={styles.tableWrapper}
          role="tabpanel"
          id="overview-projects-panel"
          aria-labelledby={`overview-tab-${filter}`}
        >
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{t("overview.table.project")}</th>
                <th scope="col">{t("overview.table.model")}</th>
                <th scope="col">{t("overview.table.status")}</th>
                <th scope="col">{t("overview.table.created")}</th>
                <th scope="col">
                  <span className={styles.srOnly}>{t("overview.table.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredProjects.map((project) => (
                <ProjectRow key={project.id} project={project} />
              ))}
              {filteredProjects.length === 0 && !projectsQuery.isPending && (
                <tr>
                  <td colSpan={5} className={styles.empty}>
                    {t("overview.empty")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

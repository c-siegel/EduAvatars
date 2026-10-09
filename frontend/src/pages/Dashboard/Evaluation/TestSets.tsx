// The "Test questions" tab of the Answer quality page: test sets per knowledge base. Questions are
// written by hand, imported from CSV, or drafted by a judge LLM — drafts only count once the
// teacher approves them. Each question has a kind that decides what it measures:
//   grounded  drafted from a passage of the material: does retrieval find it?
//   topic     asked about the subject without knowing the material: which gaps does it have?
//   offtopic  outside the subject: does the avatar admit what it doesn't know?

import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Check, Download, Pencil, Sparkles, Trash2, Upload, X } from "lucide-react";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { apiKeysApi } from "@/api/apiKeys";
import { errorMessage } from "@/api/client";
import {
  QUESTION_KINDS,
  evaluationApi,
  type EvaluationStatus,
  type QuestionKind,
  type TestCase,
  type TestSet,
} from "@/api/evaluation";
import { knowledgeApi, type KnowledgeBase } from "@/api/knowledge";
import { projectsApi } from "@/api/projects";
import { isJudgeKey, keyDisplayName, useProviders } from "@/lib/providers";
// The test set classes live next to the knowledge page's: same look for the same kind of form.
import styles from "../Knowledge/Knowledge.module.css";

/** The tab: pick a knowledge base, then work on its test sets. */
export function TestQuestions({ status }: { status: EvaluationStatus }) {
  const { t } = useTranslation();
  const kbQuery = useQuery({ queryKey: ["knowledge-bases"], queryFn: knowledgeApi.list });
  const knowledgeBases = kbQuery.data ?? [];
  const [kbId, setKbId] = useState("");
  const kb = knowledgeBases.find((k) => k.id === kbId) ?? knowledgeBases[0];

  if (kbQuery.isLoading) return <p className={styles.hint}>{t("common.loading")}</p>;
  if (!kb) {
    return (
      <div className={styles.card}>
        <h3>{t("testSets.title")}</h3>
        <p className={styles.hint}>{t("testSets.noKnowledgeBase")}</p>
      </div>
    );
  }
  return (
    <div className={styles.card}>
      <h3>{t("testSets.title")}</h3>
      <p className={styles.hint}>{t("testSets.hint")}</p>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="test-kb">
          {t("testSets.knowledgeBase")}
        </label>
        <select id="test-kb" className={styles.select} value={kb.id} onChange={(e) => setKbId(e.target.value)}>
          {knowledgeBases.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
        </select>
      </div>
      <TestSets key={kb.id} kb={kb} status={status} />
    </div>
  );
}

function TestSets({ kb, status }: { kb: KnowledgeBase; status: EvaluationStatus }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const setsQuery = useQuery({ queryKey: ["test-sets", kb.id], queryFn: () => evaluationApi.testSets(kb.id) });
  const testSets = setsQuery.data ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState<"de" | "en">("de");
  const selected = testSets.find((s) => s.id === selectedId) ?? testSets[0];

  const createMutation = useMutation({
    mutationFn: () => evaluationApi.createTestSet(kb.id, name.trim(), language),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ["test-sets"] });
      setName("");
      setSelectedId(created.id);
    },
  });

  function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  return (
    <>
      {testSets.length > 0 && (
        <div className={styles.field}>
          <label className={styles.label} htmlFor={`test-set-${kb.id}`}>
            {t("testSets.choose")}
          </label>
          <select
            id={`test-set-${kb.id}`}
            className={styles.select}
            value={selected?.id ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            {testSets.map((s) => (
              <option key={s.id} value={s.id}>
                {t("testSets.option", { name: s.name, count: s.caseCount, approved: s.approvedCount })}
              </option>
            ))}
          </select>
        </div>
      )}
      <form className={styles.searchRow} onSubmit={handleCreate}>
        <input
          className={styles.searchInput}
          value={name}
          maxLength={100}
          placeholder={t("testSets.namePlaceholder")}
          aria-label={t("testSets.name")}
          onChange={(e) => setName(e.target.value)}
        />
        <select
          className={`${styles.select} ${styles.selectInline}`}
          value={language}
          aria-label={t("testSets.language")}
          onChange={(e) => setLanguage(e.target.value as "de" | "en")}
        >
          <option value="de">{t("testSets.languageDe")}</option>
          <option value="en">{t("testSets.languageEn")}</option>
        </select>
        <Button type="submit" size="sm" disabled={!name.trim() || createMutation.isPending}>
          {t("testSets.create")}
        </Button>
      </form>
      {createMutation.isError && (
        <Callout variant="danger">{errorMessage(createMutation.error, t("testSets.saveFailed"))}</Callout>
      )}
      {selected && <TestSetDetail key={selected.id} testSet={selected} status={status} />}
    </>
  );
}

function TestSetDetail({ testSet, status }: { testSet: TestSet; status: EvaluationStatus }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const casesQuery = useQuery({ queryKey: ["test-cases", testSet.id], queryFn: () => evaluationApi.cases(testSet.id) });
  const cases = casesQuery.data ?? [];
  const drafts = cases.filter((c) => !c.approved);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [inputKey, setInputKey] = useState(0);

  function refresh() {
    queryClient.invalidateQueries({ queryKey: ["test-cases", testSet.id] });
    queryClient.invalidateQueries({ queryKey: ["test-sets"] });
  }

  const importMutation = useMutation({
    mutationFn: (file: File) => evaluationApi.importCsv(testSet.id, file),
    onSuccess: (result) => {
      setImportResult(t("testSets.imported", { imported: result.imported, skipped: result.skipped }));
      setInputKey((key) => key + 1);
      refresh();
    },
  });
  const removeMutation = useMutation({
    mutationFn: () => evaluationApi.removeTestSet(testSet.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["test-sets"] });
      queryClient.invalidateQueries({ queryKey: ["evaluation-runs"] });
    },
  });
  const discardMutation = useMutation({ mutationFn: () => evaluationApi.discardDrafts(testSet.id), onSuccess: refresh });

  return (
    <div className={styles.detail}>
      <div className={styles.retryRow}>
        <label className={styles.fileButton}>
          <Upload size={14} /> {t("testSets.importCsv")}
          <input
            key={inputKey}
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importMutation.mutate(file);
            }}
          />
        </label>
        <Button size="sm" onClick={() => evaluationApi.exportCsv(testSet.id)} disabled={testSet.approvedCount === 0}>
          <Download size={14} /> {t("testSets.exportCsv")}
        </Button>
        <Button
          size="sm"
          onClick={() => {
            if (window.confirm(t("testSets.removeConfirm", { name: testSet.name }))) removeMutation.mutate();
          }}
          disabled={removeMutation.isPending}
        >
          <Trash2 size={14} /> {t("testSets.remove")}
        </Button>
      </div>
      <p className={styles.hint}>{t("testSets.csvHint")}</p>
      {importResult && <Callout variant="success">{importResult}</Callout>}
      {importMutation.isError && (
        <Callout variant="danger">{errorMessage(importMutation.error, t("testSets.importFailed"))}</Callout>
      )}
      {removeMutation.isError && (
        <Callout variant="danger">{errorMessage(removeMutation.error, t("testSets.saveFailed"))}</Callout>
      )}

      <DraftQuestions testSet={testSet} status={status} onDrafted={refresh} />
      {drafts.length > 0 && (
        <Callout variant="info">
          {t("testSets.draftsPending", { count: drafts.length })}{" "}
          <Button size="sm" onClick={() => discardMutation.mutate()} disabled={discardMutation.isPending}>
            {t("testSets.discardDrafts")}
          </Button>
        </Callout>
      )}

      <AddCase testSet={testSet} onAdded={refresh} />
      {casesQuery.isLoading && <p className={styles.hint}>{t("common.loading")}</p>}
      {!casesQuery.isLoading && cases.length === 0 && <p className={styles.hint}>{t("testSets.noCases")}</p>}
      {cases.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t("testSets.question")}</th>
                <th>{t("testSets.reference")}</th>
                <th aria-label={t("knowledge.table.actions")} />
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <CaseRow key={c.id} testCase={c} onChanged={refresh} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function KindSelect({
  id,
  value,
  onChange,
  label,
}: {
  id: string;
  value: QuestionKind;
  onChange: (kind: QuestionKind) => void;
  label: string;
}) {
  const { t } = useTranslation();
  return (
    <select
      id={id}
      className={`${styles.select} ${styles.selectInline}`}
      value={value}
      aria-label={label}
      onChange={(e) => onChange(e.target.value as QuestionKind)}
    >
      {QUESTION_KINDS.map((kind) => (
        <option key={kind} value={kind}>
          {t(`testSets.kind.${kind}`)}
        </option>
      ))}
    </select>
  );
}

/** Draft questions with the judge LLM: from the material, or about the subject without it. */
function DraftQuestions({
  testSet,
  status,
  onDrafted,
}: {
  testSet: TestSet;
  status: EvaluationStatus;
  onDrafted: () => void;
}) {
  const { t } = useTranslation();
  const specs = useProviders().data ?? [];
  const keysQuery = useQuery({ queryKey: ["api-keys"], queryFn: apiKeysApi.list });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
  const judgeKeys = (keysQuery.data ?? []).filter(isJudgeKey);
  const projects = projectsQuery.data ?? [];
  const [kind, setKind] = useState<QuestionKind>("topic");
  const [keyId, setKeyId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [objectives, setObjectives] = useState("");
  const size = status.maxDraftsPerRequest ?? 10;
  const effectiveKey = keyId || judgeKeys[0]?.id || "";
  const effectiveProject = projectId || projects[0]?.id || "";
  const needsProject = kind !== "grounded";

  const generateMutation = useMutation({
    mutationFn: () =>
      evaluationApi.generate(testSet.id, {
        judgeApiKeyId: effectiveKey,
        size,
        kind,
        ...(needsProject ? { projectId: effectiveProject } : {}),
        ...(kind === "topic" && objectives.trim() ? { objectives: objectives.trim() } : {}),
      }),
    onSuccess: onDrafted,
  });

  if (judgeKeys.length === 0) return <p className={styles.hint}>{t("testSets.noJudgeKey")}</p>;
  return (
    <div className={styles.upload}>
      <h4>{t("testSets.draftTitle")}</h4>
      <div className={styles.searchRow}>
        <KindSelect id={`draft-kind-${testSet.id}`} value={kind} onChange={setKind} label={t("testSets.draftKind")} />
        {needsProject && (
          <select
            className={`${styles.select} ${styles.selectInline}`}
            value={effectiveProject}
            aria-label={t("testSets.draftProject")}
            onChange={(e) => setProjectId(e.target.value)}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        )}
        <select
          className={`${styles.select} ${styles.selectInline}`}
          value={effectiveKey}
          aria-label={t("evaluation.judgeKey")}
          onChange={(e) => setKeyId(e.target.value)}
        >
          {judgeKeys.map((key) => (
            <option key={key.id} value={key.id}>
              {keyDisplayName(key, specs)} · {key.modelId}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending || (needsProject && !effectiveProject)}
        >
          <Sparkles size={14} /> {generateMutation.isPending ? t("testSets.drafting") : t("testSets.draft", { count: size })}
        </Button>
      </div>
      {kind === "topic" && (
        <textarea
          className={styles.textarea}
          rows={2}
          maxLength={2000}
          value={objectives}
          placeholder={t("testSets.objectivesPlaceholder")}
          aria-label={t("testSets.objectives")}
          onChange={(e) => setObjectives(e.target.value)}
        />
      )}
      <p className={styles.hint}>{t(`testSets.kindHint.${kind}`, { count: size })}</p>
      {generateMutation.isError && (
        <Callout variant="danger">{errorMessage(generateMutation.error, t("testSets.draftFailed"))}</Callout>
      )}
    </div>
  );
}

function AddCase({ testSet, onAdded }: { testSet: TestSet; onAdded: () => void }) {
  const { t } = useTranslation();
  const [question, setQuestion] = useState("");
  const [reference, setReference] = useState("");
  const [kind, setKind] = useState<QuestionKind>("topic");
  const addMutation = useMutation({
    mutationFn: () => evaluationApi.addCase(testSet.id, question.trim(), reference.trim() || null, kind),
    onSuccess: () => {
      setQuestion("");
      setReference("");
      onAdded();
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (question.trim()) addMutation.mutate();
  }

  return (
    <form className={styles.upload} onSubmit={handleSubmit}>
      <h4>{t("testSets.addTitle")}</h4>
      <textarea
        className={styles.textarea}
        rows={2}
        maxLength={4000}
        value={question}
        placeholder={t("testSets.questionPlaceholder")}
        aria-label={t("testSets.question")}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <textarea
        className={styles.textarea}
        rows={2}
        maxLength={8000}
        value={reference}
        placeholder={t("testSets.referencePlaceholder")}
        aria-label={t("testSets.reference")}
        onChange={(e) => setReference(e.target.value)}
      />
      {addMutation.isError && (
        <Callout variant="danger">{errorMessage(addMutation.error, t("testSets.saveFailed"))}</Callout>
      )}
      <div className={styles.searchRow}>
        <KindSelect id={`add-kind-${testSet.id}`} value={kind} onChange={setKind} label={t("testSets.draftKind")} />
        <Button type="submit" size="sm" disabled={!question.trim() || addMutation.isPending}>
          {t("testSets.addCase")}
        </Button>
      </div>
    </form>
  );
}

function CaseRow({ testCase, onChanged }: { testCase: TestCase; onChanged: () => void }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [question, setQuestion] = useState(testCase.question);
  const [reference, setReference] = useState(testCase.reference ?? "");
  const [kind, setKind] = useState<QuestionKind>(testCase.kind);

  const updateMutation = useMutation({
    mutationFn: (data: { question?: string; reference?: string | null; approved?: boolean; kind?: QuestionKind }) =>
      evaluationApi.updateCase(testCase.id, data),
    onSuccess: () => {
      setEditing(false);
      onChanged();
    },
  });
  const removeMutation = useMutation({ mutationFn: () => evaluationApi.removeCase(testCase.id), onSuccess: onChanged });

  if (editing) {
    return (
      <tr>
        <td>
          <textarea
            className={styles.textarea}
            rows={3}
            maxLength={4000}
            value={question}
            aria-label={t("testSets.question")}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <KindSelect id={`kind-${testCase.id}`} value={kind} onChange={setKind} label={t("testSets.draftKind")} />
        </td>
        <td>
          <textarea
            className={styles.textarea}
            rows={3}
            maxLength={8000}
            value={reference}
            aria-label={t("testSets.reference")}
            onChange={(e) => setReference(e.target.value)}
          />
        </td>
        <td className={styles.rowActions}>
          <Button
            size="sm"
            variant="accent"
            onClick={() => updateMutation.mutate({ question: question.trim(), reference: reference.trim() || null, kind })}
            disabled={!question.trim() || updateMutation.isPending}
            aria-label={t("testSets.save")}
            title={t("testSets.save")}
          >
            <Check size={14} />
          </Button>
          <Button size="sm" onClick={() => setEditing(false)} aria-label={t("testSets.cancel")} title={t("testSets.cancel")}>
            <X size={14} />
          </Button>
        </td>
      </tr>
    );
  }

  return (
    <tr className={testCase.approved ? undefined : styles.draftRow}>
      <td>
        <span className={styles.cellText}>{testCase.question}</span>
        <span className={styles.badges}>
          <Badge title={t(`testSets.kindHint.${testCase.kind}`, { count: 10 })}>{t(`testSets.kind.${testCase.kind}`)}</Badge>
          <Badge variant={testCase.approved ? "default" : "accent"}>
            {testCase.approved ? t(`testSets.origin.${testCase.origin}`) : t("testSets.draftBadge")}
          </Badge>
        </span>
      </td>
      <td>
        <span className={styles.cellText}>{testCase.reference ?? <em className={styles.hint}>{t("testSets.noReference")}</em>}</span>
      </td>
      <td className={styles.rowActions}>
        {!testCase.approved && (
          <Button
            size="sm"
            variant="accent"
            onClick={() => updateMutation.mutate({ approved: true })}
            disabled={updateMutation.isPending}
          >
            <Check size={14} /> {t("testSets.approve")}
          </Button>
        )}
        <Button size="sm" onClick={() => setEditing(true)} aria-label={t("testSets.edit")} title={t("testSets.edit")}>
          <Pencil size={14} />
        </Button>
        <Button
          size="sm"
          onClick={() => removeMutation.mutate()}
          disabled={removeMutation.isPending}
          aria-label={t("testSets.removeCase")}
          title={t("testSets.removeCase")}
        >
          <Trash2 size={14} />
        </Button>
      </td>
    </tr>
  );
}

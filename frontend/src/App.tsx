import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCheck,
  ChevronRight,
  ClipboardList,
  Clock3,
  Database,
  FileCheck2,
  FileSearch,
  FlaskConical,
  History as HistoryIcon,
  Inbox,
  LoaderCircle,
  MessageSquareText,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import type {
  Case,
  Catalog,
  Evaluation,
  History,
  Investigation,
  Result,
  Review,
  Settings,
  Source,
} from "./types";

const pages = [
  { id: "inbox", label: "Case inbox", icon: Inbox },
  { id: "case", label: "Investigation", icon: FileSearch },
  { id: "library", label: "Evidence library", icon: BookOpen },
  { id: "history", label: "Draft history", icon: HistoryIcon },
  { id: "evaluation", label: "Evaluation lab", icon: FlaskConical },
  { id: "method", label: "Method & audit", icon: ShieldCheck },
];
const timestamp = (value: string) =>
  new Date(value).toLocaleString("en-GB", {
    timeZone: "UTC",
    dateStyle: "medium",
    timeStyle: "short",
  });
const human = (value: string) => value.replaceAll("_", " ");
const pageFromHash = () =>
  pages.some((p) => p.id === location.hash.slice(1))
    ? location.hash.slice(1)
    : "inbox";

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api${path}`,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const data = await response.json();
      message =
        typeof data.detail === "string"
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail
                .map(
                  (e: { loc: string[]; msg: string }) =>
                    `${e.loc.slice(1).join(".")}: ${e.msg}`,
                )
                .join(" · ")
            : message;
    } catch {}
    throw new Error(message);
  }
  return response.json();
}
function Tag({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`tag ${tone}`}>{children}</span>;
}
function Table({ children }: { children: React.ReactNode }) {
  return (
    <div className="table-scroll">
      <table>{children}</table>
    </div>
  );
}
function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="metric">
      <div className="metric-label">
        {label}
        <span>{icon}</span>
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <FileSearch size={34} />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
function draftLabel(run: Investigation) {
  const g = run.generation;
  if (g.state === "not_requested") return "Evidence search only";
  if (g.state === "unavailable") return "Local AI unavailable";
  if (g.state === "withheld") return "Draft withheld";
  return g.draft?.status === "insufficient"
    ? "Model abstained"
    : g.draft?.status === "conflict"
      ? "Model flagged a conflict"
      : "Model selected supporting quotes";
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [page, setPage] = useState(pageFromHash),
    [settings, setSettings] = useState<Settings | null>(null);
  const [result, setResult] = useState<Result | null>(null),
    [history, setHistory] = useState<History[]>([]),
    [evaluation, setEvaluation] = useState<Evaluation>({ ready: false });
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [caseFilter, setCaseFilter] = useState(""),
    [severity, setSeverity] = useState("All"),
    [libraryFilter, setLibraryFilter] = useState("");
  const [sourceId, setSourceId] = useState(""),
    [quote, setQuote] = useState(""),
    [note, setNote] = useState(""),
    [disposition, setDisposition] = useState("needs_follow_up");
  const [reviewBusy, setReviewBusy] = useState(false),
    [evidenceTab, setEvidenceTab] = useState("passages");
  useEffect(() => {
    Promise.all([
      api<Catalog>("/catalog"),
      api<History[]>("/investigations"),
      api<Evaluation>("/evaluation"),
    ])
      .then(([data, saved, assessment]) => {
        setCatalog(data);
        setHistory(saved);
        setEvaluation(assessment);
        const first = data.corpus.cases[0];
        setSettings({
          case_id: first.id,
          question: first.suggested_question,
          mode: "local_ai",
          model: data.release.model,
          prompt_version: data.release.prompt_version,
        });
        setSourceId(first.timeline[0].source_id);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    const changed = () => {
      if (pages.some((p) => p.id === location.hash.slice(1)))
        setPage(location.hash.slice(1));
    };
    addEventListener("hashchange", changed);
    return () => removeEventListener("hashchange", changed);
  }, []);
  function go(id: string) {
    location.hash = id;
    setPage(id);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  function choose(c: Case) {
    if (!settings) return;
    setSettings({ ...settings, case_id: c.id, question: c.suggested_question });
    setResult(null);
    setSourceId(c.timeline[0].source_id);
    setQuote("");
    setNote("");
    setError("");
    go("case");
  }
  function change<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((old) => (old ? { ...old, [key]: value } : old));
  }
  async function run() {
    if (!settings) return;
    setBusy(true);
    setError("");
    const snapshot = { ...settings };
    try {
      const next = await api<Result>("/investigations", snapshot);
      setResult(next);
      setNote("");
      setEvidenceTab("passages");
      const first = next.investigation.generation.draft?.evidence[0];
      setSourceId(
        first?.passage_id.split(":")[0] ??
          next.investigation.retrieved[0]?.document_id ??
          "",
      );
      setQuote(first?.quote ?? "");
      setHistory(await api<History[]>("/investigations"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Investigation failed.");
    } finally {
      setBusy(false);
    }
  }
  async function open(id: string) {
    setBusy(true);
    setError("");
    try {
      const next = await api<Result>(`/investigations/${id}`);
      setResult(next);
      setSettings({ ...next.investigation.request });
      setSourceId(
        next.investigation.generation.draft?.evidence[0]?.passage_id.split(
          ":",
        )[0] ??
          next.investigation.retrieved[0]?.document_id ??
          "",
      );
      setQuote(next.investigation.generation.draft?.evidence[0]?.quote ?? "");
      setNote("");
      go("case");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not open this investigation.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function saveReview(event: React.FormEvent) {
    event.preventDefault();
    if (!result) return;
    setReviewBusy(true);
    setError("");
    try {
      const reviews = await api<Review[]>(
        `/investigations/${result.investigation.id}/reviews`,
        { disposition, note },
      );
      setResult({ ...result, reviews });
      setNote("");
      setHistory(await api<History[]>("/investigations"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the note.");
    } finally {
      setReviewBusy(false);
    }
  }
  async function refreshModel() {
    if (!catalog) return;
    try {
      const model_status = await api<Catalog["model_status"]>("/model-status");
      setCatalog({ ...catalog, model_status });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status unavailable.");
    }
  }
  if (loading)
    return (
      <div className="boot">
        <LoaderCircle className="spin" />
        <p>Opening the evidence desk…</p>
      </div>
    );
  if (!catalog || !settings)
    return (
      <div className="boot">
        <TriangleAlert />
        <h1>The local workspace is unavailable.</h1>
        <p>{error}</p>
        <button className="primary" onClick={() => location.reload()}>
          Try again
        </button>
      </div>
    );
  const activeCase =
    result?.investigation.case_snapshot ??
    catalog.corpus.cases.find((c) => c.id === settings.case_id)!;
  const investigation = result?.investigation;
  const sources =
    page === "library"
      ? catalog.corpus.documents
      : (investigation?.sources ??
        catalog.corpus.documents.filter(
          (d) => d.case_id === activeCase.id || d.case_id === null,
        ));
  const activeSource = sources.find((d) => d.id === sourceId);
  const dirty =
    !!investigation &&
    JSON.stringify(settings) !== JSON.stringify(investigation.request);
  const filteredCases = catalog.corpus.cases.filter(
    (c) =>
      (severity === "All" || c.severity === severity) &&
      `${c.id} ${c.title} ${c.supplier} ${c.category}`
        .toLowerCase()
        .includes(caseFilter.toLowerCase()),
  );
  const selectedPage = pages.find((p) => p.id === page)!;
  function showSource(id: string, excerpt = "") {
    setSourceId(id.split(":")[0]);
    setQuote(excerpt);
  }
  function sourceInspector(source?: Source) {
    if (!source)
      return (
        <section className="panel source-inspector">
          <FileSearch size={26} />
          <h2>Open a source</h2>
          <p className="muted">
            Click a citation, timeline entry or evidence card to inspect the
            original fictional text.
          </p>
        </section>
      );
    const start = quote ? source.text.indexOf(quote) : -1;
    return (
      <section className="panel source-inspector" aria-label="Source inspector">
        <div className="inspector-label">
          <BookOpen size={16} />
          <span>SOURCE INSPECTOR</span>
        </div>
        <Tag tone={source.kind === "procedure" ? "neutral" : "purple"}>
          {source.case_id ?? "Shared procedure"}
        </Tag>
        <h2>{source.title}</h2>
        <code className="source-id">{source.id}</code>
        <div className="source-meta">
          <span>{human(source.kind)}</span>
          <span>{timestamp(source.recorded_at)} UTC</span>
        </div>
        <div className="document-paper">
          {start >= 0 ? (
            <>
              {source.text.slice(0, start)}
              <mark>{source.text.slice(start, start + quote.length)}</mark>
              {source.text.slice(start + quote.length)}
            </>
          ) : (
            source.text
          )}
        </div>
        {quote && start < 0 && (
          <blockquote className="selected-excerpt">{quote}</blockquote>
        )}
        <div className="source-foot">
          <ShieldCheck size={15} />
          <span>
            Fictional source text. A quote is not an independent confirmation of
            the event.
          </span>
        </div>
      </section>
    );
  }
  function exports() {
    if (!investigation) return null;
    return (
      <div className="exports">
        <span>Export this saved investigation</span>
        {["md", "csv", "json"].map((kind) => (
          <a
            className="quiet-button"
            key={kind}
            href={`/api/investigations/${investigation.id}/export/${kind}`}
          >
            <ArrowDownToLine size={14} />
            {kind === "md" ? "Case brief" : kind.toUpperCase()}
          </a>
        ))}
      </div>
    );
  }
  return (
    <div className="shell">
      <a href="#content" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <FileSearch size={25} />
          </div>
          <div>
            SUPPLY CHAIN<span>Exception Desk</span>
          </div>
        </div>
        <div className="workspace-label">F2 / EVIDENCE-GROUNDED AI</div>
        <nav aria-label="Main navigation">
          {pages.map(({ id, label, icon: Icon }, i) => (
            <button
              key={id}
              className={page === id ? "nav-item active" : "nav-item"}
              aria-current={page === id ? "page" : undefined}
              disabled={busy || reviewBusy}
              onClick={() => go(id)}
            >
              <Icon size={18} />
              <span>{label}</span>
              {i < 3 && <small>0{i + 1}</small>}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={20} />
          <strong>Read the source.</strong>
          <p>
            Case-scoped retrieval.
            <br />
            Local model. Human review.
          </p>
          <span className="sidebar-dot" /> Fictional demonstration data
        </div>
        <div className="profile">
          <span className="avatar">HM</span>
          <div>
            Hitesh M. Mahajan<small>Portfolio / AI & operations</small>
          </div>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            Casework <ChevronRight size={13} />
            <span>{selectedPage.label}</span>
          </div>
          <div className="topbar-right">
            <span className="local-status">
              <i
                className={
                  catalog.model_status.models.length > 0 ? "" : "offline"
                }
              />
              {catalog.model_status.models.length > 0
                ? "Local model available"
                : "Search-only ready"}
            </span>
            <span className="vertical-line" />
            <span>FICTIONAL CASES</span>
          </div>
        </header>
        <main id="content">
          {error && (
            <div className="notice danger" role="alert">
              <TriangleAlert size={18} />
              <div>
                <strong>We couldn’t complete that request.</strong>
                <p>{error}</p>
              </div>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {dirty && (
            <div className="notice amber" role="status">
              <TriangleAlert size={17} />
              <div>
                Question or settings changed. The evidence and exports still
                describe saved investigation{" "}
                <code>{investigation!.id.slice(0, 8)}</code>.
              </div>
              <button
                className="text-button"
                onClick={() => setSettings({ ...investigation!.request })}
              >
                Restore saved request
              </button>
            </div>
          )}

          {page === "inbox" && (
            <>
              <div className="eyebrow">CASEWORK WITH A PAPER TRAIL</div>
              <div className="page-heading">
                <div>
                  <h1>
                    Investigate the exception.
                    <br />
                    Keep the evidence.
                  </h1>
                  <p>
                    Trace a supplier report, inspect the procedure, and review a
                    cited local-AI draft.
                  </p>
                </div>
                <button
                  className="primary"
                  disabled={busy || reviewBusy}
                  onClick={() => choose(catalog.corpus.cases[0])}
                >
                  Open delay case <ArrowRight size={16} />
                </button>
              </div>
              <div className="scope-strip">
                <FlaskConical size={17} />
                <span>
                  <strong>Fictional casework.</strong> Authored records and
                  procedures for a local engineering demonstration. No real
                  shipments or company policies.
                </span>
                <button className="text-button" onClick={() => go("method")}>
                  How it works <ArrowUpRight size={14} />
                </button>
              </div>
              <div className="metrics-grid">
                <Metric
                  label="EXCEPTION CASES"
                  value={String(catalog.corpus.cases.length).padStart(2, "0")}
                  detail="Delays, shortages, damage and missing records"
                  icon={<Inbox />}
                />
                <Metric
                  label="SOURCE DOCUMENTS"
                  value={String(catalog.corpus.documents.length)}
                  detail="Original records with stable citation IDs"
                  icon={<Database />}
                />
                <Metric
                  label="SHARED PROCEDURES"
                  value={String(
                    catalog.corpus.documents.filter(
                      (d) => d.kind === "procedure",
                    ).length,
                  ).padStart(2, "0")}
                  detail="Fictional guidance, scoped across cases"
                  icon={<BookOpen />}
                />
                <Metric
                  label="INFERENCE MODE"
                  value="Local CPU"
                  detail="No paid API, cloud inference or GPU"
                  icon={<Sparkles />}
                />
              </div>
              <section className="panel case-inbox">
                <div className="panel-heading">
                  <div>
                    <h2>The exception queue</h2>
                    <p className="muted">
                      Priority and case flags are authored scenario labels, not
                      model predictions.
                    </p>
                  </div>
                  <Tag tone="purple">{filteredCases.length} cases shown</Tag>
                </div>
                <div className="filter-row">
                  <label className="search-field">
                    <Search size={16} />
                    <input
                      aria-label="Search cases"
                      placeholder="Search case, supplier or issue…"
                      value={caseFilter}
                      onChange={(e) => setCaseFilter(e.target.value)}
                    />
                  </label>
                  <label className="filter-select">
                    Priority
                    <select
                      aria-label="Filter case priority"
                      value={severity}
                      onChange={(e) => setSeverity(e.target.value)}
                    >
                      {["All", "High", "Medium"].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                </div>
                {filteredCases.length ? (
                  <Table>
                    <thead>
                      <tr>
                        <th>Case / issue</th>
                        <th>Supplier / hub</th>
                        <th>Priority</th>
                        <th>Scenario flag</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCases.map((c) => (
                        <tr key={c.id}>
                          <td>
                            <span className="case-code">{c.id}</span>
                            <strong className="case-title">{c.title}</strong>
                            <small className="case-category">
                              {c.category}
                            </small>
                          </td>
                          <td>
                            {c.supplier}
                            <small className="table-sub">{c.hub}</small>
                          </td>
                          <td>
                            <Tag
                              tone={c.severity === "High" ? "amber" : "neutral"}
                            >
                              {c.severity}
                            </Tag>
                          </td>
                          <td className="flag-cell">{c.authored_flag}</td>
                          <td>
                            <button
                              className="text-button"
                              disabled={busy || reviewBusy}
                              aria-label={`Open ${c.id}`}
                              onClick={() => choose(c)}
                            >
                              Investigate <ArrowUpRight size={15} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : (
                  <Empty
                    title="No cases match these filters."
                    text="Try another search term or choose All priorities."
                  />
                )}
              </section>
              <div className="case-principles">
                <div>
                  <FileSearch size={20} />
                  <h3>Scope the investigation</h3>
                  <p>
                    Search this case’s records and shared procedures. Other
                    cases stay outside the model context.
                  </p>
                </div>
                <div>
                  <MessageSquareText size={20} />
                  <h3>Inspect the selected quotes</h3>
                  <p>
                    The model selects excerpts. The app checks their source and
                    text; relevance still needs review.
                  </p>
                </div>
                <div>
                  <FileCheck2 size={20} />
                  <h3>Leave a review trail</h3>
                  <p>
                    Save analyst notes separately, preserve the draft and export
                    its evidence.
                  </p>
                </div>
              </div>
            </>
          )}

          {page === "case" && (
            <>
              <div className="eyebrow">INVESTIGATION / {activeCase.id}</div>
              <div className="page-heading">
                <div>
                  <h1>{activeCase.title}</h1>
                  <p>
                    {activeCase.supplier} · {activeCase.hub} ·{" "}
                    {activeCase.category}
                  </p>
                </div>
                <button
                  className="secondary"
                  disabled={busy || reviewBusy}
                  onClick={() => go("inbox")}
                >
                  <Inbox size={16} />
                  Back to queue
                </button>
              </div>
              <div className="scope-strip">
                <TriangleAlert size={17} />
                <span>
                  <strong>Authored case flag:</strong>{" "}
                  {activeCase.authored_flag}. This is a scenario description,
                  not an AI conclusion.
                </span>
                <Tag
                  tone={activeCase.severity === "High" ? "amber" : "neutral"}
                >
                  {activeCase.severity} priority
                </Tag>
              </div>
              <div className="investigation-layout">
                <div className="case-main">
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <span className="eyebrow">START WITH THE RECORD</span>
                        <h2>Case timeline</h2>
                      </div>
                      <Tag tone="neutral">Fictional records</Tag>
                    </div>
                    <p className="muted">{activeCase.summary}</p>
                    <div className="timeline">
                      {activeCase.timeline.map((event, i) => (
                        <button
                          key={event.source_id}
                          className="timeline-entry"
                          onClick={() => showSource(event.source_id)}
                        >
                          <span className="timeline-marker">{i + 1}</span>
                          <div>
                            <small>
                              {timestamp(event.timestamp)} UTC / recorded
                            </small>
                            <strong>{event.label}</strong>
                            <code>{event.source_id}</code>
                          </div>
                          <ArrowUpRight size={14} />
                        </button>
                      ))}
                    </div>
                  </section>
                  <section className="panel ask-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="eyebrow">ASK A BOUNDED QUESTION</span>
                        <h2>Find the evidence that matters.</h2>
                      </div>
                      <Sparkles size={21} />
                    </div>
                    <form
                      onSubmit={(event) => {
                        event.preventDefault();
                        run();
                      }}
                    >
                      <fieldset disabled={busy || reviewBusy}>
                        <label className="field">
                          Question
                          <textarea
                            required
                            minLength={5}
                            maxLength={400}
                            rows={3}
                            value={settings.question}
                            onChange={(e) => change("question", e.target.value)}
                          />
                        </label>
                        <div className="question-settings">
                          <label className="field">
                            Mode
                            <select
                              value={settings.mode}
                              onChange={(e) =>
                                change(
                                  "mode",
                                  e.target.value as Settings["mode"],
                                )
                              }
                            >
                              <option value="local_ai">
                                Local AI + retrieval
                              </option>
                              <option value="search_only">
                                Evidence search only
                              </option>
                            </select>
                          </label>
                          <label className="field">
                            Local model
                            <select
                              value={settings.model}
                              disabled={settings.mode === "search_only"}
                              onChange={(e) => change("model", e.target.value)}
                            >
                              {["qwen2.5:1.5b", "qwen2.5:0.5b"].map((m) => (
                                <option key={m}>{m}</option>
                              ))}
                            </select>
                          </label>
                          <label className="field">
                            Prompt
                            <select
                              value={settings.prompt_version}
                              disabled={settings.mode === "search_only"}
                              onChange={(e) =>
                                change("prompt_version", e.target.value)
                              }
                            >
                              <option value="v2">
                                v2 / explicit boundaries
                              </option>
                              <option value="v1">v1 / concise baseline</option>
                            </select>
                          </label>
                        </div>
                        <div className="form-action">
                          <span>
                            <ShieldCheck size={15} />
                            Only this case + shared procedures
                          </span>
                          <button className="primary" type="submit">
                            {busy ? (
                              <LoaderCircle className="spin" size={16} />
                            ) : (
                              <Search size={16} />
                            )}{" "}
                            {busy
                              ? "Investigating locally…"
                              : "Run investigation"}
                          </button>
                        </div>
                      </fieldset>
                    </form>
                    <div className="model-note">
                      <span>{catalog.model_status.notice}</span>
                      <button
                        className="text-button"
                        disabled={busy || reviewBusy}
                        onClick={refreshModel}
                      >
                        <RefreshCw size={13} />
                        Refresh status
                      </button>
                    </div>
                  </section>
                  {busy && (
                    <div className="notice purple" role="status">
                      <LoaderCircle className="spin" size={18} />
                      <span>
                        Retrieving case-scoped passages and checking the local
                        model response. Model loading can take longer than a
                        warm request.
                      </span>
                    </div>
                  )}
                  {investigation && (
                    <>
                      <section className="panel draft-panel">
                        <div className="panel-heading">
                          <div>
                            <span className="eyebrow">
                              LOCAL-AI DRAFT / REQUIRES REVIEW
                            </span>
                            <h2>{draftLabel(investigation)}</h2>
                          </div>
                          <Tag
                            tone={
                              investigation.generation.state === "checked"
                                ? "purple"
                                : "amber"
                            }
                          >
                            {investigation.seconds.toFixed(2)}s total
                          </Tag>
                        </div>
                        {investigation.generation.draft ? (
                          <>
                            <p className="draft-boundary">
                              Output checks validate schema and verbatim
                              citations. They do not establish that the model’s
                              stance is correct or that a report is confirmed.
                            </p>
                            {investigation.generation.draft.status ===
                            "insufficient" ? (
                              <div className="abstention">
                                <TriangleAlert size={20} />
                                <div>
                                  <strong>
                                    The model selected insufficient evidence.
                                  </strong>
                                  <p>
                                    No requested value or outcome has been
                                    filled in. Review the retrieved sources
                                    before deciding what is missing.
                                  </p>
                                </div>
                              </div>
                            ) : (
                              investigation.generation.draft.evidence.map(
                                (e, i) => (
                                  <div
                                    className="quote-card"
                                    key={e.passage_id}
                                  >
                                    <div className="quote-index">0{i + 1}</div>
                                    <blockquote>{e.quote}</blockquote>
                                    <button
                                      className="citation"
                                      aria-label={`Inspect citation ${e.passage_id}`}
                                      onClick={() =>
                                        showSource(e.passage_id, e.quote)
                                      }
                                    >
                                      <BookOpen size={13} />
                                      {e.passage_id}
                                      <ArrowUpRight size={13} />
                                    </button>
                                  </div>
                                ),
                              )
                            )}
                          </>
                        ) : (
                          <div className="abstention">
                            <TriangleAlert size={20} />
                            <div>
                              <strong>
                                {investigation.generation.state ===
                                "not_requested"
                                  ? "No model was called."
                                  : "No model draft is presented."}
                              </strong>
                              <p>
                                {investigation.generation.errors.join(" ") ||
                                  "The passages below are search results. This mode is not a generative RAG answer."}
                              </p>
                            </div>
                          </div>
                        )}
                        <div className="run-caption">
                          <code>{investigation.id.slice(0, 8)}</code>
                          <span>{timestamp(investigation.created_at)} UTC</span>
                          <span>
                            {investigation.request.mode === "local_ai"
                              ? `${investigation.request.model} / ${investigation.request.prompt_version}`
                              : "Search only / zero model calls"}
                          </span>
                        </div>
                      </section>
                      <section className="panel">
                        <div className="panel-heading">
                          <div>
                            <h2>Retrieved evidence</h2>
                            <p className="muted">
                              Top {investigation.retrieved.length} passages /
                              case records and shared procedures
                            </p>
                          </div>
                          <Tag tone="neutral">FTS5 + TF-IDF</Tag>
                        </div>
                        <div className="tabs">
                          <button
                            className={
                              evidenceTab === "passages" ? "selected" : ""
                            }
                            onClick={() => setEvidenceTab("passages")}
                          >
                            Passages
                          </button>
                          <button
                            className={
                              evidenceTab === "trace" ? "selected" : ""
                            }
                            onClick={() => setEvidenceTab("trace")}
                          >
                            Technical trace
                          </button>
                        </div>
                        {evidenceTab === "passages" ? (
                          investigation.retrieved.length ? (
                            investigation.retrieved.map((p, i) => (
                              <button
                                className={`passage-card ${sourceId === p.document_id ? "selected" : ""}`}
                                key={p.id}
                                onClick={() => showSource(p.id)}
                              >
                                <span className="rank">{i + 1}</span>
                                <div>
                                  <small>
                                    {p.case_id ?? "Shared procedure"} /{" "}
                                    {human(p.kind)}
                                  </small>
                                  <strong>{p.title}</strong>
                                  <p>{p.text}</p>
                                  <code>{p.id}</code>
                                </div>
                                <ArrowUpRight size={15} />
                              </button>
                            ))
                          ) : (
                            <Empty
                              title="No eligible passages matched."
                              text="Try a more specific question. An empty result is not evidence that an event did or did not happen."
                            />
                          )
                        ) : (
                          <div className="trace">
                            <div className="fingerprint">
                              <span>Corpus SHA-256</span>
                              <code>{investigation.corpus_sha256}</code>
                            </div>
                            <div className="fingerprint">
                              <span>Engine SHA-256</span>
                              <code>{investigation.engine_sha256}</code>
                            </div>
                            <div className="fingerprint">
                              <span>Model digest</span>
                              <code>
                                {investigation.generation.model_digest ??
                                  "No model result"}
                              </code>
                            </div>
                            <div className="fingerprint">
                              <span>Prompt SHA-256</span>
                              <code>
                                {investigation.generation.prompt_sha256 ??
                                  "Not requested"}
                              </code>
                            </div>
                            <h3>Raw model JSON / not an approved answer</h3>
                            <pre className="code-block">
                              {investigation.generation.raw ??
                                "No raw model response."}
                            </pre>
                            <h3>Retrieval ranks</h3>
                            <p className="field-note">
                              TF-IDF is word similarity, not confidence.
                              Reciprocal-rank fusion combines the lexical and
                              TF-IDF rankings.
                            </p>
                            <Table>
                              <thead>
                                <tr>
                                  <th>Passage</th>
                                  <th>FTS rank</th>
                                  <th>Similarity</th>
                                </tr>
                              </thead>
                              <tbody>
                                {investigation.retrieved.map((p) => (
                                  <tr key={p.id}>
                                    <td>{p.id}</td>
                                    <td>{p.lexical_rank}</td>
                                    <td>{p.tfidf_similarity.toFixed(3)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </Table>
                            <details>
                              <summary>Generation settings and runtime</summary>
                              <pre className="code-block">
                                {JSON.stringify(
                                  {
                                    options: investigation.generation.options,
                                    runtime: investigation.runtime,
                                    checks: investigation.generation.errors,
                                  },
                                  null,
                                  2,
                                )}
                              </pre>
                            </details>
                          </div>
                        )}
                      </section>
                      <section className="panel review-panel">
                        <div className="panel-heading">
                          <div>
                            <span className="eyebrow">
                              ANALYST REVIEW / SEPARATE FROM AI
                            </span>
                            <h2>Add your judgement.</h2>
                          </div>
                          <Tag tone="neutral">Append-only notes</Tag>
                        </div>
                        <form onSubmit={saveReview}>
                          <label className="field">
                            Review disposition
                            <select
                              value={disposition}
                              onChange={(e) => setDisposition(e.target.value)}
                            >
                              <option value="needs_follow_up">
                                Needs follow-up
                              </option>
                              <option value="reviewed">Reviewed</option>
                            </select>
                          </label>
                          <label className="field">
                            Analyst note
                            <textarea
                              required
                              maxLength={1200}
                              rows={3}
                              placeholder="What do the records establish, what remains uncertain, and what should be checked next?"
                              value={note}
                              onChange={(e) => setNote(e.target.value)}
                            />
                          </label>
                          <div className="form-action">
                            <span>
                              Review does not change the model output.
                            </span>
                            <button
                              className="secondary"
                              disabled={busy || reviewBusy || !note.trim()}
                              type="submit"
                            >
                              {reviewBusy ? (
                                <LoaderCircle className="spin" size={15} />
                              ) : (
                                <Check size={15} />
                              )}
                              Save review note
                            </button>
                          </div>
                        </form>
                        {result.reviews.length > 0 && (
                          <div className="review-history">
                            {result.reviews.map((r) => (
                              <div key={r.id}>
                                <div>
                                  <Tag
                                    tone={
                                      r.disposition === "reviewed"
                                        ? "purple"
                                        : "amber"
                                    }
                                  >
                                    {human(r.disposition)}
                                  </Tag>
                                  <small>{timestamp(r.created_at)} UTC</small>
                                </div>
                                <p>{r.note}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </section>
                      {exports()}
                    </>
                  )}
                </div>
                <aside className="case-aside">
                  {sourceInspector(activeSource)}
                  <section className="dark-panel">
                    <ShieldCheck size={23} />
                    <h3>A report is not a confirmation.</h3>
                    <p>
                      Supplier estimates, carrier statuses and procedures answer
                      different questions. Keep those distinctions visible.
                    </p>
                    <button
                      className="text-button"
                      disabled={busy || reviewBusy}
                      onClick={() => go("evaluation")}
                    >
                      Inspect the model checks <ArrowRight size={14} />
                    </button>
                  </section>
                </aside>
              </div>
            </>
          )}

          {page === "library" && (
            <>
              <div className="eyebrow">
                LIBRARY / ORIGINAL FICTIONAL SOURCES
              </div>
              <div className="page-heading">
                <div>
                  <h1>Every citation has a source.</h1>
                  <p>
                    Browse the 31 authored records. Investigations only retrieve
                    their own case and shared procedures.
                  </p>
                </div>
                <Tag tone="purple">Corpus {catalog.corpus.version}</Tag>
              </div>
              <div className="library-layout">
                <section className="panel">
                  <label className="search-field">
                    <Search size={16} />
                    <input
                      aria-label="Search source library"
                      placeholder="Find a source, case or procedure…"
                      value={libraryFilter}
                      onChange={(e) => setLibraryFilter(e.target.value)}
                    />
                  </label>
                  <div className="library-list">
                    {catalog.corpus.documents
                      .filter((d) =>
                        `${d.id} ${d.title} ${d.text}`
                          .toLowerCase()
                          .includes(libraryFilter.toLowerCase()),
                      )
                      .map((d) => (
                        <button
                          key={d.id}
                          className={`library-item ${sourceId === d.id ? "selected" : ""}`}
                          onClick={() => showSource(d.id)}
                        >
                          <FileCheck2 size={17} />
                          <div>
                            <small>{d.case_id ?? "Shared procedure"}</small>
                            <strong>{d.title}</strong>
                            <code>{d.id}</code>
                          </div>
                          <ChevronRight size={15} />
                        </button>
                      ))}
                  </div>
                </section>
                <aside>{sourceInspector(activeSource)}</aside>
              </div>
            </>
          )}

          {page === "history" && (
            <>
              <div className="eyebrow">AUDIT TRAIL / DRAFT HISTORY</div>
              <div className="page-heading">
                <div>
                  <h1>Preserve the question and the answer.</h1>
                  <p>
                    Saved requests, source snapshots, model outputs and analyst
                    reviews stay on this computer.
                  </p>
                </div>
                <button className="secondary" onClick={() => go("inbox")}>
                  Open case queue <ArrowRight size={16} />
                </button>
              </div>
              {history.length ? (
                <section className="panel">
                  <Table>
                    <thead>
                      <tr>
                        <th>Case / question</th>
                        <th>Created / UTC</th>
                        <th>Mode / output</th>
                        <th>Review</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((row) => (
                        <tr key={row.id}>
                          <td className="history-question">
                            <span className="case-code">{row.case_id}</span>
                            <strong>{row.question}</strong>
                            <small className="table-sub mono">
                              {row.id.slice(0, 8)}
                            </small>
                          </td>
                          <td>{timestamp(row.created_at)}</td>
                          <td>
                            <Tag
                              tone={
                                row.state === "checked"
                                  ? "purple"
                                  : row.state === "not_requested"
                                    ? "neutral"
                                    : "amber"
                              }
                            >
                              {human(row.state)}
                            </Tag>
                            <small className="table-sub">
                              {human(row.mode)}
                            </small>
                          </td>
                          <td>{human(row.review)}</td>
                          <td>
                            <button
                              className="text-button"
                              disabled={busy || reviewBusy}
                              aria-label={`Open investigation ${row.id.slice(0, 8)}`}
                              onClick={() => open(row.id)}
                            >
                              Open <ArrowUpRight size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                  <p className="inset-note">
                    Latest 100 investigations shown. Stored drafts are
                    immutable; analyst notes append to the record.
                  </p>
                </section>
              ) : (
                <Empty
                  title="No investigations saved yet."
                  text="Open a case and run an investigation. Search-only requests are saved too."
                />
              )}
            </>
          )}

          {page === "evaluation" && (
            <>
              <div className="eyebrow">EVALUATION / MEASURED LOCAL CALLS</div>
              <div className="page-heading">
                <div>
                  <h1>Source checks are not answer accuracy.</h1>
                  <p>
                    Inspect the fixed development comparison and the held-out
                    case-question results.
                  </p>
                </div>
                <Tag tone="neutral">
                  Saved evaluation / not a live accuracy estimate
                </Tag>
              </div>
              {!evaluation.ready || !evaluation.heldout ? (
                <Empty
                  title="No recorded evaluation yet."
                  text="The optional evaluator saves actual local-model results. No performance numbers are filled in automatically."
                />
              ) : (
                <>
                  <div className="scope-strip">
                    <FlaskConical size={17} />
                    <span>
                      Selected configuration:{" "}
                      <strong>
                        {evaluation.release?.model} /{" "}
                        {evaluation.release?.prompt_version}
                      </strong>
                      . Six development questions on two cases; eighteen
                      held-out questions on six separate cases in the indexed
                      fictional corpus.
                    </span>
                  </div>
                  <div className="metrics-grid">
                    <Metric
                      label="EXACT TASK CHECKS"
                      value={`${evaluation.heldout.task_pass}/${evaluation.heldout.questions}`}
                      detail="Stance + exact sources + value fragments"
                      icon={<ClipboardList />}
                    />
                    <Metric
                      label="REQUIRED SOURCES IN TOP 4"
                      value={`${evaluation.heldout.retrieval_all_hit}/${evaluation.heldout.answerable}`}
                      detail="Answerable questions only"
                      icon={<Search />}
                    />
                    <Metric
                      label="CORRECT MODEL ABSTENTIONS"
                      value={`${evaluation.heldout.refusal_pass}/${evaluation.heldout.unanswerable}`}
                      detail="Questions with no requested value available"
                      icon={<ShieldCheck />}
                    />
                    <Metric
                      label="MEDIAN REQUEST TIME"
                      value={`${evaluation.heldout.median_seconds.toFixed(2)}s`}
                      detail="Measured end to end on this CPU"
                      icon={<Clock3 />}
                    />
                  </div>
                  <div className="evidence-grid">
                    <section className="panel">
                      <span className="eyebrow">
                        DEVELOPMENT / CONFIGURATION SELECTION
                      </span>
                      <h2>Four settings. The same six questions.</h2>
                      <div className="evaluation-bars">
                        {evaluation.development?.map((row) => (
                          <div key={row.model + row.prompt_version}>
                            <div>
                              <span>
                                {row.model.replace("qwen2.5:", "")} /{" "}
                                {row.prompt_version}
                              </span>
                              <strong>
                                {row.task_pass}/{row.questions}
                              </strong>
                            </div>
                            <div className="evaluation-track">
                              <span
                                style={{ width: `${row.task_pass_pct}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                      <p className="field-note">
                        Selection prioritizes exact task checks, field checks
                        and output checks. Ties prefer 1.5B and v2. This is a
                        tiny fixture comparison, not a universal model ranking.
                      </p>
                    </section>
                    <section className="panel">
                      <span className="eyebrow">
                        HELD-OUT / DISTINCT CHECKS
                      </span>
                      <h2>Keep the denominators visible.</h2>
                      <div className="summary-row">
                        <span>Accepted value-fragment checks</span>
                        <strong>
                          {evaluation.heldout.field_pass}/
                          {evaluation.heldout.answerable}
                        </strong>
                      </div>
                      <div className="summary-row">
                        <span>Schema/source checks passed</span>
                        <strong>
                          {evaluation.heldout.checked}/
                          {evaluation.heldout.questions}
                        </strong>
                      </div>
                      <div className="summary-row">
                        <span>Drafts withheld by the gate</span>
                        <strong>{evaluation.heldout.withheld}</strong>
                      </div>
                      <div className="summary-row">
                        <span>Answered stance on unanswerable items</span>
                        <strong>
                          {evaluation.heldout.displayed_answer_on_unanswerable}
                        </strong>
                      </div>
                      <div className="summary-row">
                        <span>Completed local calls</span>
                        <strong>
                          {evaluation.heldout.completed_calls}/
                          {evaluation.heldout.questions}
                        </strong>
                      </div>
                      <p className="field-note">
                        A wrong stance can accompany a real quote. Withheld
                        outputs are not counted as correct model abstentions.
                      </p>
                    </section>
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Inspect the held-out questions</h2>
                        <p className="muted">
                          Exact fixture checks can reject other reasonable
                          excerpts. Read the raw evidence when interpreting
                          failures.
                        </p>
                      </div>
                    </div>
                    <Table>
                      <thead>
                        <tr>
                          <th>Case / field</th>
                          <th>Expected stance</th>
                          <th>Model stance</th>
                          <th>Output state</th>
                          <th>Task check</th>
                        </tr>
                      </thead>
                      <tbody>
                        {evaluation.questions?.map((row) => (
                          <tr key={row.id}>
                            <td className="history-question">
                              <span className="case-code">
                                {row.id} / {row.case_id}
                              </span>
                              <strong>{human(row.field)}</strong>
                              <small>{row.question}</small>
                            </td>
                            <td>{row.expected_status}</td>
                            <td>
                              {row.predicted_status ?? "No accepted draft"}
                            </td>
                            <td>{human(row.state)}</td>
                            <td>
                              <Tag tone={row.task_pass ? "purple" : "amber"}>
                                {row.task_pass ? "Matched" : "Did not match"}
                              </Tag>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </section>
                  <div className="scope-strip">
                    <TriangleAlert size={17} />
                    <span>{evaluation.limitations}</span>
                  </div>
                </>
              )}
            </>
          )}

          {page === "method" && (
            <>
              <div className="eyebrow">METHOD / SYSTEM BOUNDARIES</div>
              <div className="page-heading">
                <div>
                  <h1>Retrieve. Select. Check. Review.</h1>
                  <p>
                    A small local RAG workflow with an inspectable paper trail.
                  </p>
                </div>
                <a
                  className="secondary"
                  href="/openapi.json"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open API contract <ArrowUpRight size={15} />
                </a>
              </div>
              <div className="method-grid">
                <section className="panel">
                  <Tag tone="purple">Retrieval</Tag>
                  <h2>Scoped hybrid text search</h2>
                  <p>
                    SQLite FTS5/BM25 and TF-IDF word-vector similarity rank
                    paragraphs. Reciprocal-rank fusion combines the two
                    orderings. Only this case’s records and the seven shared
                    procedures are eligible.
                  </p>
                  <p>
                    Top four passages, with a fixed minimum TF-IDF similarity of
                    0.06. This is a word-matching method, not neural embeddings
                    or a calibrated confidence score. Query labels never fit the
                    index.
                  </p>
                </section>
                <section className="panel">
                  <Tag tone="purple">Local generation</Tag>
                  <h2>Extractive evidence selection</h2>
                  <p>
                    Ollama runs an already installed small Qwen model on CPU. A
                    JSON schema constrains stance and up to three cited quotes.
                    The model selects excerpts rather than writing unconstrained
                    business advice.
                  </p>
                  <p>
                    The checker verifies schema, source membership, exact quoted
                    text and status/evidence consistency. Semantic relevance and
                    the model’s stance still require review.
                  </p>
                </section>
              </div>
              <section className="panel">
                <h2>The failure paths are part of the workflow.</h2>
                <div className="boundary-grid">
                  {[
                    [
                      "Missing information",
                      "An insufficient stance leaves the requested value blank. The app never fills an absent delivery time, approval or temperature.",
                    ],
                    [
                      "Conflicting records",
                      "A conflict stance requires two distinct cited passages. A valid pair still needs a human to determine whether the records actually conflict.",
                    ],
                    [
                      "Invalid output",
                      "Malformed JSON, unknown citations or nonverbatim excerpts are withheld. Raw output stays in the technical trace, clearly labelled.",
                    ],
                    [
                      "Model unavailable",
                      "Case browsing and retrieval remain usable. The result is labelled search-only or unavailable; it is not presented as a generated answer.",
                    ],
                    [
                      "Separate judgement",
                      "Analyst notes append to the saved record. A Reviewed flag is workflow bookkeeping, not proof that the model was correct.",
                    ],
                    [
                      "Local scope",
                      "No external message, order, receipt confirmation, engineering approval or release is executed. No model download happens inside a request.",
                    ],
                  ].map(([title, text]) => (
                    <div key={title}>
                      <ShieldCheck size={18} />
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </div>
                  ))}
                </div>
              </section>
              <section className="panel">
                <h2>Read the prompt versions</h2>
                <div className="prompt-grid">
                  {Object.entries(catalog.prompts).map(([key, text]) => (
                    <details key={key}>
                      <summary>
                        {key} /{" "}
                        {key === "v1"
                          ? "concise baseline"
                          : "explicit evidence boundaries"}
                      </summary>
                      <pre className="code-block">{text}</pre>
                    </details>
                  ))}
                </div>
                <p className="muted">
                  Development and held-out evaluation labels are separate files.
                  The generation context contains only the question and
                  retrieved passages. The raw context and configuration are
                  preserved in each saved investigation.
                </p>
              </section>
              <section className="panel">
                <h2>Architecture at a glance</h2>
                <div className="architecture">
                  <span>React + TypeScript</span>
                  <ArrowRight size={17} />
                  <span>FastAPI + scoped retrieval</span>
                  <ArrowRight size={17} />
                  <span>Local Ollama + checks</span>
                  <ArrowRight size={17} />
                  <span>SQLite + review trail</span>
                </div>
                <p className="muted">
                  Single-origin localhost app. All case records are fictional.
                  Search-only mode remains available without Ollama.
                </p>
              </section>
            </>
          )}
          <footer className="footer">
            <span>
              Hitesh Milind Mahajan / Supply Chain Exception Investigator
            </span>
            <span>
              Fictional casework · Local inference · Inspect every citation
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

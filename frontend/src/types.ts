export type Source = {
  id: string;
  case_id: string | null;
  title: string;
  kind: string;
  recorded_at: string;
  text: string;
  synthetic: boolean;
};
export type Case = {
  id: string;
  title: string;
  category: string;
  severity: string;
  supplier: string;
  hub: string;
  summary: string;
  authored_flag: string;
  synthetic: boolean;
  suggested_question: string;
  timeline: { timestamp: string; label: string; source_id: string }[];
};
export type ModelStatus = {
  available: boolean;
  version: string | null;
  models: { name: string; digest: string; bytes: number }[];
  notice: string;
};
export type Settings = {
  case_id: string;
  question: string;
  mode: "local_ai" | "search_only";
  model: string;
  prompt_version: string;
};
export type Catalog = {
  corpus: {
    version: string;
    seed: number;
    synthetic: boolean;
    cases: Case[];
    documents: Source[];
    scope: string;
  };
  corpus_sha256: string;
  release: {
    model: string;
    prompt_version: string;
    selection: string;
    frozen_at?: string;
  };
  model_status: ModelStatus;
  prompts: Record<string, string>;
};
export type Passage = {
  id: string;
  document_id: string;
  case_id: string | null;
  kind: string;
  title: string;
  text: string;
  recorded_at: string;
  tfidf_similarity: number;
  fusion_score: number;
  lexical_rank: number;
};
export type Draft = {
  status: "supported" | "insufficient" | "conflict";
  evidence: { passage_id: string; quote: string }[];
};
export type Generation = {
  state: string;
  attempted: boolean;
  completed: boolean;
  draft: Draft | null;
  raw: string | null;
  errors: string[];
  seconds: number | null;
  model: string | null;
  model_digest?: string;
  prompt_version: string | null;
  prompt_sha256?: string;
  ollama_version?: string;
  options?: Record<string, unknown>;
  input_context?: unknown[];
};
export type Investigation = {
  id: string;
  created_at: string;
  request: Settings;
  case_snapshot: Case;
  sources: Source[];
  retrieved: Passage[];
  generation: Generation;
  corpus_sha256: string;
  engine_sha256: string;
  engine_version: string;
  seconds: number;
  boundary: string;
  settings: Record<string, unknown>;
  runtime: Record<string, string>;
};
export type Review = {
  id: string;
  investigation_id: string;
  created_at: string;
  disposition: string;
  note: string;
};
export type Result = { investigation: Investigation; reviews: Review[] };
export type History = {
  id: string;
  created_at: string;
  case_id: string;
  question: string;
  state: string;
  mode: string;
  review: string;
};
export type Score = {
  id: string;
  case_id: string;
  question: string;
  field: string;
  expected_status: string;
  retrieval_all_hit: boolean | null;
  task_pass: boolean;
  field_pass: boolean | null;
  refusal_pass: boolean | null;
  state: string;
  predicted_status: string | null;
  seconds: number;
  expected_passage_ids: string[];
  selected_passage_ids: string[];
  displayed_answer_on_unanswerable: boolean;
};
export type Summary = {
  questions: number;
  task_pass: number;
  task_pass_pct: number;
  answerable: number;
  retrieval_all_hit: number;
  field_pass: number;
  unanswerable: number;
  refusal_pass: number;
  displayed_answer_on_unanswerable: number;
  checked: number;
  withheld: number;
  unavailable: number;
  completed_calls: number;
  mean_seconds: number;
  median_seconds: number;
};
export type Evaluation = {
  ready: boolean;
  evaluated_at?: string;
  release?: Catalog["release"];
  development?: (Summary & { model: string; prompt_version: string })[];
  heldout?: Summary;
  questions?: Score[];
  limitations?: string;
};

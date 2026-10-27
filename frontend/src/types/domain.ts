import type { FeatureCollection } from "geojson";

export interface ArtifactSummary {
  id: string;
  name: string;
  kind: string;
  mime: string;
  size: number;
  created_at: string;
}

export interface ModelOption {
  id: string;
  label: string;
  description: string;
  ready: boolean;
  kind: "local" | "llm";
  base_url?: string;
}

export interface UserModelInput {
  label: string;
  model: string;
  base_url: string;
  api_key: string;
}

export interface UserModelOutput {
  id: string;
  label: string;
  model: string;
  base_url: string;
  created_at: string;
  api_key_masked: string;
}

export interface CreateUserModelResponse {
  model: UserModelOutput;
  workspace: WorkspaceSummary;
}

export interface PolicyDocumentSummary {
  id: string;
  name: string;
  source: string;
  category: string;
  suffix: string;
  size: number;
  text_length: number;
  excerpt: string;
}

export interface PolicyDocumentDetail extends PolicyDocumentSummary {
  content: string;
}

export interface PolicySearchResult {
  document_id: string | null;
  source: string;
  type: string;
  score: number;
  rule_id?: string | null;
  article_ref?: string | null;
  excerpt: string;
}

export interface PolicyAnswer {
  answer: string;
  mode: string;
  best_score: number;
  sources: Record<string, unknown>[];
}

export interface WorkspaceSummary {
  dataset_name: string;
  block_count: number;
  field_count: number;
  has_spatial_data: boolean;
  dataset_warnings: readonly string[];
  model_ready: boolean;
  default_model_id: string;
  models: readonly ModelOption[];
  artifacts: readonly ArtifactSummary[];
}

export interface DatasetPayload {
  name: string;
  block_count: number;
  matched_count: number;
  has_more: boolean;
  blocks: Record<string, unknown>[];
}

export interface RegenerationDecision {
  block_id: string;
  block_name?: string;
  district?: string;
  regeneration_scenario: string;
  scenario_positioning: string;
  inefficiency_score: number;
  inefficiency_level: string;
  inefficiency_dimensions: Record<string, number>;
  dominant_problem: string;
  screening_status: string;
  regeneration_potential: number;
  priority_score: number;
  priority_level: string;
  data_coverage: number;
  implementation_timing: string;
  scenario_actions: string[];
  key_evidence: string[];
  manual_review_required: boolean;
}

export interface RegenerationResult {
  title: string;
  summary: {
    total: number;
    candidate_count: number;
    inefficiency_level_counts: Record<string, number>;
    priority_count: number;
    manual_review_count: number;
    average_inefficiency: number;
    average_potential: number;
    scenario_counts: Record<string, number>;
  };
  decisions: RegenerationDecision[];
  spatial?: FeatureCollection;
  artifact?: ArtifactSummary;
  disclaimer: string;
}

export interface ChatProcessEvent {
  phase?: string;
  title: string;
  detail?: string | null;
  observation?: string;
  status?: "running" | "completed" | "warning" | "error";
}

export type ChatPacket =
  | { type: "process"; event: ChatProcessEvent }
  | {
      type: "landscape_progress";
      progress: { message?: string; percent?: number };
    }
  | { type: "answer_delta"; content: string }
  | {
      type: "result";
      result: { response?: string; model_name?: string; warnings?: string[] };
    }
  | { type: "error"; message: string };

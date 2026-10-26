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

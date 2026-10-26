import { requestJson, streamNdjson } from "./http";
import type {
  ChatPacket,
  DatasetPayload,
  RegenerationResult,
  WorkspaceSummary,
} from "../types/domain";

export const getWorkspace = () => requestJson<WorkspaceSummary>("/workspace");

export const getDataset = (query = "") =>
  requestJson<DatasetPayload>(`/dataset?limit=100&q=${encodeURIComponent(query)}`);

export const resetWorkspace = () =>
  requestJson<WorkspaceSummary>("/workspace/reset", { method: "POST" });

export const analyzeRegeneration = (inefficiency: number, potential: number) =>
  requestJson<RegenerationResult>("/regeneration/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      inefficiency_threshold: inefficiency,
      potential_threshold: potential,
    }),
  });

export async function uploadDataset(file: File): Promise<WorkspaceSummary> {
  const body = new FormData();
  body.append("file", file);
  return requestJson<WorkspaceSummary>("/datasets/upload", { method: "POST", body });
}

export async function streamChat(
  query: string,
  modelId: string,
  onPacket: (packet: ChatPacket) => void,
): Promise<void> {
  return streamNdjson<ChatPacket>(
    "/chat/stream",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, model_id: modelId }),
    },
    onPacket,
  );
}

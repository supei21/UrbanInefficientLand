import { requestJson, streamNdjson } from "./http";
import type {
  ChatPacket,
  CreateUserModelResponse,
  DatasetPayload,
  PolicyAnswer,
  PolicyDocumentDetail,
  PolicyDocumentSummary,
  PolicySearchResult,
  RegenerationResult,
  UserModelInput,
  WorkspaceSummary,
} from "../types/domain";

export const getWorkspace = () => requestJson<WorkspaceSummary>("/workspace");

export const getDataset = (query = "") =>
  requestJson<DatasetPayload>(`/dataset?limit=100&q=${encodeURIComponent(query)}`);

export const resetWorkspace = () =>
  requestJson<WorkspaceSummary>("/workspace/reset", { method: "POST" });

export const createUserModel = (input: UserModelInput) =>
  requestJson<CreateUserModelResponse>("/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

export const deleteUserModel = (modelId: string) =>
  requestJson<WorkspaceSummary>(`/models/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
  });

export const listPolicyDocuments = () => requestJson<PolicyDocumentSummary[]>("/rag/policies");

export const getPolicyDocument = (documentId: string) =>
  requestJson<PolicyDocumentDetail>(`/rag/policies/${encodeURIComponent(documentId)}`);

export const searchPolicyDocuments = (query: string, limit = 8) =>
  requestJson<PolicySearchResult[]>(
    `/rag/search?q=${encodeURIComponent(query)}&limit=${encodeURIComponent(limit)}`,
  );

export const askPolicyQuestion = (question: string, modelId: string) =>
  requestJson<PolicyAnswer>("/rag/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, model_id: modelId }),
  });

export async function uploadPolicyDocuments(files: readonly File[]) {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return requestJson<PolicyDocumentSummary[]>("/rag/policies/upload", {
    method: "POST",
    body,
  });
}

export const analyzeRegeneration = (potential: number) =>
  requestJson<RegenerationResult>("/regeneration/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
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

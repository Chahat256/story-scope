import axios from "axios";
import type {
  JobStatusResponse,
  AnalysisReport,
  ChatMessage,
  ChatResponse,
} from "@/types/analysis";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
});

export async function uploadNovel(file: File): Promise<{ job_id: string; filename: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post("/api/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const response = await api.get(`/api/status/${jobId}`);
  return response.data;
}

export async function getReport(jobId: string): Promise<AnalysisReport> {
  const response = await api.get(`/api/report/${jobId}`);
  return response.data;
}

/** Non-streaming chat — kept for backward compatibility. */
export async function sendChatMessage(
  jobId: string,
  message: string,
  history: ChatMessage[]
): Promise<ChatResponse> {
  const response = await api.post("/api/chat", {
    job_id: jobId,
    message,
    history,
  });
  return response.data;
}

export interface StreamCallbacks {
  onSources: (sources: ChatResponse["sources"]) => void;
  onToken: (token: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

/**
 * Streaming chat via Server-Sent Events.
 *
 * The backend emits three event types:
 *   { type: "sources", sources: [...] }
 *   { type: "token",   token: "...", done: false }
 *   { type: "done",    done: true }
 */
export async function streamChatMessage(
  jobId: string,
  message: string,
  history: ChatMessage[],
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`${API_URL}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, message, history }),
  });

  if (!response.ok) {
    const text = await response.text();
    callbacks.onError(text || "Stream request failed");
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    // Keep the last (potentially incomplete) line in the buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const payload = JSON.parse(line.slice(6));
        if (payload.type === "sources") {
          callbacks.onSources(payload.sources ?? []);
        } else if (payload.type === "token" && payload.token) {
          callbacks.onToken(payload.token);
        } else if (payload.type === "done") {
          callbacks.onDone();
        } else if (payload.type === "error") {
          callbacks.onError(payload.error ?? "Unknown streaming error");
        }
      } catch {
        // Malformed SSE line — skip
      }
    }
  }
}

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

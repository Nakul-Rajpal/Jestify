import {
  CharacterListResponse,
  DocumentUploadResponse,
  GenerateRequest,
  GenerateResponse,
  JobStatusResponse,
  LibraryResponse,
  TopicDetailResponse,
} from "@/types";

export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "Unknown error");
    throw new Error(`API error ${response.status}: ${errorBody}`);
  }

  return response.json();
}

export async function getCharacters(): Promise<CharacterListResponse> {
  return request<CharacterListResponse>("/api/characters");
}

export async function uploadDocument(
  file: File
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<DocumentUploadResponse>("/api/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export async function generateVideo(
  requestBody: GenerateRequest
): Promise<GenerateResponse> {
  return request<GenerateResponse>("/api/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  });
}

export async function getJobStatus(
  jobId: string
): Promise<JobStatusResponse> {
  return request<JobStatusResponse>(`/api/jobs/${jobId}`);
}

export async function getLibrary(): Promise<LibraryResponse> {
  return request<LibraryResponse>("/api/library");
}

export async function getTopicVideos(
  subjectId: string,
  topicId: string
): Promise<TopicDetailResponse> {
  return request<TopicDetailResponse>(
    `/api/library/${subjectId}/topics/${topicId}`
  );
}

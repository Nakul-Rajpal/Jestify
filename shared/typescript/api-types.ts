import { Character, Difficulty, JobStatus } from "./enums";

export interface GenerateRequest {
  character: Character;
  difficulty: Difficulty;
  document_ids: string[];
  prompt?: string;
  interests?: string[];
  voice_id?: string;
}

export interface GenerateResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress_percent: number;
  current_step: string;
  video_url: string | null;
  thumbnail_url: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  document_type: string;
  size_bytes: number;
  extracted_text_preview: string;
}

export interface CharacterInfo {
  id: Character;
  name: string;
  description: string;
  thumbnail_url: string;
  personality_summary: string;
}

export interface CharacterListResponse {
  characters: CharacterInfo[];
}

export interface VoiceInfo {
  id: string;
  name: string;
  description: string;
  is_public: boolean;
  language: string | null;
}

export interface VoiceListResponse {
  voices: VoiceInfo[];
}

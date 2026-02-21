// Type definitions matching shared TypeScript contracts

export enum Character {
  SPONGEBOB = "spongebob",
  SUPERMAN = "superman",
  EINSTEIN = "einstein",
  PIRATE = "pirate",
}

export enum Difficulty {
  BEGINNER = "beginner",
  INTERMEDIATE = "intermediate",
  ADVANCED = "advanced",
}

export enum JobStatus {
  PENDING = "pending",
  EXTRACTING_TEXT = "extracting_text",
  GENERATING_SCRIPT = "generating_script",
  RENDERING_ANIMATIONS = "rendering_animations",
  SYNTHESIZING_VOICE = "synthesizing_voice",
  COMPOSITING = "compositing",
  ASSEMBLING = "assembling",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum DocumentType {
  PDF = "pdf",
  IMAGE = "image",
  TEXT = "text",
  URL = "url",
}

export interface GenerateRequest {
  character: Character;
  difficulty: Difficulty;
  document_ids: string[];
  prompt?: string;
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

export interface UploadedDocument {
  id: string;
  filename: string;
  document_type: string;
  size_bytes: number;
}

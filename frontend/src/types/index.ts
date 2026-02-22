// Type definitions matching shared TypeScript contracts

export enum Character {
  LEBRON = "lebron",
  GOKU = "goku",
  PETER = "peter",
  ALYSA = "alysa",
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
  GENERATING_ANIMATIONS = "generating_animations",
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

export interface UploadedDocument {
  id: string;
  filename: string;
  document_type: string;
  size_bytes: number;
}

// --- Library types ---

export interface TopicSummary {
  id: string;
  name: string;
  description: string | null;
  sort_order: number;
  video_count: number;
}

export interface SubjectSummary {
  id: string;
  name: string;
  description: string | null;
  category: string;
  topic_count: number;
  video_count: number;
  topics: TopicSummary[];
}

export interface LibraryResponse {
  subjects: SubjectSummary[];
}

export interface VideoSummary {
  job_id: string;
  title: string;
  character: string;
  difficulty: string;
  video_url: string;
  thumbnail_url: string | null;
  created_at: string;
}

export interface TopicDetailResponse {
  id: string;
  name: string;
  description: string | null;
  sort_order: number;
  subject_name: string;
  videos: VideoSummary[];
}

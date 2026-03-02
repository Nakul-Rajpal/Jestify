"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import CharacterSelector from "@/components/CharacterSelector";
import DifficultySelector from "@/components/DifficultySelector";
import InputBar from "@/components/InputBar";
import JobStatusComponent from "@/components/JobStatus";
import VideoPlayer from "@/components/VideoPlayer";
import { generateVideo } from "@/lib/api";
import { useDocumentUpload } from "@/hooks/useDocumentUpload";
import { useJobPolling } from "@/hooks/useJobPolling";
import { Character, Difficulty, JobStatus, UploadedDocument } from "@/types";

function parseApiError(err: unknown): string {
  const message = err instanceof Error ? err.message : "Failed to start generation";
  const notFoundPrefix = "API error 404: ";
  const invalidPrefix = "API error 400: ";
  if (message.startsWith(notFoundPrefix)) {
    return message.slice(notFoundPrefix.length);
  }
  if (message.startsWith(invalidPrefix)) {
    return message.slice(invalidPrefix.length);
  }
  return message;
}

export default function GeneratePage() {
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);
  const [selectedDifficulty, setSelectedDifficulty] = useState<Difficulty>(Difficulty.INTERMEDIATE);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDocument[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const { upload, isUploading, error: uploadError } = useDocumentUpload();
  const {
    status,
    progress,
    currentStep,
    videoUrl,
    thumbnailUrl,
    error: pollingError,
    isPolling,
  } = useJobPolling(jobId);

  const canGenerate = selectedCharacter !== null && !isSubmitting && !isPolling;

  const activeError = useMemo(() => {
    return submitError || uploadError || pollingError || null;
  }, [submitError, uploadError, pollingError]);

  const handleUpload = async (file: File): Promise<UploadedDocument | null> => {
    const uploaded = await upload(file);
    if (!uploaded) return null;

    setSubmitError(null);
    setUploadedDocs((prev) => {
      if (prev.some((doc) => doc.id === uploaded.id)) return prev;
      return [...prev, uploaded];
    });
    return uploaded;
  };

  const handleSubmit = async (prompt: string, documentIds: string[]) => {
    if (!selectedCharacter) {
      setSubmitError("Select a character before generating.");
      return;
    }

    if (documentIds.length === 0) {
      setSubmitError("Upload at least one document before generating.");
      return;
    }

    setSubmitError(null);
    setJobId(null);
    setIsSubmitting(true);

    try {
      const response = await generateVideo({
        character: selectedCharacter,
        difficulty: selectedDifficulty,
        document_ids: documentIds,
        prompt: prompt || undefined,
      });
      setJobId(response.job_id);
    } catch (err) {
      setSubmitError(parseApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveDoc = (docId: string) => {
    setUploadedDocs((prev) => prev.filter((doc) => doc.id !== docId));
  };

  const showStatus = status !== null && status !== JobStatus.COMPLETED;
  const showVideo = status === JobStatus.COMPLETED && Boolean(videoUrl);

  return (
    <main className="min-h-screen bg-[#090510] text-white pb-44">
      <section className="max-w-5xl mx-auto px-4 sm:px-6 pt-10 pb-10">
        <div className="flex items-center justify-between gap-3 mb-10">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-white/70 hover:text-white transition-colors"
          >
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to landing page
          </Link>
          <span className="text-xs uppercase tracking-[0.18em] text-fuchsia-200/80">
            Video Generation
          </span>
        </div>

        <div className="liquid-glass-card rounded-3xl border border-white/15 p-6 sm:p-8 mb-8">
          <h1 className="font-serif text-4xl sm:text-5xl leading-tight mb-3">
            Build your lesson video
          </h1>
          <p className="text-white/75 mb-8 max-w-2xl">
            Pick a character, choose depth, upload your source content, and generate a narrated lesson.
          </p>

          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.15em] text-fuchsia-200/80 mb-3">Step 1</p>
            <CharacterSelector
              selected={selectedCharacter}
              onSelect={(character) => {
                setSelectedCharacter(character);
                setSubmitError(null);
              }}
              disabled={isPolling}
            />
          </div>

          <div>
            <p className="text-xs uppercase tracking-[0.15em] text-fuchsia-200/80 mb-3">Step 2</p>
            <DifficultySelector
              selected={selectedDifficulty}
              onSelect={setSelectedDifficulty}
              disabled={isPolling}
            />
          </div>
        </div>

        <div className="liquid-glass-card rounded-3xl border border-white/15 p-6 sm:p-8 mb-8">
          <p className="text-xs uppercase tracking-[0.15em] text-fuchsia-200/80 mb-2">Step 3</p>
          <h2 className="text-2xl font-serif mb-2">Add your document and generate</h2>
          <p className="text-sm text-white/70 mb-3">
            Upload at least one source file, then describe what you want to learn.
          </p>

          {!selectedCharacter && (
            <p className="text-sm text-amber-300/90">
              Select a character first to unlock generation.
            </p>
          )}
        </div>

        <div className="liquid-glass-card rounded-3xl border border-white/15 p-6 sm:p-8 min-h-[280px]">
          {isSubmitting && (
            <p className="text-sm text-blue-300 mb-4">Starting your generation job...</p>
          )}

          {activeError && (
            <div className="mb-5 rounded-xl border border-red-500/35 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {activeError}
            </div>
          )}

          {showStatus && status && (
            <JobStatusComponent
              status={status}
              progress={progress}
              currentStep={currentStep}
              character={selectedCharacter}
              error={pollingError}
            />
          )}

          {showVideo && videoUrl && (
            <VideoPlayer
              videoUrl={videoUrl}
              thumbnailUrl={thumbnailUrl}
              title="Your generated lesson"
            />
          )}

          {!showStatus && !showVideo && !isSubmitting && (
            <p className="text-sm text-white/70">
              Your generation status will appear here once you submit.
            </p>
          )}
        </div>
      </section>

      <InputBar
        onSubmit={handleSubmit}
        onUpload={handleUpload}
        uploadedDocs={uploadedDocs}
        onRemoveDoc={handleRemoveDoc}
        isGenerating={isSubmitting || isPolling}
        isUploading={isUploading}
        disabled={!canGenerate}
      />
    </main>
  );
}

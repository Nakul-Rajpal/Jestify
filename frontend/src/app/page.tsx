"use client";

import { useState, useCallback } from "react";
import Image from "next/image";
import {
  Character,
  Difficulty,
  JobStatus as JobStatusEnum,
  UploadedDocument,
} from "@/types";
import Link from "next/link";
import { generateVideo, BASE_URL } from "@/lib/api";
import { useJobPolling } from "@/hooks/useJobPolling";
import { useDocumentUpload } from "@/hooks/useDocumentUpload";
import CharacterSelector from "@/components/CharacterSelector";
import DifficultySelector from "@/components/DifficultySelector";
import InputBar from "@/components/InputBar";
import JobStatusComponent from "@/components/JobStatus";
import VideoPlayer from "@/components/VideoPlayer";
import NeuralBackground from "@/components/ui/flow-field-background";

export default function Home() {
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(
    null
  );
  const [selectedDifficulty, setSelectedDifficulty] =
    useState<Difficulty | null>(null);
  const [uploadedDocuments, setUploadedDocuments] = useState<
    UploadedDocument[]
  >([]);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const { upload, isUploading, error: uploadError } = useDocumentUpload();
  const { status, progress, currentStep, videoUrl, thumbnailUrl, error, isPolling } =
    useJobPolling(currentJobId);

  const handleUpload = useCallback(
    async (file: File): Promise<UploadedDocument | null> => {
      const doc = await upload(file);
      if (doc) {
        setUploadedDocuments((prev) => [...prev, doc]);
      }
      return doc;
    },
    [upload]
  );

  const handleRemoveDoc = useCallback((docId: string) => {
    setUploadedDocuments((prev) => prev.filter((d) => d.id !== docId));
  }, []);

  const handleSubmit = useCallback(
    async (prompt: string, documentIds: string[]) => {
      if (!selectedCharacter || !selectedDifficulty) return;

      setIsGenerating(true);
      setGenerateError(null);

      try {
        const response = await generateVideo({
          character: selectedCharacter,
          difficulty: selectedDifficulty,
          document_ids: documentIds,
          prompt: prompt || undefined,
        });
        setCurrentJobId(response.job_id);
        setUploadedDocuments([]);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to start generation";
        setGenerateError(message);
      } finally {
        setIsGenerating(false);
      }
    },
    [selectedCharacter, selectedDifficulty]
  );

  const handleNewVideo = useCallback(() => {
    setCurrentJobId(null);
    setUploadedDocuments([]);
    setGenerateError(null);
  }, []);

  const isJobActive =
    currentJobId !== null &&
    status !== null &&
    status !== JobStatusEnum.COMPLETED &&
    status !== JobStatusEnum.FAILED;

  const isJobComplete = status === JobStatusEnum.COMPLETED && videoUrl;
  const isJobFailed = status === JobStatusEnum.FAILED;

  const hasActiveJob = isJobActive || isJobComplete || isJobFailed;
  const inputDisabled = selectedCharacter === null || selectedDifficulty === null;

  return (
    <div className="purple-gradient-stage relative flex min-h-screen flex-col overflow-hidden text-white">
      <div className="pointer-events-none absolute inset-0 z-0 opacity-55">
        <NeuralBackground
          className="bg-transparent"
          color="#d946ef"
          trailOpacity={0.08}
          particleCount={560}
          speed={0.72}
          mouseMode="attract"
          mouseStrength={0.065}
          interactionRadius={220}
        />
      </div>

      {/* Header */}
      <header className="relative z-10 flex flex-col items-center justify-center px-4 pb-1 pt-4">
        <div className="relative -mt-1">
          <Image
            src="/jestify-v2.png"
            alt="Jestify"
            width={224}
            height={224}
            className="h-56 w-56 object-contain relative z-10"
            priority
          />
          <span className="logo-unglow" aria-hidden="true" />
        </div>
        <h1 className="neo-grotesk-wordmark">
          <span className="text-[#8b5cf6]">J E S T</span>
          <span className="text-[#facc15]"> I F Y</span>
        </h1>
        <Link
          href="/library"
          className="text-sm text-neutral-400 hover:text-white transition-colors"
        >
          Library
        </Link>
      </header>

      {/* Main content area */}
      <main className="relative z-10 flex flex-1 flex-col items-center px-4 pb-40">
        {/* Selectors section — show when no active job */}
        {!hasActiveJob && (
          <div className="w-full max-w-3xl mt-8 space-y-6">
            <CharacterSelector
              selected={selectedCharacter}
              onSelect={setSelectedCharacter}
              disabled={isGenerating || isPolling}
            />
            <DifficultySelector
              selected={selectedDifficulty}
              onSelect={setSelectedDifficulty}
              disabled={isGenerating || isPolling}
            />
          </div>
        )}

        {/* Error from generation */}
        {generateError && !hasActiveJob && (
          <div className="mt-6 max-w-md mx-auto">
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-center">
              <p className="text-sm text-red-400">{generateError}</p>
            </div>
          </div>
        )}

        {/* Job status — show when processing */}
        {isJobActive && status && (
          <div className="flex-1 flex items-center justify-center mt-12">
            <JobStatusComponent
              status={status}
              progress={progress}
              currentStep={currentStep}
              character={selectedCharacter}
              error={error}
            />
          </div>
        )}

        {/* Job failed */}
        {isJobFailed && status && (
          <div className="flex-1 flex flex-col items-center justify-center mt-12 gap-4">
            <JobStatusComponent
              status={status}
              progress={progress}
              currentStep={currentStep}
              character={selectedCharacter}
              error={error}
            />
            <button
              onClick={handleNewVideo}
              className="mt-4 px-6 py-2.5 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-300 hover:text-white hover:border-neutral-500 transition-colors duration-200 cursor-pointer"
            >
              Try again
            </button>
          </div>
        )}

        {/* Video player — show when complete */}
        {isJobComplete && videoUrl && (
          <div className="flex-1 flex flex-col items-center justify-center mt-12 gap-4 w-full">
            <VideoPlayer
              videoUrl={`${BASE_URL}${videoUrl}`}
              thumbnailUrl={thumbnailUrl ? `${BASE_URL}${thumbnailUrl}` : undefined}
            />
            <button
              onClick={handleNewVideo}
              className="mt-2 px-6 py-2.5 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-300 hover:text-white hover:border-neutral-500 transition-colors duration-200 cursor-pointer"
            >
              Generate another video
            </button>
          </div>
        )}
      </main>

      {/* Input bar — fixed at bottom, hidden when job is active or complete */}
      {!hasActiveJob && (
        <InputBar
          onSubmit={handleSubmit}
          onUpload={handleUpload}
          uploadedDocs={uploadedDocuments}
          onRemoveDoc={handleRemoveDoc}
          isGenerating={isGenerating}
          isUploading={isUploading}
          disabled={inputDisabled}
        />
      )}
    </div>
  );
}

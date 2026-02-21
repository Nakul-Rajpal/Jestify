"use client";

import { JobStatus as JobStatusEnum, Character } from "@/types";

interface JobStatusProps {
  status: JobStatusEnum;
  progress: number;
  currentStep: string;
  character: Character | null;
  error: string | null;
}

function getStatusMessage(
  status: JobStatusEnum,
  character: Character | null
): string {
  const charName = getCharacterName(character);

  switch (status) {
    case JobStatusEnum.PENDING:
      return "Preparing your video...";
    case JobStatusEnum.EXTRACTING_TEXT:
      return "Reading and extracting text from your documents...";
    case JobStatusEnum.GENERATING_SCRIPT:
      return `Generating script in ${charName}'s voice...`;
    case JobStatusEnum.GENERATING_ANIMATIONS:
      return `Designing animations for ${charName}'s lesson...`;
    case JobStatusEnum.RENDERING_ANIMATIONS:
      return `Creating animations for ${charName}...`;
    case JobStatusEnum.SYNTHESIZING_VOICE:
      return `Synthesizing ${charName}'s voice...`;
    case JobStatusEnum.COMPOSITING:
      return "Compositing video layers...";
    case JobStatusEnum.ASSEMBLING:
      return "Assembling final video...";
    case JobStatusEnum.COMPLETED:
      return "Video is ready!";
    case JobStatusEnum.FAILED:
      return "Something went wrong";
    default:
      return "Processing...";
  }
}

function getCharacterName(character: Character | null): string {
  switch (character) {
    case Character.LEBRON:
      return "LeBron";
    case Character.GOKU:
      return "Goku";
    case Character.PETER:
      return "Peter Griffin";
    case Character.ROGAN:
      return "Joe Rogan";
    default:
      return "your character";
  }
}

export default function JobStatusComponent({
  status,
  progress,
  currentStep,
  character,
  error,
}: JobStatusProps) {
  const message = getStatusMessage(status, character);
  const isFailed = status === JobStatusEnum.FAILED;
  const isComplete = status === JobStatusEnum.COMPLETED;

  return (
    <div className="w-full max-w-md mx-auto text-center">
      {/* Spinner */}
      {!isComplete && !isFailed && (
        <div className="mb-6 flex justify-center">
          <div className="relative w-16 h-16">
            <svg
              className="w-16 h-16 animate-spin"
              viewBox="0 0 50 50"
              fill="none"
            >
              <circle
                cx="25"
                cy="25"
                r="20"
                stroke="currentColor"
                strokeWidth="3"
                className="text-neutral-700"
              />
              <path
                d="M25 5a20 20 0 0117.32 10"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                className="text-white"
              />
            </svg>
          </div>
        </div>
      )}

      {/* Failed icon */}
      {isFailed && (
        <div className="mb-6 flex justify-center">
          <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-red-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </div>
        </div>
      )}

      {/* Status message */}
      <h3
        className={`text-lg font-medium mb-2 ${
          isFailed ? "text-red-400" : "text-white"
        }`}
      >
        {message}
      </h3>

      {/* Current step detail */}
      {currentStep && !isComplete && !isFailed && (
        <p className="text-sm text-neutral-400 mb-4">{currentStep}</p>
      )}

      {/* Error message */}
      {error && (
        <p className="text-sm text-red-400/80 mb-4">{error}</p>
      )}

      {/* Progress bar */}
      {!isComplete && !isFailed && (
        <div className="w-full bg-neutral-800 rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-white rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.max(progress, 2)}%` }}
          />
        </div>
      )}

      {/* Progress percentage */}
      {!isComplete && !isFailed && (
        <p className="text-xs text-neutral-500 mt-2">{Math.round(progress)}%</p>
      )}
    </div>
  );
}

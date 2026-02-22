"use client";

import { useState, useEffect, useRef } from "react";
import { JobStatus as JobStatusEnum, Character } from "@/types";

interface JobStatusProps {
  status: JobStatusEnum;
  progress: number;
  currentStep: string;
  character: Character | null;
  error: string | null;
}

const STAGE_ORDER: JobStatusEnum[] = [
  JobStatusEnum.PENDING,
  JobStatusEnum.GENERATING_SCRIPT,
  JobStatusEnum.RENDERING_ANIMATIONS,
  JobStatusEnum.SYNTHESIZING_VOICE,
  JobStatusEnum.COMPOSITING,
  JobStatusEnum.ASSEMBLING,
];

interface StageInfo {
  label: string;
  icon: string;
}

const STAGE_META: Record<string, StageInfo> = {
  [JobStatusEnum.PENDING]: { label: "Queued", icon: "" },
  [JobStatusEnum.GENERATING_SCRIPT]: { label: "Writing Script", icon: "" },
  [JobStatusEnum.RENDERING_ANIMATIONS]: { label: "Rendering Animations", icon: "" },
  [JobStatusEnum.SYNTHESIZING_VOICE]: { label: "Generating Voice", icon: "" },
  [JobStatusEnum.COMPOSITING]: { label: "Compositing", icon: "" },
  [JobStatusEnum.ASSEMBLING]: { label: "Final Assembly", icon: "" },
};

function getCharacterName(character: Character | null): string {
  switch (character) {
    case Character.LEBRON:
      return "LeBron";
    case Character.GOKU:
      return "Goku";
    case Character.PETER:
      return "Peter Griffin";
    case Character.TAYLOR:
      return "Taylor Swift";
    default:
      return "your character";
  }
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function ElapsedTimer() {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed((Date.now() - startRef.current) / 1000);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <span className="tabular-nums text-neutral-500">{formatElapsed(elapsed)}</span>
  );
}

export default function JobStatusComponent({
  status,
  progress,
  currentStep,
  character,
  error,
}: JobStatusProps) {
  const isFailed = status === JobStatusEnum.FAILED;
  const isComplete = status === JobStatusEnum.COMPLETED;
  const charName = getCharacterName(character);

  const currentStageIdx = STAGE_ORDER.indexOf(status);

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Header with character name and timer */}
      {!isComplete && !isFailed && (
        <div className="text-center mb-6">
          <h3 className="text-lg font-medium text-white mb-1">
            Creating {charName}&apos;s lesson
          </h3>
          <div className="flex items-center justify-center gap-2 text-sm">
            <ElapsedTimer />
            <span className="text-neutral-600">·</span>
            <span className="text-neutral-400">{Math.round(progress)}%</span>
          </div>
        </div>
      )}

      {/* Failed state */}
      {isFailed && (
        <div className="text-center mb-6">
          <div className="w-14 h-14 rounded-full bg-red-500/15 flex items-center justify-center mx-auto mb-3">
            <svg
              className="w-7 h-7 text-red-400"
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
          <h3 className="text-lg font-medium text-red-400 mb-1">Generation failed</h3>
          {error && <p className="text-sm text-red-400/70 max-w-sm mx-auto">{error}</p>}
        </div>
      )}

      {/* Progress bar */}
      {!isComplete && !isFailed && (
        <div className="mb-6">
          <div className="w-full bg-neutral-800 rounded-full h-2.5 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700 ease-out bg-gradient-to-r from-blue-500 to-blue-400"
              style={{ width: `${Math.max(progress, 2)}%` }}
            />
          </div>
        </div>
      )}

      {/* Stage pipeline */}
      {!isComplete && !isFailed && (
        <div className="space-y-1 mb-6">
          {STAGE_ORDER.map((stage, i) => {
            const meta = STAGE_META[stage];
            const isActive = stage === status;
            const isDone = currentStageIdx > i;
            const isPending = currentStageIdx < i;

            return (
              <div
                key={stage}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-300 ${
                  isActive
                    ? "bg-neutral-800/80 border border-neutral-700"
                    : isDone
                    ? "opacity-50"
                    : "opacity-30"
                }`}
              >
                <span className="w-6 text-center text-sm">
                  {isDone ? (
                    <svg className="w-4 h-4 text-green-400 mx-auto" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : isActive ? (
                    <svg className="w-4 h-4 animate-spin text-blue-400 mx-auto" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" className="text-neutral-700" />
                      <path d="M12 2a10 10 0 018.66 5" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" className="text-blue-400" />
                    </svg>
                  ) : (
                    <span className="block w-2 h-2 rounded-full bg-neutral-600 mx-auto" />
                  )}
                </span>
                <span
                  className={`text-sm font-medium ${
                    isActive
                      ? "text-white"
                      : isDone
                      ? "text-neutral-400"
                      : "text-neutral-600"
                  }`}
                >
                  {meta.label}
                </span>
                {isActive && isPending === false && (
                  <span className="ml-auto text-xs text-blue-400/80 font-medium">In progress</span>
                )}
                {isDone && (
                  <span className="ml-auto text-xs text-green-500/70">Done</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Current step detail */}
      {!isComplete && !isFailed && currentStep && (
        <div className="bg-neutral-800/50 rounded-lg px-4 py-3 border border-neutral-800">
          <p className="text-sm text-neutral-300 leading-relaxed">{currentStep}</p>
        </div>
      )}
    </div>
  );
}

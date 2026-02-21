"use client";

import { Difficulty } from "@/types";

interface DifficultyOption {
  id: Difficulty;
  label: string;
}

const DIFFICULTIES: DifficultyOption[] = [
  { id: Difficulty.BEGINNER, label: "Beginner" },
  { id: Difficulty.INTERMEDIATE, label: "Intermediate" },
  { id: Difficulty.ADVANCED, label: "Advanced" },
];

interface DifficultySelectorProps {
  selected: Difficulty | null;
  onSelect: (difficulty: Difficulty) => void;
  disabled?: boolean;
}

export default function DifficultySelector({
  selected,
  onSelect,
  disabled = false,
}: DifficultySelectorProps) {
  return (
    <div className="w-full">
      <h2 className="text-sm font-medium text-neutral-400 mb-3 text-center">
        Select difficulty
      </h2>
      <div className="flex justify-center gap-2">
        {DIFFICULTIES.map((difficulty) => {
          const isSelected = selected === difficulty.id;
          return (
            <button
              key={difficulty.id}
              onClick={() => onSelect(difficulty.id)}
              disabled={disabled}
              className={`
                px-5 py-2 rounded-full text-sm font-medium
                transition-all duration-200 cursor-pointer
                ${
                  isSelected
                    ? "bg-white text-neutral-900"
                    : "bg-neutral-800 text-neutral-300 hover:bg-neutral-700 hover:text-white border border-neutral-700"
                }
                ${disabled ? "opacity-50 cursor-not-allowed" : ""}
              `}
            >
              {difficulty.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

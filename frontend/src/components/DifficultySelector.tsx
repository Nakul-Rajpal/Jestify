"use client";

import { Difficulty } from "@/types";

interface DifficultyOption {
  id: Difficulty;
  label: string;
  duration: string;
}

const DIFFICULTIES: DifficultyOption[] = [
  { id: Difficulty.BEGINNER, label: "Beginner", duration: "~2 min" },
  { id: Difficulty.INTERMEDIATE, label: "Intermediate", duration: "~4 min" },
  { id: Difficulty.ADVANCED, label: "Advanced", duration: "~8 min" },
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
                transition-all duration-200 cursor-pointer border
                ${
                  isSelected
                    ? "scale-[1.06] bg-[#FACC15]/15 border-[#FACC15]/60 text-[#FACC15] shadow-[0_0_20px_rgba(250,204,21,0.25)]"
                    : "bg-[#1E1B2E] border-white/10 text-[#A8A3C0] hover:text-white hover:border-[#A855F7]/40 hover:bg-[#252240] hover:-translate-y-0.5"
                }
                ${disabled ? "opacity-50 cursor-not-allowed" : ""}
              `}
            >
              {difficulty.label}
              <span className="ml-1.5 text-xs opacity-60">{difficulty.duration}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

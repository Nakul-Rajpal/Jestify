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
                liquid-glass-pill px-5 py-2 rounded-full text-sm font-medium
                transition-all duration-200 cursor-pointer
                ${
                  isSelected
                    ? "scale-[1.06] border-fuchsia-100/95 text-white bg-[linear-gradient(145deg,rgba(255,186,247,0.48),rgba(224,184,255,0.34),rgba(58,34,92,0.46))] shadow-[0_0_0_1px_rgba(252,196,255,0.55),0_0_22px_rgba(230,116,255,0.58),0_14px_34px_rgba(214,90,255,0.5)]"
                    : "text-white/80 hover:text-white hover:border-fuchsia-100/85 hover:bg-[linear-gradient(145deg,rgba(255,170,244,0.35),rgba(216,171,255,0.27),rgba(41,24,64,0.35))] hover:shadow-[0_14px_34px_rgba(214,90,255,0.5)] hover:-translate-y-0.5"
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

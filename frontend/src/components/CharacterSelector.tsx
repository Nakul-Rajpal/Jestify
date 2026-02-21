"use client";

import { Character } from "@/types";

interface CharacterOption {
  id: Character;
  name: string;
  description: string;
  initial: string;
  accentColor: string;
  bgColor: string;
}

const CHARACTERS: CharacterOption[] = [
  {
    id: Character.LEBRON,
    name: "LeBron James",
    description: "Motivational, coach-style lessons",
    initial: "L",
    accentColor: "border-amber-400",
    bgColor: "bg-amber-400",
  },
  {
    id: Character.GOKU,
    name: "Goku",
    description: "High-energy training mindset",
    initial: "G",
    accentColor: "border-orange-500",
    bgColor: "bg-orange-500",
  },
  {
    id: Character.PETER,
    name: "Peter Griffin",
    description: "Comedic and casual explanations",
    initial: "P",
    accentColor: "border-green-500",
    bgColor: "bg-green-500",
  },
  {
    id: Character.ROGAN,
    name: "Joe Rogan",
    description: "Conversational, podcast-like teaching",
    initial: "J",
    accentColor: "border-cyan-500",
    bgColor: "bg-cyan-500",
  },
];

interface CharacterSelectorProps {
  selected: Character | null;
  onSelect: (character: Character) => void;
  disabled?: boolean;
}

export default function CharacterSelector({
  selected,
  onSelect,
  disabled = false,
}: CharacterSelectorProps) {
  return (
    <div className="w-full">
      <h2 className="text-sm font-medium text-neutral-400 mb-3 text-center">
        Choose your instructor
      </h2>
      <div className="flex justify-center gap-3 flex-wrap">
        {CHARACTERS.map((character) => {
          const isSelected = selected === character.id;
          return (
            <button
              key={character.id}
              onClick={() => onSelect(character.id)}
              disabled={disabled}
              className={`
                flex flex-col items-center gap-2 p-4 rounded-xl
                border-2 transition-all duration-200 cursor-pointer
                min-w-[120px] max-w-[140px]
                ${
                  isSelected
                    ? `${character.accentColor} bg-neutral-800`
                    : "border-neutral-700 bg-neutral-800/50 hover:border-neutral-500 hover:bg-neutral-800"
                }
                ${disabled ? "opacity-50 cursor-not-allowed" : ""}
              `}
            >
              <div
                className={`
                  w-12 h-12 rounded-full flex items-center justify-center
                  text-lg font-bold text-neutral-900
                  ${character.bgColor}
                  ${isSelected ? "ring-2 ring-white/20" : ""}
                `}
              >
                {character.initial}
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-white">
                  {character.name}
                </p>
                <p className="text-xs text-neutral-400 mt-0.5 leading-tight">
                  {character.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

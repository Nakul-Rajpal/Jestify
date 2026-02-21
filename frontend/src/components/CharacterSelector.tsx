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
    id: Character.SPONGEBOB,
    name: "SpongeBob",
    description: "Fun and enthusiastic explanations",
    initial: "S",
    accentColor: "border-yellow-400",
    bgColor: "bg-yellow-400",
  },
  {
    id: Character.SUPERMAN,
    name: "Superman",
    description: "Heroic and confident teaching",
    initial: "S",
    accentColor: "border-blue-500",
    bgColor: "bg-blue-500",
  },
  {
    id: Character.EINSTEIN,
    name: "Einstein",
    description: "Brilliant and curious insights",
    initial: "E",
    accentColor: "border-purple-400",
    bgColor: "bg-purple-400",
  },
  {
    id: Character.PIRATE,
    name: "Captain Blackbeard",
    description: "Adventurous and bold lessons",
    initial: "B",
    accentColor: "border-red-500",
    bgColor: "bg-red-500",
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

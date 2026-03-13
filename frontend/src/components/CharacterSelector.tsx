"use client";

import { Character } from "@/types";

interface CharacterOption {
  id: Character;
  name: string;
  description: string;
  imageSrc: string;
}

const CHARACTERS: CharacterOption[] = [
  {
    id: Character.LEBRON,
    name: "LeBron James",
    description: "Energetic coaching style that breaks concepts into practical steps.",
    imageSrc: "/characters/lebron.png",
  },
  {
    id: Character.GOKU,
    name: "Goku",
    description: "High-energy explanations with a focus on momentum and confidence.",
    imageSrc: "/characters/goku.png",
  },
  {
    id: Character.PETER,
    name: "Peter",
    description: "Casual, humorous teaching style with simple relatable examples.",
    imageSrc: "/characters/peter.png",
  },
  {
    id: Character.TAYLOR,
    name: "Taylor Swift",
    description: "Expressive explanations with a clear, story-driven learning flow.",
    imageSrc: "/characters/taylor.png",
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
      <div className="flex flex-wrap justify-center gap-3">
        {CHARACTERS.map((character) => {
          const isSelected = selected === character.id;
          return (
            <button
              key={character.id}
              onClick={() => onSelect(character.id)}
              disabled={disabled}
              className={`
                group relative min-w-[120px] max-w-[140px] h-[172px] cursor-pointer rounded-2xl
                [perspective:1200px]
                ${
                  isSelected
                    ? "scale-[1.02] shadow-[0_0_0_1px_rgba(250,204,21,0.6),0_0_28px_rgba(250,204,21,0.45),0_22px_46px_rgba(168,85,247,0.35)]"
                    : "hover:shadow-[0_18px_42px_rgba(168,85,247,0.4)]"
                }
                ${disabled ? "opacity-50 cursor-not-allowed" : ""}
              `}
            >
              <div
                className={`
                  relative h-full w-full rounded-2xl border
                  transition-[transform,border-color,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]
                  will-change-transform
                  [transform-style:preserve-3d]
                  ${isSelected ? "border-[#FACC15]/80" : "border-white/20 group-hover:border-[#A855F7]/60"}
                  ${!disabled ? "group-hover:[transform:rotateY(180deg)]" : ""}
                `}
              >
                {/* Front */}
                <div className="absolute inset-0 rounded-2xl [backface-visibility:hidden] overflow-hidden">
                  <div
                    className={`absolute inset-0 ${
                      isSelected
                        ? "bg-[linear-gradient(145deg,rgba(250,204,21,0.2),rgba(168,85,247,0.25),rgba(30,27,46,0.7))]"
                        : "bg-[linear-gradient(145deg,rgba(168,85,247,0.15),rgba(138,92,246,0.1),rgba(30,27,46,0.5))]"
                    }`}
                  />
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-0 top-0 h-8 bg-gradient-to-b from-white/10 to-transparent"
                  />
                  <div className="relative z-10 flex h-full flex-col items-center justify-center gap-3 px-3 transition-opacity duration-150 group-hover:opacity-0">
                    <div className="relative flex h-[108px] w-[108px] items-center justify-center rounded-full border border-[#A855F7]/40 bg-gradient-to-br from-[#A855F7]/30 via-[#7C3AED]/25 to-[#1E1B2E]/60 shadow-[0_10px_30px_rgba(168,85,247,0.3)]">
                      <svg
                        aria-hidden="true"
                        viewBox="0 0 24 24"
                        className="h-10 w-10 text-white/45"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <circle cx="12" cy="8" r="4" />
                        <path d="M4 20c1.8-3.4 4.6-5 8-5s6.2 1.6 8 5" />
                      </svg>
                      <img
                        src={character.imageSrc}
                        alt={character.name}
                        className="absolute inset-0 h-full w-full rounded-full object-cover"
                        onError={(e) => {
                          e.currentTarget.style.display = "none";
                        }}
                      />
                    </div>
                    <p className="text-xs font-semibold text-white text-center">
                      {character.name}
                    </p>
                  </div>
                </div>

                {/* Back */}
                <div className="absolute inset-0 rounded-2xl [backface-visibility:hidden] [transform:rotateY(180deg)] overflow-hidden">
                  <div className="absolute inset-0 bg-[linear-gradient(155deg,rgba(168,85,247,0.25),rgba(124,58,237,0.2),rgba(30,27,46,0.6))]" />
                  <div className="relative z-10 flex h-full w-full flex-col items-start justify-center gap-1 px-3.5 text-left">
                    <p className="w-full break-words text-[12px] font-semibold leading-tight text-white">
                      {character.name}
                    </p>
                    <p className="w-full break-words text-[10px] leading-snug text-white/85">
                      {character.description}
                    </p>
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

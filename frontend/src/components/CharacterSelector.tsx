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
    id: Character.SPONGEBOB,
    name: "LeBron James",
    description: "Energetic coaching style that breaks concepts into practical steps.",
    imageSrc: "/characters/lebron.png",
  },
  {
    id: Character.SUPERMAN,
    name: "Goku",
    description: "High-energy explanations with a focus on momentum and confidence.",
    imageSrc: "/characters/goku.png",
  },
  {
    id: Character.EINSTEIN,
    name: "Peter",
    description: "Casual, humorous teaching style with simple relatable examples.",
    imageSrc: "/characters/peter.png",
  },
  {
    id: Character.PIRATE,
    name: "Alyssa",
    description: "Calm and clear delivery focused on clarity and step-by-step flow.",
    imageSrc: "/characters/alyssa.png",
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
                    ? "scale-[1.02] shadow-[0_0_0_1px_rgba(252,196,255,0.6),0_0_28px_rgba(230,116,255,0.65),0_22px_46px_rgba(214,90,255,0.55)]"
                    : "hover:shadow-[0_18px_42px_rgba(214,90,255,0.5)]"
                }
                ${disabled ? "opacity-50 cursor-not-allowed" : ""}
              `}
            >
              <div
                className={`
                  relative h-full w-full rounded-2xl border
                  transition-[transform,border-color,box-shadow] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]
                  will-change-transform
                  [transform-style:preserve-3d]
                  ${isSelected ? "border-fuchsia-100/95" : "border-white/20 group-hover:border-fuchsia-100/85"}
                  ${!disabled ? "group-hover:[transform:rotateY(180deg)]" : ""}
                `}
              >
                {/* Front */}
                <div className="absolute inset-0 rounded-2xl [backface-visibility:hidden] overflow-hidden">
                  <div
                    className={`absolute inset-0 backdrop-blur-[18px] ${
                      isSelected
                        ? "bg-[linear-gradient(145deg,rgba(255,190,248,0.45),rgba(224,184,255,0.32),rgba(58,34,92,0.46))]"
                        : "bg-[linear-gradient(145deg,rgba(232,121,249,0.18),rgba(192,132,252,0.12),rgba(28,16,45,0.24))]"
                    }`}
                  />
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-0 top-0 h-8 bg-gradient-to-b from-white/18 to-transparent"
                  />
                  <div className="relative z-10 flex h-full flex-col items-center justify-center gap-3 px-3">
                    <div className="relative flex h-[108px] w-[108px] items-center justify-center rounded-full border border-fuchsia-100/55 bg-gradient-to-br from-fuchsia-300/45 via-violet-300/35 to-purple-600/45 backdrop-blur-md shadow-[0_10px_30px_rgba(196,76,255,0.38)] transition-all duration-300 group-hover:h-[78px] group-hover:w-[78px]">
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
                  <div className="absolute inset-0 backdrop-blur-[18px] bg-[linear-gradient(155deg,rgba(255,170,244,0.32),rgba(216,171,255,0.24),rgba(41,24,64,0.34))]" />
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

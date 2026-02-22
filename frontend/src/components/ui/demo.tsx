"use client";

import React from "react";
import { ArrowRight, Sparkles } from "lucide-react";

import NeuralBackground from "@/components/ui/flow-field-background";

export default function NeuralHeroDemo() {
  return (
    <div className="relative h-screen w-full overflow-hidden rounded-3xl">
      <NeuralBackground
        className="absolute inset-0 bg-transparent"
        color="#c084fc"
        trailOpacity={0.1}
        speed={0.8}
      />
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
        <div className="flex items-center gap-3 rounded-full border border-white/25 bg-white/10 px-5 py-2 text-sm text-white backdrop-blur-md">
          <Sparkles className="h-4 w-4 text-fuchsia-200" />
          <span>Flow-field glass atmosphere</span>
          <ArrowRight className="h-4 w-4 text-violet-200" />
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import Image from "next/image";
import NeuralBackground from "@/components/ui/flow-field-background";
import { joinWaitlist } from "@/lib/api";

type Status = "idle" | "loading" | "success" | "error";

export default function WaitlistPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) return;

    setStatus("loading");
    setErrorMessage("");

    try {
      await joinWaitlist(trimmed);
      setStatus("success");
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Something went wrong";
      if (raw.includes("409")) {
        setErrorMessage("This email is already on the waitlist.");
      } else if (raw.includes("422")) {
        setErrorMessage("Please enter a valid email address.");
      } else {
        setErrorMessage("Something went wrong. Please try again.");
      }
      setStatus("error");
    }
  };

  const canSubmit = status !== "loading" && email.trim().length > 0;

  return (
    <div className="purple-gradient-stage relative flex min-h-screen flex-col overflow-hidden text-white">
      {/* Background animation */}
      <div className="pointer-events-none absolute inset-0 z-0 opacity-55">
        <NeuralBackground
          className="bg-transparent"
          color="#d946ef"
          trailOpacity={0.08}
          particleCount={560}
          speed={0.72}
          mouseMode="attract"
          mouseStrength={0.065}
          interactionRadius={220}
        />
      </div>

      {/* Header */}
      <header className="relative z-10 flex flex-col items-center justify-center px-4 pb-1 pt-4">
        <div className="relative -mt-1">
          <Image
            src="/jestify-v2.png"
            alt="Jestify"
            width={224}
            height={224}
            className="h-56 w-56 object-contain relative z-10"
            priority
          />
          <span className="logo-unglow" aria-hidden="true" />
        </div>
        <h1 className="neo-grotesk-wordmark">
          <span className="text-[#8b5cf6]">J E S T</span>
          <span className="text-[#facc15]"> I F Y</span>
        </h1>
      </header>

      {/* Main content */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-4 pb-24">
        <div className="w-full max-w-md">
          {/* Tagline */}
          <div className="text-center mb-10">
            <p className="text-white/70 text-lg leading-relaxed">
              AI-powered educational videos taught by your favorite characters.
              <br />
              Be the first to know when we launch.
            </p>
          </div>

          {/* Success state */}
          {status === "success" ? (
            <div className="liquid-glass-card rounded-2xl px-8 py-10 text-center">
              <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-fuchsia-500/20 border border-fuchsia-400/30">
                <svg
                  className="w-7 h-7 text-fuchsia-300"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-white mb-3">
                You&apos;re on the list!
              </h2>
              <p className="text-white/65 text-sm leading-relaxed">
                We&apos;ve sent a confirmation to{" "}
                <span className="text-fuchsia-300">{email}</span>.
                <br />
                We&apos;ll notify you the moment Jestify launches.
              </p>
            </div>
          ) : (
            /* Form state */
            <form onSubmit={handleSubmit} className="space-y-3">
              <div
                className={[
                  "liquid-glass-toolbar flex items-center gap-3 rounded-[1.6rem] px-4 py-3",
                  "ring-1 ring-fuchsia-200/45",
                  "shadow-[0_0_0_1px_rgba(248,205,255,0.25),0_22px_55px_rgba(123,29,180,0.45)]",
                  "transition-colors duration-200",
                  status === "loading" ? "opacity-60" : "",
                ].join(" ")}
              >
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (status === "error") setStatus("idle");
                  }}
                  placeholder="Enter your email address"
                  disabled={status === "loading"}
                  className="flex-1 bg-transparent text-white placeholder:text-white/55 outline-none text-sm text-center"
                  autoComplete="email"
                />

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className={[
                    "p-2 rounded-xl transition-all duration-200 shrink-0",
                    canSubmit
                      ? "bg-gradient-to-br from-fuchsia-200 to-violet-300 text-violet-950 hover:from-fuchsia-100 hover:to-violet-200 shadow-[0_8px_20px_rgba(198,105,255,0.35)] cursor-pointer"
                      : "bg-white/12 text-white/45 cursor-not-allowed border border-white/15",
                  ].join(" ")}
                  title="Join waitlist"
                >
                  {status === "loading" ? (
                    <svg
                      className="w-4 h-4 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <circle
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="2"
                        className="opacity-25"
                      />
                      <path
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        fill="currentColor"
                        className="opacity-75"
                      />
                    </svg>
                  ) : (
                    <svg
                      className="w-4 h-4"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <line x1="12" y1="19" x2="12" y2="5" />
                      <polyline points="5 12 12 5 19 12" />
                    </svg>
                  )}
                </button>
              </div>

              {/* Error message */}
              {status === "error" && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 text-center">
                  <p className="text-sm text-red-400">{errorMessage}</p>
                </div>
              )}
            </form>
          )}
        </div>
      </main>
    </div>
  );
}

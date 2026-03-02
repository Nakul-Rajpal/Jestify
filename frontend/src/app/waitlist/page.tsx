"use client";

import { useState } from "react";
import { joinWaitlist } from "@/lib/api";

type Status = "idle" | "loading" | "success" | "error";

export default function WaitlistPage() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const handleSubmit = async () => {
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
    <div className="min-h-screen bg-zinc-900 text-white flex flex-col relative overflow-hidden">
      {/* Dot grid */}
      <div
        className="absolute inset-0 opacity-[0.06] pointer-events-none"
        style={{ backgroundImage: "radial-gradient(circle, #fff 1px, transparent 1px)", backgroundSize: "24px 24px" }}
      />
      {/* Glow */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[#E07B2A] opacity-10 blur-[160px] rounded-full pointer-events-none" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-6">
        <a href="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 bg-white/10 rounded-full flex items-center justify-center group-hover:bg-[#E07B2A] transition-colors duration-300">
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm-3.5 7a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm7 0a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm-6.75 5.5c.42-1 1.67-2 3.25-2s2.83 1 3.25 2H8.75z" />
            </svg>
          </div>
          <span className="font-serif text-xl tracking-tight text-white">Jestify</span>
        </a>

        <a
          href="/"
          className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition-colors duration-200"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Back to home
        </a>
      </nav>

      {/* Main */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <div className="w-full max-w-xl">
          <div className="text-[#E07B2A] flex justify-center mb-8">
            <svg className="w-12 h-12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm-3.5 7a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm7 0a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm-6.75 5.5c.42-1 1.67-2 3.25-2s2.83 1 3.25 2H8.75z" />
            </svg>
          </div>

          <h1 className="font-serif text-5xl md:text-6xl mb-5 leading-[0.95]">
            Stop pretending to read.
          </h1>

          <p className="text-gray-400 text-lg mb-10 leading-relaxed">
            AI-powered educational videos taught by your favorite characters.
            <br />
            Be the first to know when we launch.
          </p>

          {status === "success" ? (
            <div className="bg-white/5 border border-white/10 rounded-2xl px-8 py-10">
              <div className="w-14 h-14 rounded-full bg-[#E07B2A]/20 border border-[#E07B2A]/40 flex items-center justify-center mx-auto mb-5">
                <svg className="w-7 h-7 text-[#E07B2A]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <h2 className="font-serif text-2xl text-white mb-3">You&apos;re on the list!</h2>
              <p className="text-gray-400 text-sm leading-relaxed">
                Confirmation sent to <span className="text-[#E07B2A]">{email}</span>.<br />
                We&apos;ll notify you the moment Jestify launches.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <form onSubmit={(e) => { e.preventDefault(); void handleSubmit(); }} className="flex flex-col sm:flex-row gap-4">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (status === "error") setStatus("idle");
                  }}
                  placeholder="student@university.edu"
                  disabled={status === "loading"}
                  className="flex-1 px-6 py-4 rounded-full bg-white/5 border border-white/20 text-white placeholder-gray-500 focus:outline-none focus:border-[#E07B2A] transition disabled:opacity-60"
                  autoComplete="email"
                />
                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="px-8 py-4 bg-[#E07B2A] text-black rounded-full font-bold hover:bg-white hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:hover:bg-[#E07B2A] whitespace-nowrap"
                >
                  {status === "loading" ? "Joining..." : "Join Waitlist"}
                </button>
              </form>
              {status === "error" && (
                <p className="text-sm text-red-400">{errorMessage}</p>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

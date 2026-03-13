"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { joinWaitlist } from "@/lib/api";

type WaitlistStatus = "idle" | "loading" | "success" | "error";

const CHARACTERS = [
  {
    name: "The Athlete",
    subtitle: "Baller Analogies",
    image: "/characters/lebron.png",
    description: "Physics explained through plays, momentum, and game strategy.",
  },
  {
    name: "The Fighter",
    subtitle: "Power Level Breakdowns",
    image: "/characters/goku.png",
    description: "Complex concepts become battles of energy and transformation.",
  },
  {
    name: "The Everyman",
    subtitle: "Relatable Humor",
    image: "/characters/peter.png",
    description: "Makes calculus feel like a conversation at the dinner table.",
  },
  {
    name: "The Artist",
    subtitle: "Pop Culture References",
    image: "/characters/taylor.png",
    description: "Every theorem is a story arc. Every formula is a lyric.",
  },
];

export default function Home() {
  const [email, setEmail] = useState("");
  const [waitlistStatus, setWaitlistStatus] = useState<WaitlistStatus>("idle");
  const [waitlistError, setWaitlistError] = useState("");

  const handleWaitlistSubmit = async () => {
    const trimmed = email.trim();
    if (!trimmed) return;

    setWaitlistStatus("loading");
    setWaitlistError("");

    try {
      await joinWaitlist(trimmed);
      setWaitlistStatus("success");
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Something went wrong";
      if (raw.includes("409")) {
        setWaitlistError("This email is already on the waitlist.");
      } else if (raw.includes("422")) {
        setWaitlistError("Please enter a valid email address.");
      } else {
        setWaitlistError("Something went wrong. Please try again.");
      }
      setWaitlistStatus("error");
    }
  };

  const canSubmit = waitlistStatus !== "loading" && email.trim().length > 0;

  return (
    <div className="antialiased overflow-x-hidden bg-[#0D0B1A] text-[#F5F5F7]">

      {/* ── Floating Nav ── */}
      <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50 w-[90%] max-w-4xl">
        <div className="bg-[#1A1730]/80 backdrop-blur-md border border-white/8 rounded-full px-6 py-3 flex items-center justify-between shadow-lg shadow-black/20">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-[#FACC15] rounded-full flex items-center justify-center">
              <svg className="w-4 h-4 text-[#0D0B1A]" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm-3.5 7a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm7 0a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm-6.75 5.5c.42-1 1.67-2 3.25-2s2.83 1 3.25 2H8.75z" />
              </svg>
            </div>
            <span className="font-bold text-xl tracking-tight">Jestify</span>
          </div>

          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-[#A8A3C0]">
            <a href="#how-it-works" className="hover:text-white transition">The Engine</a>
            <a href="#voices" className="hover:text-white transition">Voices</a>
            <a href="#sync" className="hover:text-white transition">Syllabus Sync</a>
          </div>

          <a
            href="#waitlist"
            className="bg-[#FACC15] text-[#0D0B1A] px-5 py-2 rounded-full text-sm font-semibold hover:bg-[#FDE047] transition-colors duration-300"
          >
            Get Early Access
          </a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <header className="relative min-h-screen flex flex-col items-center justify-center pt-24 pb-12 px-4 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute top-20 left-[5%] w-64 h-64 bg-[#A855F7]/15 rounded-full blur-[120px]" />
          <div className="absolute bottom-20 right-[5%] w-96 h-96 bg-[#FACC15]/10 rounded-full blur-[120px]" />
        </div>

        <div className="container max-w-5xl mx-auto text-center relative z-10 mt-12">
          <div className="inline-flex items-center gap-2 border border-[#FACC15]/30 rounded-full px-4 py-1.5 mb-8 bg-[#FACC15]/10 backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-[#FACC15] animate-pulse-dot" />
            <span className="text-xs font-medium tracking-wide uppercase text-[#FACC15]">The Analogy Engine is Live</span>
          </div>

          <h1 className="font-extrabold text-6xl md:text-[88px] leading-[0.92] mb-8 tracking-tight">
            Complex physics.<br />
            <span className="italic font-light text-[#A8A3C0]">Explained by</span><br />
            LeBron James.
          </h1>

          <p className="text-lg md:text-xl text-[#A8A3C0] max-w-2xl mx-auto mb-10 leading-relaxed">
            Jestify transforms your boring syllabus into personalized explainer videos.
            AI analogies tailored to your interests—narrated by your favorite personas.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <a
              href="#waitlist"
              className="group px-8 py-4 bg-[#FACC15] text-[#0D0B1A] rounded-full font-bold hover:shadow-[0_20px_50px_rgba(250,204,21,0.35)] transition-all duration-300 flex items-center gap-2"
            >
              Join the Waitlist
              <svg
                className="w-4 h-4 -rotate-45 group-hover:rotate-0 transition-transform duration-300"
                viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round" strokeLinejoin="round"
              >
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </a>
            <Link
              href="/generate"
              className="px-8 py-4 bg-[#1A1730] border border-white/12 text-white rounded-full font-medium hover:border-[#FACC15]/40 transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4 text-[#FACC15]" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              Generate Video
            </Link>
          </div>
        </div>

        {/* Floating decorative cards */}
        <div className="hidden lg:block absolute top-1/2 left-[6%] -translate-y-1/2 w-60 card p-4 rounded-2xl shadow-lg -rotate-6 animate-flutter">
          <div className="flex items-center gap-3 border-b border-white/8 pb-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-[#FACC15]/15 flex items-center justify-center">
              <svg className="w-4 h-4 text-[#FACC15]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <div>
              <div className="text-[10px] font-bold text-[#6B6589] uppercase">Input Topic</div>
              <div className="text-sm font-semibold">Thermodynamics</div>
            </div>
          </div>
          <p className="text-xs text-[#A8A3C0] leading-relaxed">
            &ldquo;Imagine heat transfer like passing the ball in the 4th quarter...&rdquo;
          </p>
        </div>

        <div className="hidden lg:block absolute top-1/2 right-[6%] -translate-y-1/2 w-60 card-elevated p-4 rounded-2xl shadow-2xl rotate-3 animate-flutter-delayed">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-[#6B6589] font-mono tracking-wider">GENERATING...</span>
            <svg className="w-4 h-4 text-[#FACC15] animate-spin" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" className="opacity-25" />
              <path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" className="opacity-75" />
            </svg>
          </div>
          <div className="h-28 bg-[#0D0B1A] rounded-xl flex items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-[#A855F7]/20 via-[#0D0B1A] to-[#1A1730]" />
            <div className="w-10 h-10 bg-white/10 backdrop-blur-sm rounded-full flex items-center justify-center relative z-10">
              <svg className="w-4 h-4 text-white ml-0.5" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
            </div>
          </div>
        </div>
      </header>

      {/* ── The Analogy Engine ── */}
      <section id="how-it-works" className="py-24">
        <div className="container mx-auto px-6">
          <div className="text-center mb-20">
            <h2 className="font-extrabold text-5xl md:text-6xl mb-6">The Analogy Engine</h2>
            <p className="text-[#A8A3C0] max-w-xl mx-auto leading-relaxed">
              We don&apos;t just summarize text. We translate concepts into analogies
              tailored to your psychological profile.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-12 items-center max-w-5xl mx-auto">
            <div className="relative group">
              <div className="absolute inset-0 bg-[#A855F7]/10 rounded-[2rem] rotate-3 transition-transform duration-500 group-hover:rotate-6" />
              <div className="relative card p-8 rounded-[2rem]">
                <div className="flex items-center gap-4 mb-6">
                  <svg className="w-8 h-8 text-[#6B6589]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  <div>
                    <h3 className="font-bold text-2xl">The Syllabus</h3>
                    <p className="text-xs text-[#6B6589] uppercase tracking-widest">Raw Input</p>
                  </div>
                </div>
                <div className="font-mono text-xs text-[#A8A3C0] bg-[#0D0B1A] p-4 rounded-xl border border-white/8 space-y-3">
                  <p>Newton&apos;s First Law states that every object will remain at rest or in uniform motion in a straight line unless compelled to change its state by the action of an external force.</p>
                  <div className="h-1 w-full bg-[#252240] rounded" />
                  <div className="h-1 w-2/3 bg-[#252240] rounded" />
                </div>
              </div>
            </div>

            <div className="relative group">
              <div className="absolute inset-0 bg-[#FACC15]/20 rounded-[2rem] -rotate-2 transition-transform duration-500 group-hover:-rotate-3" />
              <div className="relative bg-[#252240] p-8 rounded-[2rem] border border-white/12 overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-[#A855F7]/10 to-transparent" />
                <div className="relative z-10">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="w-10 h-10 rounded-full border-2 border-[#FACC15] overflow-hidden shrink-0">
                      <Image src="/characters/lebron.png" alt="LeBron" width={40} height={40} className="w-full h-full object-cover" />
                    </div>
                    <div>
                      <h3 className="font-bold text-2xl">The Explanation</h3>
                      <p className="text-xs text-[#FACC15] uppercase tracking-widest">Personalized Output</p>
                    </div>
                  </div>
                  <div className="bg-white/5 backdrop-blur-md p-6 rounded-xl border border-white/8">
                    <p className="text-lg italic leading-relaxed text-[#F5F5F7]">
                      &ldquo;Alright, think of Inertia like a lazy defender. He ain&apos;t moving unless contact forces him to. That&apos;s the external force, fam.&rdquo;
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Personalization ── */}
      <section className="py-24 overflow-hidden relative">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-[#A855F7] opacity-[0.07] blur-[180px] rounded-full pointer-events-none" />

        <div className="container mx-auto px-6 relative z-10">
          <div className="flex flex-col md:flex-row items-center justify-between gap-16">
            <div className="w-full md:w-1/2">
              <p className="text-[#FACC15] font-mono text-sm mb-4 tracking-widest uppercase">
                AI Personalization
              </p>
              <h2 className="font-extrabold text-5xl md:text-6xl mb-6 leading-[1.05]">
                Insights from your feed,<br />
                <span className="italic font-light text-[#A8A3C0]">videos for</span> your brain.
              </h2>
              <p className="text-[#A8A3C0] text-lg mb-8 leading-relaxed">
                We don&apos;t post to your social media. We learn from it. Connect your platforms to
                let Jestify analyze your interests—whether it&apos;s gaming, makeup, or golf. We use
                those insights to craft the perfect analogy for your course.
              </p>
              <ul className="space-y-4">
                {[
                  "Connect account securely (Read-only access)",
                  'We identify your "Sense of Humor" profile',
                  "Generate distraction-free videos on Jestify",
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-4">
                    <div className="w-8 h-8 rounded-full bg-white/5 border border-white/8 flex items-center justify-center text-[#FACC15] text-sm font-semibold shrink-0">
                      {i + 1}
                    </div>
                    <span className="text-[#A8A3C0]">{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="w-full md:w-5/12">
              <div className="card-elevated p-3">
                <div className="bg-[#0D0B1A] rounded-xl p-6 space-y-4">
                  <div>
                    <span className="inline-block px-3 py-1 bg-[#FACC15] text-[#0D0B1A] text-[10px] font-bold rounded mb-3">
                      CHAPTER 3: MOMENTUM
                    </span>
                    <h4 className="font-bold text-2xl text-white">The Swing Analogy</h4>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div className="h-full w-2/3 bg-[#FACC15] rounded-full" />
                  </div>
                  <div className="flex items-center justify-between text-[#6B6589] text-xs">
                    <span>2:14</span>
                    <span>3:22</span>
                  </div>
                  <div className="flex items-center gap-3 pt-2 border-t border-white/8">
                    <div className="w-9 h-9 rounded-full overflow-hidden border border-[#FACC15]/40 shrink-0">
                      <Image src="/characters/goku.png" alt="Goku" width={36} height={36} className="w-full h-full object-cover" />
                    </div>
                    <div>
                      <div className="text-white text-sm font-medium">Goku</div>
                      <div className="text-[#6B6589] text-xs">Physics 101 · Chapter 3</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Syllabus Sync ── */}
      <section id="sync" className="py-24">
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center gap-16 max-w-5xl mx-auto">

            <div className="w-full md:w-1/2 order-2 md:order-1">
              <div className="relative">
                <div className="w-full card p-6 relative z-30 hover:-translate-y-2 transition-transform duration-500">
                  <div className="flex items-center justify-between mb-6">
                    <span className="font-bold text-xl">Syllabus.pdf</span>
                    <div className="flex gap-1.5">
                      <span className="w-3 h-3 rounded-full bg-red-400" />
                      <span className="w-3 h-3 rounded-full bg-yellow-400" />
                      <span className="w-3 h-3 rounded-full bg-green-400" />
                    </div>
                  </div>
                  <div className="space-y-3">
                    {[
                      { month: "Oct", day: "12", title: "Midterm: Kinematics", status: "Video Playlist Generated (4)", done: true },
                      { month: "Oct", day: "24", title: "Essay: Gravity", status: "Processing...", done: false },
                    ].map((item) => (
                      <div key={item.day} className="flex items-center gap-4 p-3 bg-[#0D0B1A] rounded-xl border border-white/8">
                        <div className="text-center min-w-[48px]">
                          <div className="text-[10px] text-[#6B6589] uppercase">{item.month}</div>
                          <div className="text-xl font-bold leading-tight">{item.day}</div>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold truncate">{item.title}</div>
                          <div className={`text-xs ${item.done ? "text-[#FACC15]" : "text-[#6B6589]"}`}>{item.status}</div>
                        </div>
                        {item.done ? (
                          <svg className="w-5 h-5 text-green-500 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                        ) : (
                          <svg className="w-5 h-5 text-[#6B6589] shrink-0 animate-spin" viewBox="0 0 24 24" fill="none">
                            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" className="opacity-25" />
                            <path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" className="opacity-75" />
                          </svg>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="absolute top-4 left-4 w-full h-full bg-[#252240] rounded-2xl z-20 border border-white/6" />
                <div className="absolute top-8 left-8 w-full h-full bg-[#1A1730] rounded-2xl z-10 border border-white/4" />
              </div>
            </div>

            <div className="w-full md:w-1/2 order-1 md:order-2">
              <h2 className="font-extrabold text-4xl md:text-5xl mb-6">Syllabus Sync.</h2>
              <p className="text-[#A8A3C0] text-lg mb-8 leading-relaxed">
                Upload your PDF or connect to Canvas. We scrape the dates, topics, and exams to
                build a custom study playlist of animated explainers narrated by your chosen persona.
              </p>
              <div className="flex flex-wrap gap-3">
                {["PDF Upload", "Canvas LMS", "Blackboard"].map((tag) => (
                  <div key={tag} className="px-4 py-2 bg-[#1A1730] border border-white/10 rounded-full text-sm font-medium text-[#A8A3C0]">
                    {tag}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Voices ── */}
      <section id="voices" className="py-24">
        <div className="container mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="font-extrabold text-5xl mb-4">Choose Your Narrator</h2>
            <p className="text-[#A8A3C0]">Voice cloning technology tailored to engagement.</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 max-w-5xl mx-auto">
            {CHARACTERS.map((char) => (
              <div key={char.name} className="group cursor-pointer">
                <div className="relative h-[280px] md:h-[360px] mb-4 overflow-hidden rounded-[1.5rem] border border-white/8">
                  <Image
                    src={char.image}
                    alt={char.name}
                    fill
                    className="object-cover grayscale group-hover:grayscale-0 transition-all duration-500 group-hover:scale-105"
                  />
                  <div className="absolute bottom-0 left-0 w-full p-4 bg-gradient-to-t from-black/80 to-transparent">
                    <div className="text-white font-bold text-lg leading-tight">{char.name}</div>
                    <div className="text-[#FACC15] text-xs uppercase tracking-wider">{char.subtitle}</div>
                  </div>
                </div>
                <p className="text-sm text-[#A8A3C0] px-1 leading-snug">{char.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Marquee ── */}
      <div className="py-5 bg-[#FACC15] overflow-hidden whitespace-nowrap">
        <div className="animate-marquee">
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] opacity-90">LEARN FASTER.</span>
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] italic opacity-70">RETAIN MORE.</span>
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] opacity-90">JESTIFY YOUR MIND.</span>
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] italic opacity-70">NO MORE BORING LECTURES.</span>
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] opacity-90">LEARN FASTER.</span>
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] italic opacity-70">RETAIN MORE.</span>
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] opacity-90">JESTIFY YOUR MIND.</span>
          <span className="font-bold text-2xl mx-8 text-[#0D0B1A] italic opacity-70">NO MORE BORING LECTURES.</span>
        </div>
      </div>

      {/* ── Waitlist ── */}
      <section id="waitlist" className="py-32 bg-[#1A1730] relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-[0.04] pointer-events-none"
          style={{ backgroundImage: "radial-gradient(circle, #A855F7 1px, transparent 1px)", backgroundSize: "24px 24px" }}
        />

        <div className="container max-w-2xl mx-auto px-6 text-center relative z-10">
          <div className="text-[#FACC15] flex justify-center mb-8">
            <svg className="w-12 h-12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm-3.5 7a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm7 0a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm-6.75 5.5c.42-1 1.67-2 3.25-2s2.83 1 3.25 2H8.75z" />
            </svg>
          </div>

          <h2 className="font-extrabold text-5xl md:text-7xl mb-6 leading-[0.95]">
            Stop pretending to read.
          </h2>
          <p className="text-[#A8A3C0] text-lg mb-10 leading-relaxed">
            Join thousands of students reclaiming their GPA with bespoke AI video courses.
          </p>

          {waitlistStatus === "success" ? (
            <div className="card-elevated px-8 py-10">
              <div className="w-14 h-14 rounded-full bg-[#FACC15]/15 border border-[#FACC15]/30 flex items-center justify-center mx-auto mb-5">
                <svg className="w-7 h-7 text-[#FACC15]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <h3 className="font-bold text-2xl text-white mb-3">You&apos;re on the list!</h3>
              <p className="text-[#A8A3C0] text-sm leading-relaxed">
                Confirmation sent to <span className="text-[#FACC15]">{email}</span>.<br />
                We&apos;ll notify you the moment Jestify launches.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <form onSubmit={(e) => { e.preventDefault(); void handleWaitlistSubmit(); }} className="flex flex-col sm:flex-row gap-4">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (waitlistStatus === "error") setWaitlistStatus("idle");
                  }}
                  placeholder="student@university.edu"
                  disabled={waitlistStatus === "loading"}
                  className="flex-1 px-6 py-4 rounded-full bg-white/5 border border-white/15 text-white placeholder-[#6B6589] focus:outline-none focus:border-[#FACC15] transition disabled:opacity-60"
                />
                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="px-8 py-4 bg-[#FACC15] text-[#0D0B1A] rounded-full font-bold hover:bg-[#FDE047] hover:scale-105 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 disabled:hover:bg-[#FACC15] whitespace-nowrap"
                >
                  {waitlistStatus === "loading" ? "Joining..." : "Join Waitlist"}
                </button>
              </form>
              {waitlistStatus === "error" && (
                <p className="text-sm text-red-400">{waitlistError}</p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="bg-[#0A0818] text-[#6B6589] py-12 text-sm">
        <div className="container mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <div>&copy; 2025 Jestify Inc. All rights reserved.</div>
          <div className="flex gap-6">
            <a href="#" className="hover:text-[#FACC15] transition">Twitter</a>
            <a href="#" className="hover:text-[#FACC15] transition">Instagram</a>
            <a href="#" className="hover:text-[#FACC15] transition">Terms</a>
          </div>
        </div>
      </footer>

    </div>
  );
}

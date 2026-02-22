"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getLibrary } from "@/lib/api";
import { SubjectSummary, TopicSummary } from "@/types";

export default function LibraryPage() {
  const [subjects, setSubjects] = useState<SubjectSummary[]>([]);
  const [expandedSubject, setExpandedSubject] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLibrary() {
      try {
        const data = await getLibrary();
        setSubjects(data.subjects);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load library");
      } finally {
        setLoading(false);
      }
    }
    fetchLibrary();
  }, []);

  const toggleSubject = (subjectId: string) => {
    setExpandedSubject((prev) => (prev === subjectId ? null : subjectId));
  };

  return (
    <div className="flex flex-col min-h-screen bg-neutral-900 text-white">
      {/* Header */}
      <header className="flex items-center justify-between pt-6 pb-2 px-4 max-w-4xl mx-auto w-full">
        <Link href="/">
          <h1 className="text-xl font-semibold tracking-tight">
            <span className="text-white">Jest</span>
            <span className="text-neutral-400">ify</span>
          </h1>
        </Link>
        <nav className="flex gap-4">
          <Link
            href="/"
            className="text-sm text-neutral-400 hover:text-white transition-colors"
          >
            Generate
          </Link>
          <Link href="/library" className="text-sm text-white font-medium">
            Library
          </Link>
        </nav>
      </header>

      <main className="flex-1 px-4 py-8 max-w-4xl mx-auto w-full">
        <h2 className="text-2xl font-semibold mb-6">Video Library</h2>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <p className="text-neutral-400">Loading library...</p>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center py-16">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {!loading && !error && subjects.length === 0 && (
          <div className="text-center py-16">
            <p className="text-neutral-400">
              No videos in the library yet. Generate your first video to get
              started!
            </p>
            <Link
              href="/"
              className="mt-4 inline-block px-6 py-2.5 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-300 hover:text-white hover:border-neutral-500 transition-colors"
            >
              Generate a video
            </Link>
          </div>
        )}

        {!loading && !error && subjects.length > 0 && (
          <div className="space-y-4">
            {subjects.map((subject) => (
              <SubjectCard
                key={subject.id}
                subject={subject}
                isExpanded={expandedSubject === subject.id}
                onToggle={() => toggleSubject(subject.id)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function SubjectCard({
  subject,
  isExpanded,
  onToggle,
}: {
  subject: SubjectSummary;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border border-neutral-700 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-neutral-800/50 transition-colors cursor-pointer"
      >
        <div className="text-left">
          <h3 className="text-lg font-medium text-white">{subject.name}</h3>
          {subject.description && (
            <p className="text-sm text-neutral-400 mt-1">
              {subject.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4 text-sm text-neutral-400">
          <span>
            {subject.topic_count}{" "}
            {subject.topic_count === 1 ? "topic" : "topics"}
          </span>
          <span>
            {subject.video_count}{" "}
            {subject.video_count === 1 ? "video" : "videos"}
          </span>
          <svg
            className={`w-5 h-5 transition-transform ${isExpanded ? "rotate-180" : ""}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-neutral-700 p-4 space-y-3">
          {subject.topics.map((topic) => (
            <TopicRow
              key={topic.id}
              topic={topic}
              subjectId={subject.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TopicRow({
  topic,
  subjectId,
}: {
  topic: TopicSummary;
  subjectId: string;
}) {
  return (
    <Link
      href={`/library/${subjectId}/topics/${topic.id}`}
      className="flex items-center justify-between p-3 rounded-lg bg-neutral-800/50 hover:bg-neutral-800 transition-colors"
    >
      <div>
        <p className="text-sm font-medium text-white">{topic.name}</p>
        {topic.description && (
          <p className="text-xs text-neutral-400 mt-0.5">
            {topic.description}
          </p>
        )}
      </div>
      <span className="text-xs text-neutral-500">
        {topic.video_count} {topic.video_count === 1 ? "video" : "videos"}
      </span>
    </Link>
  );
}

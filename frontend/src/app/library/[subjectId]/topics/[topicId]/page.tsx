"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import VideoPlayer from "@/components/VideoPlayer";
import { getTopicVideos, BASE_URL } from "@/lib/api";
import { TopicDetailResponse, VideoSummary } from "@/types";

export default function TopicPage() {
  const params = useParams();
  const subjectId = params.subjectId as string;
  const topicId = params.topicId as string;

  const [topic, setTopic] = useState<TopicDetailResponse | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<VideoSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchTopic() {
      try {
        const data = await getTopicVideos(subjectId, topicId);
        setTopic(data);
        if (data.videos.length > 0) {
          setSelectedVideo(data.videos[0]);
        }
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load topic"
        );
      } finally {
        setLoading(false);
      }
    }
    fetchTopic();
  }, [subjectId, topicId]);

  if (loading) {
    return (
      <div className="flex flex-col min-h-screen bg-neutral-900 text-white">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-neutral-400">Loading...</p>
        </main>
      </div>
    );
  }

  if (error || !topic) {
    return (
      <div className="flex flex-col min-h-screen bg-neutral-900 text-white">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-red-400">{error || "Topic not found"}</p>
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-neutral-900 text-white">
      <Header />

      <main className="flex-1 px-4 py-8 max-w-4xl mx-auto w-full">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-neutral-400 mb-6">
          <Link
            href="/library"
            className="hover:text-white transition-colors"
          >
            Library
          </Link>
          <span>/</span>
          <span>{topic.subject_name}</span>
          <span>/</span>
          <span className="text-white">{topic.name}</span>
        </div>

        <h2 className="text-2xl font-semibold mb-2">{topic.name}</h2>
        {topic.description && (
          <p className="text-neutral-400 mb-6">{topic.description}</p>
        )}

        {/* Video player */}
        {selectedVideo && (
          <div className="mb-8">
            <VideoPlayer
              videoUrl={`${BASE_URL}${selectedVideo.video_url}`}
              thumbnailUrl={
                selectedVideo.thumbnail_url
                  ? `${BASE_URL}${selectedVideo.thumbnail_url}`
                  : undefined
              }
              title={selectedVideo.title}
            />
          </div>
        )}

        {/* Video list */}
        {topic.videos.length > 1 && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-neutral-400 mb-2">
              All videos
            </h3>
            {topic.videos.map((video) => (
              <button
                key={video.job_id}
                onClick={() => setSelectedVideo(video)}
                className={`w-full text-left flex items-center justify-between p-4 rounded-lg border transition-colors cursor-pointer ${
                  selectedVideo?.job_id === video.job_id
                    ? "border-white bg-neutral-800"
                    : "border-neutral-700 hover:bg-neutral-800/50"
                }`}
              >
                <div>
                  <p className="font-medium text-white">{video.title}</p>
                  <p className="text-xs text-neutral-400 mt-1">
                    {video.character} / {video.difficulty} /{" "}
                    {new Date(video.created_at).toLocaleDateString()}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}

        {topic.videos.length === 0 && (
          <p className="text-neutral-400 text-center py-8">
            No videos for this topic yet.
          </p>
        )}
      </main>
    </div>
  );
}

function Header() {
  return (
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
        <Link
          href="/library"
          className="text-sm text-neutral-400 hover:text-white transition-colors"
        >
          Library
        </Link>
      </nav>
    </header>
  );
}

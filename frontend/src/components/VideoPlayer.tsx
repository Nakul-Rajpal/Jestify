"use client";

import { useState, useRef } from "react";

interface VideoPlayerProps {
  videoUrl: string;
  thumbnailUrl?: string | null;
  title?: string;
}

export default function VideoPlayer({
  videoUrl,
  thumbnailUrl,
  title = "Your Educational Video",
}: VideoPlayerProps) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const videoRef = useRef<HTMLVideoElement>(null);

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="mb-4">
        <h3 className="text-lg font-medium text-white">{title}</h3>
      </div>

      <div className="rounded-xl overflow-hidden bg-black border border-neutral-800 relative">
        {isLoading && !hasError && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/80 z-10">
            <div className="flex flex-col items-center gap-2">
              <svg className="w-8 h-8 animate-spin text-white" viewBox="0 0 50 50" fill="none">
                <circle cx="25" cy="25" r="20" stroke="currentColor" strokeWidth="3" className="text-neutral-700" />
                <path d="M25 5a20 20 0 0117.32 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" className="text-white" />
              </svg>
              <span className="text-xs text-neutral-400">Loading video...</span>
            </div>
          </div>
        )}

        {hasError && (
          <div className="aspect-video flex items-center justify-center bg-neutral-900">
            <div className="text-center px-6">
              <p className="text-sm text-red-400 mb-2">Failed to load video</p>
              <button
                onClick={() => {
                  setHasError(false);
                  setIsLoading(true);
                  if (videoRef.current) {
                    videoRef.current.load();
                  }
                }}
                className="text-xs text-neutral-400 hover:text-white underline cursor-pointer"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        <video
          ref={videoRef}
          controls
          playsInline
          preload="auto"
          className={`w-full aspect-video ${hasError ? "hidden" : ""}`}
          poster={thumbnailUrl || undefined}
          onLoadedData={() => setIsLoading(false)}
          onError={() => {
            setHasError(true);
            setIsLoading(false);
          }}
        >
          <source src={videoUrl} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>

      <div className="mt-4 flex items-center justify-center gap-3">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20">
          <svg
            className="w-4 h-4 text-green-400"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span className="text-sm text-green-400">Video generated successfully</span>
        </div>
        <a
          href={videoUrl}
          download="jestify-video.mp4"
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 hover:bg-blue-500/20 transition-colors cursor-pointer"
        >
          <svg
            className="w-4 h-4 text-blue-400"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          <span className="text-sm text-blue-400">Download</span>
        </a>
      </div>
    </div>
  );
}

"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string | null;
  loading: boolean;
  error: string | null;
}

export default function MarkdownSection({ markdown, loading, error }: Props) {
  if (loading)
    return (
      <div className="space-y-2 animate-pulse">
        {[...Array(6)].map((_, i) => (
          <div key={i} className={`h-4 bg-slate-100 rounded ${i % 3 === 2 ? "w-3/4" : "w-full"}`} />
        ))}
      </div>
    );

  if (error)
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );

  if (!markdown) return null;

  return (
    <div className="prose-dashboard">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
    </div>
  );
}

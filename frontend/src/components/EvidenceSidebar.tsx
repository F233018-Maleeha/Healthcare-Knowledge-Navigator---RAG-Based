import { useEffect } from "react";
import type { RetrievedChunk } from "../api/types";
import { SourceCard } from "./SourceCard";

interface EvidenceSidebarProps {
  chunks: RetrievedChunk[];
  loading: boolean;
  highlightedChunkId: string | null;
  hasAnswered: boolean;
}

export function EvidenceSidebar({ chunks, loading, highlightedChunkId, hasAnswered }: EvidenceSidebarProps) {
  useEffect(() => {
    if (!highlightedChunkId) return;
    document
      .getElementById(`src-${highlightedChunkId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightedChunkId]);

  return (
    <div className="bg-panel border border-line rounded-md p-5">
      <h2 className="font-display text-[15px] uppercase tracking-wide text-ink-soft mb-3.5">
        Evidence retrieved
      </h2>

      {loading && <p className="text-ink-soft italic text-sm">Searching corpus…</p>}

      {!loading && chunks.length === 0 && !hasAnswered && (
        <p className="text-ink-soft italic text-sm">
          Retrieved source excerpts will appear here once you ask a question.
        </p>
      )}

      {!loading && chunks.length === 0 && hasAnswered && (
        <p className="text-ink-soft italic text-sm">
          No sources in the corpus were relevant enough to inform an answer to this question.
        </p>
      )}

      {!loading &&
        chunks.map((rc) => (
          <SourceCard
            key={rc.chunk.chunk_id}
            retrievedChunk={rc}
            highlighted={rc.chunk.chunk_id === highlightedChunkId}
          />
        ))}
    </div>
  );
}

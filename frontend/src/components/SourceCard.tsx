import type { RetrievedChunk } from "../api/types";

const TIER_STYLES: Record<number, string> = {
  1: "bg-green-dim text-green",
  2: "bg-teal-dim text-teal",
  3: "bg-amber-dim text-amber",
  4: "bg-red-dim text-red",
};

interface SourceCardProps {
  retrievedChunk: RetrievedChunk;
  highlighted: boolean;
}

export function SourceCard({ retrievedChunk, highlighted }: SourceCardProps) {
  const { chunk } = retrievedChunk;

  return (
    <div
      id={`src-${chunk.chunk_id}`}
      className={`border rounded p-3 mb-2.5 transition-shadow ${
        highlighted ? "border-amber shadow-[0_0_0_3px_var(--color-amber-dim)]" : "border-line"
      }`}
    >
      <div className="flex justify-between items-start gap-2 mb-1.5">
        <div className="font-body font-semibold text-[13px] leading-snug">{chunk.title}</div>
        <div className="font-mono text-[10px] text-teal shrink-0">{chunk.chunk_id}</div>
      </div>
      <div className="text-[11px] text-ink-soft font-mono mb-1.5">
        <span className={`px-1.5 py-px rounded-full text-[9.5px] uppercase mr-1 ${TIER_STYLES[chunk.authority_tier]}`}>
          tier {chunk.authority_tier}
        </span>
        {chunk.evidence_grade ?? "n/a"} · {chunk.publication_date}
      </div>
      <div className="text-[12.5px] leading-relaxed text-ink-soft border-t border-dashed border-line pt-1.5">
        {chunk.text}
      </div>
    </div>
  );
}

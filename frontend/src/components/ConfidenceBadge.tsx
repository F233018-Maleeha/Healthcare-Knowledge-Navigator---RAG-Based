import { useState } from "react";
import type { ConfidenceResult } from "../api/types";

const LABEL_STYLES: Record<ConfidenceResult["label"], string> = {
  high: "bg-green-dim text-green border border-green",
  moderate: "bg-amber-dim text-amber border border-amber",
  low: "bg-red-dim text-red border border-red",
};

const BREAKDOWN_COPY: Record<keyof ConfidenceResult["breakdown"], string> = {
  retrieval_agreement: "independent sources supporting the answer",
  source_authority: "average evidence tier of cited sources",
  recency: "how current the cited sources are",
  self_rating: "model's own per-claim certainty, verified against context",
};

interface ConfidenceBadgeProps {
  confidence: ConfidenceResult;
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2.5">
        <span
          className={`font-mono text-xs font-semibold tracking-wide px-2.5 py-1 rounded ${LABEL_STYLES[confidence.label]}`}
        >
          {confidence.label.toUpperCase()} CONFIDENCE — {confidence.score}/100
        </span>
        <button
          onClick={() => setOpen((o) => !o)}
          className="text-xs text-ink-soft underline decoration-dotted"
        >
          {open ? "hide breakdown" : "show breakdown"}
        </button>
      </div>

      {open && (
        <div className="text-[12.5px] text-ink-soft bg-paper border border-line rounded px-3 py-2.5 mt-2 leading-relaxed">
          {(Object.keys(confidence.breakdown) as Array<keyof ConfidenceResult["breakdown"]>).map((key) => (
            <div key={key}>
              <code className="font-mono text-ink">{key.replace(/_/g, " ")}</code>{" "}
              {confidence.breakdown[key]}/100 — {BREAKDOWN_COPY[key]}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

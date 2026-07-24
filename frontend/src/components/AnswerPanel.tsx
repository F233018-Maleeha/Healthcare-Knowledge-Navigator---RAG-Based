import type { FeedbackRating, GeneratedAnswer, ConfidenceResult } from "../api/types";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { ClaimList } from "./ClaimList";
import { ContradictionBox, GapBox } from "./Callouts";
import { FeedbackBar } from "./FeedbackBar";

interface AnswerPanelProps {
  answer: GeneratedAnswer | null;
  confidence: ConfidenceResult | null;
  loading: boolean;
  error: string | null;
  onCitationClick: (chunkId: string) => void;
  feedbackStatus: "idle" | "sending" | "sent" | "error";
  onRate: (rating: FeedbackRating) => void;
}

export function AnswerPanel({
  answer,
  confidence,
  loading,
  error,
  onCitationClick,
  feedbackStatus,
  onRate,
}: AnswerPanelProps) {
  return (
    <div className="bg-panel border border-line rounded-md p-5">
      <h2 className="font-display text-[15px] uppercase tracking-wide text-ink-soft mb-3.5">
        Answer
      </h2>

      {error && (
        <div className="bg-red-dim border-l-[3px] border-red px-3 py-2.5 text-[13px] rounded-r">
          <b>Something went wrong:</b> {error}
        </div>
      )}

      {loading && !error && (
        <p className="text-ink-soft italic text-sm">
          Retrieving relevant evidence and synthesizing a grounded answer…
        </p>
      )}

      {!loading && !error && !answer && (
        <p className="text-ink-soft italic text-sm">
          Ask a question above — the assistant retrieves relevant excerpts, synthesizes a
          grounded answer, and cites every claim.
        </p>
      )}

      {!loading && !error && answer && confidence && (
        <>
          <ConfidenceBadge confidence={confidence} />
          <ClaimList claims={answer.claims} onCitationClick={onCitationClick} />
          <ContradictionBox text={answer.contradictions} />
          <GapBox text={answer.gaps} />
          <FeedbackBar status={feedbackStatus} onRate={onRate} />
        </>
      )}
    </div>
  );
}

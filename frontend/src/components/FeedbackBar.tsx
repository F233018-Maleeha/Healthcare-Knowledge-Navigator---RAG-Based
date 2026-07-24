import type { FeedbackRating } from "../api/types";

interface FeedbackBarProps {
  status: "idle" | "sending" | "sent" | "error";
  onRate: (rating: FeedbackRating) => void;
}

const OPTIONS: { rating: FeedbackRating; label: string }[] = [
  { rating: "helpful", label: "Helpful" },
  { rating: "not_helpful", label: "Not helpful" },
  { rating: "incorrect", label: "Incorrect" },
];

export function FeedbackBar({ status, onRate }: FeedbackBarProps) {
  if (status === "sent") {
    return <p className="text-[12.5px] text-ink-soft mt-4">Thanks — feedback recorded.</p>;
  }

  return (
    <div className="flex items-center gap-2 mt-4 pt-3 border-t border-line">
      <span className="text-[12.5px] text-ink-soft mr-1">Rate this answer:</span>
      {OPTIONS.map((opt) => (
        <button
          key={opt.rating}
          onClick={() => onRate(opt.rating)}
          disabled={status === "sending"}
          className="text-[12.5px] font-body border border-line text-ink-soft px-2.5 py-1 rounded-full hover:border-teal hover:text-teal transition-colors disabled:opacity-50"
        >
          {opt.label}
        </button>
      ))}
      {status === "error" && (
        <span className="text-[12px] text-red ml-1">Couldn't send — try again.</span>
      )}
    </div>
  );
}

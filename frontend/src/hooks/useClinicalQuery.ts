import { useCallback, useState } from "react";
import { ApiError, postFeedback, postQuery } from "../api/client";
import type { FeedbackRating, QueryResponse } from "../api/types";

interface ClinicalQueryState {
  query: string;
  setQuery: (q: string) => void;
  submit: (overrideQuery?: string) => Promise<void>;
  loading: boolean;
  error: string | null;
  data: QueryResponse | null;
  highlightedChunkId: string | null;
  setHighlightedChunkId: (id: string | null) => void;
  submitFeedback: (rating: FeedbackRating) => Promise<void>;
  feedbackStatus: "idle" | "sending" | "sent" | "error";
}

/**
 * Owns every piece of state the query experience needs: the input
 * value, in-flight/error/result state, which evidence card is
 * currently highlighted (from clicking a citation), and the feedback
 * submission flow. Components consume this via useClinicalQuery() and
 * never talk to the API directly - see api/client.ts for that layer.
 */
export function useClinicalQuery(): ClinicalQueryState {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<QueryResponse | null>(null);
  const [highlightedChunkId, setHighlightedChunkId] = useState<string | null>(null);
  const [feedbackStatus, setFeedbackStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  const submit = useCallback(
    async (overrideQuery?: string) => {
      const q = (overrideQuery ?? query).trim();
      if (!q) return;

      setQuery(q);
      setLoading(true);
      setError(null);
      setData(null);
      setHighlightedChunkId(null);
      setFeedbackStatus("idle");

      try {
        const result = await postQuery({ query: q });
        setData(result);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Something went wrong reaching the server.");
      } finally {
        setLoading(false);
      }
    },
    [query]
  );

  const submitFeedback = useCallback(
    async (rating: FeedbackRating) => {
      if (!data) return;
      setFeedbackStatus("sending");
      try {
        await postFeedback({ request_id: data.request_id, rating });
        setFeedbackStatus("sent");
      } catch {
        setFeedbackStatus("error");
      }
    },
    [data]
  );

  return {
    query,
    setQuery,
    submit,
    loading,
    error,
    data,
    highlightedChunkId,
    setHighlightedChunkId,
    submitFeedback,
    feedbackStatus,
  };
}

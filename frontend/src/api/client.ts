import type { FeedbackRequest, QueryRequest, QueryResponse } from "./types";

/**
 * The backend base URL comes from an env var so switching environments
 * (local, staging, production) never means editing code - see .env.example.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "https://healthcare-knowledge-navigator-rag-based-production.up.railway.app";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<TResponse>(path: string, options: RequestInit): Promise<TResponse> {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!resp.ok) {
    // The backend deliberately returns a clean, readable `detail` field
    // on every error (see routes_query.py / routes_ingest.py) - surface
    // that directly instead of a generic "request failed" message.
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON - fall back to statusText, already set above
    }
    throw new ApiError(resp.status, detail);
  }

  return resp.json() as Promise<TResponse>;
}

/** POST /query - the main retrieve-and-answer call. */
export function postQuery(payload: QueryRequest): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** POST /feedback - attaches a clinician's rating to a prior request_id. */
export function postFeedback(payload: FeedbackRequest): Promise<{ status: string }> {
  return request<{ status: string }>("/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

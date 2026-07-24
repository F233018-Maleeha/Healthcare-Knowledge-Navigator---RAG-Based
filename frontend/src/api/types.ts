/**
 * These types mirror backend/app/models/schemas.py exactly.
 * If you add/change a field on the backend, update it here too -
 * TypeScript will then flag every place in the UI that needs updating.
 */

export type AuthorityTier = 1 | 2 | 3 | 4;

export type SectionType =
  | "recommendation"
  | "background"
  | "dosing"
  | "contraindication"
  | "evidence"
  | "other";

export interface Chunk {
  chunk_id: string;
  doc_id: string;
  section_type: SectionType;
  text: string;
  title: string;
  source: string;
  authority_tier: AuthorityTier;
  evidence_grade: string | null;
  publication_date: string;
  specialty: string[];
  embedding: number[] | null;
}

export interface RetrievedChunk {
  chunk: Chunk;
  dense_score: number | null;
  sparse_score: number | null;
  fused_score: number | null;
  rerank_score: number | null;
}

export type ClaimConfidence = "high" | "moderate" | "low";

export interface Claim {
  text: string;
  citation_ids: string[];
  confidence: ClaimConfidence;
}

export interface ConfidenceBreakdown {
  retrieval_agreement: number;
  source_authority: number;
  recency: number;
  self_rating: number;
}

export type ConfidenceLabel = "high" | "moderate" | "low";

export interface ConfidenceResult {
  label: ConfidenceLabel;
  score: number;
  breakdown: ConfidenceBreakdown;
}

export interface GeneratedAnswer {
  claims: Claim[];
  contradictions: string;
  gaps: string;
}

export interface QueryRequest {
  query: string;
  specialty_filter?: string[] | null;
  top_k?: number | null;
}

export interface QueryResponse {
  query: string;
  answer: GeneratedAnswer;
  confidence: ConfidenceResult;
  retrieved_chunks: RetrievedChunk[];
  request_id: string;
}

export type FeedbackRating = "helpful" | "not_helpful" | "incorrect";

export interface FeedbackRequest {
  request_id: string;
  rating: FeedbackRating;
  comment?: string | null;
}

import type { Claim as ClaimType } from "../api/types";
import { Claim } from "./Claim";

interface ClaimListProps {
  claims: ClaimType[];
  onCitationClick: (chunkId: string) => void;
}

export function ClaimList({ claims, onCitationClick }: ClaimListProps) {
  return (
    <div>
      {claims.map((claim, i) => (
        <Claim key={i} claim={claim} onCitationClick={onCitationClick} />
      ))}
    </div>
  );
}

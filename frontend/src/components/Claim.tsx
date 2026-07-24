import type { Claim as ClaimType } from "../api/types";
import { Citation } from "./Citation";

interface ClaimProps {
  claim: ClaimType;
  onCitationClick: (chunkId: string) => void;
}

export function Claim({ claim, onCitationClick }: ClaimProps) {
  return (
    <p className="text-[15.5px] leading-relaxed mb-3">
      {claim.text}{" "}
      {claim.citation_ids.map((id) => (
        <span key={id} className="mr-1 inline-block">
          <Citation chunkId={id} onClick={onCitationClick} />
        </span>
      ))}
      <span className="text-[10px] uppercase tracking-wide opacity-75 ml-1">
        · {claim.confidence}
      </span>
    </p>
  );
}

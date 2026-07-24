interface CitationProps {
  chunkId: string;
  onClick: (chunkId: string) => void;
}

export function Citation({ chunkId, onClick }: CitationProps) {
  return (
    <button
      onClick={() => onClick(chunkId)}
      className="font-mono text-[10.5px] text-teal bg-teal-dim border border-teal px-1.5 py-px rounded-full hover:bg-teal hover:text-white transition-colors whitespace-nowrap"
    >
      {chunkId}
    </button>
  );
}

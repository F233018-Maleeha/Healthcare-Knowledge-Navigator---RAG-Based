interface ExampleQueriesProps {
  examples: string[];
  onPick: (example: string) => void;
}

export function ExampleQueries({ examples, onPick }: ExampleQueriesProps) {
  return (
    <div className="flex gap-2 flex-wrap mb-6">
      {examples.map((example) => (
        <button
          key={example}
          onClick={() => onPick(example)}
          className="text-[12.5px] font-body bg-panel border border-line text-ink-soft px-2.5 py-1.5 rounded-full hover:border-teal hover:text-teal transition-colors"
        >
          {example}
        </button>
      ))}
    </div>
  );
}

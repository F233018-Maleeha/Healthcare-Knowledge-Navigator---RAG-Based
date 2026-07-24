interface QueryBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function QueryBar({ value, onChange, onSubmit, loading }: QueryBarProps) {
  return (
    <div className="flex gap-2.5 mb-2.5">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onSubmit();
        }}
        placeholder="Ask a cardiology question, e.g. “When should I start anticoagulation in atrial fibrillation?”"
        className="flex-1 px-3.5 py-3 text-[15px] font-body border-[1.5px] border-ink rounded bg-panel text-ink focus:outline-none focus:ring-2 focus:ring-teal focus:ring-offset-1"
      />
      <button
        onClick={onSubmit}
        disabled={loading}
        className="font-mono text-[13px] tracking-wide uppercase text-white bg-ink hover:bg-teal disabled:bg-gray-400 disabled:cursor-progress px-5 rounded transition-colors"
      >
        {loading ? "Asking…" : "Ask"}
      </button>
    </div>
  );
}

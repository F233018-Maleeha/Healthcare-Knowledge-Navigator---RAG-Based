interface CalloutProps {
  text: string;
}

export function ContradictionBox({ text }: CalloutProps) {
  if (!text) return null;
  return (
    <div className="bg-red-dim border-l-[3px] border-red px-3 py-2.5 text-[13px] leading-relaxed my-3.5 rounded-r">
      <b>Sources disagree:</b> {text}
    </div>
  );
}

export function GapBox({ text }: CalloutProps) {
  if (!text) return null;
  return (
    <div className="bg-paper border-l-[3px] border-ink-soft px-3 py-2.5 text-[13px] leading-relaxed my-3.5 rounded-r text-ink-soft">
      <b className="text-ink">Not fully covered by retrieved sources:</b> {text}
    </div>
  );
}

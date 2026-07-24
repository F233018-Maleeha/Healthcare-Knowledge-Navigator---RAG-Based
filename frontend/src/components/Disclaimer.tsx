interface DisclaimerProps {
  message: string;
}

export function Disclaimer({ message }: DisclaimerProps) {
  return (
    <div className="text-[12.5px] text-ink-soft bg-amber-dim border-l-[3px] border-amber px-3 py-2 my-4 leading-relaxed">
      {message}
    </div>
  );
}

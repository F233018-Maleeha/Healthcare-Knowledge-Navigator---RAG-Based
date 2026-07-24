interface HeaderProps {
  specialty?: string;
}

export function Header({ specialty = "Cardiology" }: HeaderProps) {
  return (
    <header className="flex flex-wrap items-baseline justify-between gap-3 border-b-2 border-ink pb-4 mb-1">
      <div className="flex items-baseline gap-3">
        <h1 className="font-display font-bold text-2xl tracking-tight m-0">
          Knowledge Navigator
        </h1>
        <span className="font-mono text-[11px] uppercase tracking-wide bg-teal text-white px-2.5 py-1 rounded">
          {specialty}
        </span>
      </div>
    </header>
  );
}

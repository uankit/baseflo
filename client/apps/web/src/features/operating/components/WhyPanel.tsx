import type { ReactNode } from 'react';

export function WhyPanel({
  title = 'why',
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <aside className="border border-ink/20 bg-paper-soft p-4">
      <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.22em] text-ink/45">
        {title}
      </p>
      <div className="mt-2 text-sm leading-6 text-ink/70">{children}</div>
    </aside>
  );
}

export function TagList({ tags }: { tags: string[] }) {
  if (!tags.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag) => (
        <span
          key={tag}
          className="border border-ink/25 bg-paper px-2 py-0.5 text-[11px] font-semibold text-ink/65"
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

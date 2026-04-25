interface Props {
  title: string;
  subtitle?: string;
  badge?: string;
}

export function PageHeader({ title, subtitle, badge }: Props) {
  return (
    <div className="mb-8 animate-fade-in">
      {badge && (
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-xs font-medium text-primary mb-3">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          {badge}
        </div>
      )}
      <h1 className="text-4xl font-bold tracking-tight mb-2 gradient-text">{title}</h1>
      {subtitle && <p className="text-muted-foreground max-w-3xl leading-relaxed">{subtitle}</p>}
    </div>
  );
}

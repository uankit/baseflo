export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function compactDateTime(iso: string | null | undefined): string {
  if (!iso) return 'not run yet';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return iso;
  const diffMs = Date.now() - then.getTime();
  const minutes = Math.max(0, Math.round(diffMs / 60_000));
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function labelize(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function asDisplayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value === null || value === undefined) return '';
  return JSON.stringify(value);
}

export function statusTone(status: string): 'good' | 'warning' | 'neutral' {
  if (status === 'completed' || status === 'prepared' || status === 'active' || status === 'synced') {
    return 'good';
  }
  if (status === 'failed' || status === 'error' || status === 'partial') {
    return 'warning';
  }
  return 'neutral';
}

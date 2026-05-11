import { useState, useMemo } from 'react';

interface Suggestion {
  id: string;
  label: string;
  description: string;
  icon: 'query' | 'action' | 'navigate';
}

const DEFAULT_SUGGESTIONS: Suggestion[] = [
  {
    id: '1',
    label: 'What is my total revenue?',
    description: 'Query your unified metrics',
    icon: 'query',
  },
  {
    id: '2',
    label: 'Show me at-risk customers',
    description: 'Segment analysis',
    icon: 'query',
  },
  {
    id: '3',
    label: 'Connect Shopify store',
    description: 'Add a new data source',
    icon: 'action',
  },
  {
    id: '4',
    label: 'Export customer list',
    description: 'Generate a report',
    icon: 'action',
  },
];

export function useCommandPalette() {
  const [query, setQuery] = useState('');

  const suggestions = useMemo(() => {
    if (!query.trim()) return DEFAULT_SUGGESTIONS;
    const q = query.toLowerCase();
    return DEFAULT_SUGGESTIONS.filter(
      (s) =>
        s.label.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q),
    );
  }, [query]);

  return { query, setQuery, suggestions };
}

import { useQuery, useMutation } from '@tanstack/react-query';

const API_BASE = '/api/v1/workbench';

export interface WorkbenchData {
  workbench_id: string;
  title: string;
  generated_at: string;
  metrics: MetricValue[];
  alerts: AlertItem[];
  tables: RankedTableData[];
  charts: ChartData[];
  actions: ActionItem[];
  drill_downs: DrillDown[];
}

export interface MetricValue {
  key: string;
  title: string;
  value: number | string | null;
  formatted_value: string;
  change_percent?: number;
  change_direction?: 'up' | 'down' | 'flat';
  context?: string;
}

export interface AlertItem {
  alert_id: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  entity_type: string;
  entity_id: string;
  entity_name: string;
  proposed_action?: string;
}

export interface RankedTableData {
  title: string;
  columns: TableColumn[];
  rows: TableRow[];
  total_count: number;
}

export interface TableColumn {
  key: string;
  label: string;
  type: string;
}

export interface TableRow {
  row_id: string;
  cells: Record<string, unknown>;
  actions: string[];
  severity?: string;
}

export interface ChartData {
  title: string;
  chart_type: string;
  labels: string[];
  datasets: Array<{ label: string; data: number[] }>;
}

export interface ActionItem {
  type: string;
  label: string;
}

export interface DrillDown {
  entity_type: string;
  route_template: string;
  title_template: string;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export function useWorkbenchOverview() {
  return useQuery({
    queryKey: ['workbench', 'overview'],
    queryFn: () => fetchJson<WorkbenchData>(`${API_BASE}/overview`),
  });
}

export function useWorkbenchParty(partyName: string) {
  return useQuery({
    queryKey: ['workbench', 'party', partyName],
    queryFn: () => fetchJson<WorkbenchData>(`${API_BASE}/party/${encodeURIComponent(partyName)}`),
  });
}

export function useWorkbenchCollections() {
  return useQuery({
    queryKey: ['workbench', 'collections'],
    queryFn: () => fetchJson<WorkbenchData>(`${API_BASE}/collections`),
  });
}

export function useAvailableWorkbenches() {
  return useQuery({
    queryKey: ['workbenches', 'available'],
    queryFn: () => fetchJson<{ workbenches: unknown[]; primary: string | null }>(`${API_BASE}/available`),
  });
}

export function useWorkbenchAction() {
  return useMutation({
    mutationFn: async ({ actionType, payload }: { actionType: string; payload: Record<string, unknown> }) => {
      const res = await fetch(`${API_BASE}/actions/${actionType}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
  });
}

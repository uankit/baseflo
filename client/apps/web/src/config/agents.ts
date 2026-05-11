import type { ComponentType } from 'react';
import {
  IconDatabase,
  IconShieldCheck,
  IconZap,
  IconLightbulb,
} from '@baseflo/ui/icons';

export interface AgentConfig {
  id: string;
  name: string;
  role: string;
  personality: string;
  artifactType: string;
  tone: 'accent' | 'success' | 'info' | 'warning' | 'purple' | 'emerald' | 'amber';
  icon: string; // lucide icon name
}

export const AGENTS: AgentConfig[] = [
  {
    id: 'source',
    name: 'Source',
    role: 'Data Engineer',
    personality: 'Maps raw inputs into structured streams',
    artifactType: 'source_map',
    tone: 'accent',
    icon: 'Database',
  },
  {
    id: 'reconciliation',
    name: 'Recon',
    role: 'Data Steward',
    personality: 'Resolves conflicts and unifies entities',
    artifactType: 'entity_graph',
    tone: 'purple',
    icon: 'ShieldCheck',
  },
  {
    id: 'schema',
    name: 'Schema',
    role: 'Architect',
    personality: 'Designs the unified model blueprint',
    artifactType: 'schema_ir',
    tone: 'emerald',
    icon: 'Zap',
  },
  {
    id: 'insight',
    name: 'Insight',
    role: 'Analyst',
    personality: 'Surfaces patterns and anomalies',
    artifactType: 'insight_board',
    tone: 'amber',
    icon: 'Lightbulb',
  },
];

export function getAgent(id: string): AgentConfig | undefined {
  return AGENTS.find((a) => a.id === id);
}

export function getAgentForArtifact(type: string): AgentConfig | undefined {
  return AGENTS.find((a) => a.artifactType === type);
}

export function listAgents(): AgentConfig[] {
  return [...AGENTS];
}

export const AGENT_ICON_MAP: Record<
  string,
  ComponentType<{ className?: string; size?: number }>
> = {
  Database: IconDatabase,
  ShieldCheck: IconShieldCheck,
  Zap: IconZap,
  Lightbulb: IconLightbulb,
};

export const TONE_STYLE_MAP: Record<
  AgentConfig['tone'],
  {
    text: string;
    bg: string;
    border: string;
    dot: string;
    softShadow: string;
    glowShadow: string;
  }
> = {
  accent: {
    text: 'text-accent',
    bg: 'bg-accent-soft',
    border: 'border-accent',
    dot: 'bg-accent',
    softShadow: 'shadow-[0_0_8px_hsl(var(--color-accent)/0.25)]',
    glowShadow: 'shadow-[0_0_12px_hsl(var(--color-accent)/0.4)]',
  },
  success: {
    text: 'text-success',
    bg: 'bg-success/10',
    border: 'border-success',
    dot: 'bg-success',
    softShadow: 'shadow-[0_0_8px_hsl(var(--color-success)/0.25)]',
    glowShadow: 'shadow-[0_0_12px_hsl(var(--color-success)/0.4)]',
  },
  info: {
    text: 'text-info',
    bg: 'bg-info/10',
    border: 'border-info',
    dot: 'bg-info',
    softShadow: '',
    glowShadow: '',
  },
  warning: {
    text: 'text-warning',
    bg: 'bg-warning/10',
    border: 'border-warning',
    dot: 'bg-warning',
    softShadow: '',
    glowShadow: '',
  },
  purple: {
    text: 'text-purple-600',
    bg: 'bg-purple-50',
    border: 'border-purple-200',
    dot: 'bg-purple-600',
    softShadow: 'shadow-[0_0_8px_rgba(147,51,234,0.25)]',
    glowShadow: 'shadow-[0_0_12px_rgba(147,51,234,0.4)]',
  },
  emerald: {
    text: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-200',
    dot: 'bg-emerald-600',
    softShadow: 'shadow-[0_0_8px_rgba(16,185,129,0.25)]',
    glowShadow: 'shadow-[0_0_12px_rgba(16,185,129,0.4)]',
  },
  amber: {
    text: 'text-amber-600',
    bg: 'bg-amber-50',
    border: 'border-amber-200',
    dot: 'bg-amber-600',
    softShadow: 'shadow-[0_0_8px_rgba(217,119,6,0.25)]',
    glowShadow: 'shadow-[0_0_12px_rgba(217,119,6,0.4)]',
  },
};

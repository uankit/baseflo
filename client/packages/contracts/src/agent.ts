import { z } from 'zod';

export const AgentDefSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string(),
  personality: z.string(),
  artifactType: z.string(),
  tone: z.string(),
  icon: z.string(),
});

export type AgentDef = z.infer<typeof AgentDefSchema>;

export const ListAgentsResponseSchema = z.object({
  agents: z.array(AgentDefSchema),
});

export const AgentFeedEntrySchema = z.object({
  id: z.string(),
  projectId: z.string(),
  agentId: z.string(),
  entryType: z.string(),
  content: z.string(),
  context: z.record(z.string(), z.unknown()).optional().default({}),
  createdAt: z.string(),
  acknowledgedAt: z.string().nullable(),
});

export const GetAgentFeedResponseSchema = z.object({
  entries: z.array(AgentFeedEntrySchema),
});

export const AgentTaskSchema = z.object({
  id: z.string(),
  projectId: z.string(),
  agentId: z.string(),
  kind: z.string(),
  status: z.string(),
  priority: z.number(),
  payload: z.record(z.string(), z.unknown()).optional().default({}),
  result: z.record(z.string(), z.unknown()).nullable().optional(),
  error: z.record(z.string(), z.unknown()).nullable().optional(),
  createdAt: z.string(),
  startedAt: z.string().nullable(),
  completedAt: z.string().nullable(),
});

export const GetAgentTasksResponseSchema = z.object({
  tasks: z.array(AgentTaskSchema),
});



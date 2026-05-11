import { z } from 'zod';
import { TimestampSchema, UUIDSchema } from './common.js';

/**
 * SSE saga event taxonomy. Matches the server emission set documented in
 * docs/04-database-schema.md §4.13 and consumed by docs/40-features/WEB-APP.md §5.6.
 *
 * Adding a kind on the server is a breaking change here: bump the contracts
 * package major version, regenerate, force every consumer to handle the new case.
 */
export const SagaEventKindSchema = z.enum([
  'heartbeat',
  'conversation.message',
  'clarification.required',
  'clarification.answered',
  'agent.start',
  'agent.complete',
  'validation.passed',
  'validation.warning',
  'validation.failed',
  'artifact.ready',
  'workspace.ready',
  'error.recoverable',
  'error.terminal',
  'refinement.start',
  'refinement.complete',
]);
export type SagaEventKind = z.infer<typeof SagaEventKindSchema>;

export const SagaEventSchema = z.object({
  conversationId: UUIDSchema,
  sequence: z.number().int().nonnegative(),
  kind: SagaEventKindSchema,
  createdAt: TimestampSchema,
  payload: z.record(z.string(), z.unknown()),
});
export type SagaEvent = z.infer<typeof SagaEventSchema>;

export const ClarificationQuestionSchema = z.object({
  id: z.string(),
  prompt: z.string(),
  choices: z.array(z.string()).optional(),
  allowFreeText: z.boolean().default(true),
});
export type ClarificationQuestion = z.infer<typeof ClarificationQuestionSchema>;

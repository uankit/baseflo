import { z } from 'zod';

export const ArtifactHeaderSchema = z.looseObject({
  artifactId: z.uuid(),
  projectId: z.uuid(),
  artifactType: z.string(),
  version: z.number(),
  producedBy: z.string(),
  createdAt: z.iso.datetime(),
});

export const ArtifactProvenanceSchema = z.looseObject({
  agentName: z.string(),
  modelName: z.string().nullable(),
  tokensPrompt: z.number(),
  tokensCompletion: z.number(),
  latencyMs: z.number(),
  startedAt: z.iso.datetime(),
  finishedAt: z.iso.datetime(),
});

export const ArtifactSchema = z.looseObject({
  artifactId: z.uuid(),
  projectId: z.uuid(),
  artifactType: z.string(),
  version: z.number(),
  producedBy: z.string(),
  createdAt: z.iso.datetime(),
  payload: z.any(),
  provenance: ArtifactProvenanceSchema,
});

export const ListArtifactsResponseSchema = z.looseObject({
  artifacts: z.array(ArtifactHeaderSchema),
});

export type ArtifactHeader = z.infer<typeof ArtifactHeaderSchema>;
export type ArtifactProvenance = z.infer<typeof ArtifactProvenanceSchema>;
export type Artifact = z.infer<typeof ArtifactSchema>;
export type ListArtifactsResponse = z.infer<typeof ListArtifactsResponseSchema>;

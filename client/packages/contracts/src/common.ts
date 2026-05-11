import { z } from 'zod';

/**
 * Shared atomic schemas used across the contracts package. Zod 4's preferred
 * idiom is top-level format helpers (`z.uuid()`, `z.email()`, `z.iso.datetime()`)
 * rather than string-method chains. Centralizing them here keeps consumer
 * schemas terse and makes review-time scanning trivial.
 */

export const UUIDSchema = z.uuid();
export type UUID = z.infer<typeof UUIDSchema>;

export const TimestampSchema = z.iso.datetime({ offset: true });
export type Timestamp = z.infer<typeof TimestampSchema>;

export const EmailSchema = z.email();
export type Email = z.infer<typeof EmailSchema>;

export const URLSchema = z.url();
export type URLString = z.infer<typeof URLSchema>;

export const SlugSchema = z
  .string()
  .min(1)
  .max(64)
  .regex(/^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$/, 'Slug must be url-safe lowercase.');
export type Slug = z.infer<typeof SlugSchema>;

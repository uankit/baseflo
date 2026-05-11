import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * The standard Baseflo class-name composer. Combines clsx (conditional logic)
 * with tailwind-merge (deduping conflicting utilities). Used by every primitive.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

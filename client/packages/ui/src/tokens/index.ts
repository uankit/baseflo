/**
 * TS-side mirror of the design tokens defined in tokens.css. Use these when
 * you need a token value at runtime (e.g. chart palette computation). Component
 * code should consume tokens via Tailwind classes, not these constants.
 */

export const SEMANTIC_COLORS = [
  'bg',
  'surface',
  'surface-2',
  'border',
  'border-focus',
  'fg',
  'fg-muted',
  'fg-subtle',
  'fg-on-accent',
  'accent',
  'accent-hover',
  'accent-soft',
  'success',
  'warning',
  'danger',
  'info',
  'private',
] as const;
export type SemanticColor = (typeof SEMANTIC_COLORS)[number];

export const SPACE_SCALE = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16] as const;
export type SpaceStep = (typeof SPACE_SCALE)[number];

export const RADIUS = ['sm', 'md', 'lg', 'xl', 'pill'] as const;
export type Radius = (typeof RADIUS)[number];

export const MOTION = ['fast', 'normal', 'slow'] as const;
export type Motion = (typeof MOTION)[number];

export const Z_INDEX = ['base', 'sticky', 'overlay', 'modal', 'toast', 'tooltip'] as const;
export type ZIndex = (typeof Z_INDEX)[number];

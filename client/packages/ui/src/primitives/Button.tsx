import type { ButtonHTMLAttributes, Ref } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../lib/utils.js';

/**
 * Baseflo Button primitive. Wraps Radix Slot for `asChild` composition.
 * All visual properties driven by tokens — no hex, no arbitrary spacing.
 *
 * See docs/06-design.md §4.3 (component tier 1) and §4.7 voice rules.
 *
 * React 19: `ref` is a regular prop; no `forwardRef` wrapper required.
 */
export const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2',
    'font-sans font-medium',
    'rounded-md',
    'transition-colors duration-fast ease-baseflo',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
    'disabled:pointer-events-none disabled:opacity-50',
  ].join(' '),
  {
    variants: {
      variant: {
        primary: 'bg-accent text-fg-on-accent hover:bg-accent-hover',
        secondary: 'bg-surface text-fg border border-border hover:bg-surface-2',
        ghost: 'text-fg hover:bg-surface-2',
        danger: 'bg-danger text-fg-on-accent hover:bg-danger/90',
        link: 'text-accent underline-offset-4 hover:underline',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-sm',
        lg: 'h-12 px-6 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render as the immediate child element (Radix Slot) for composition. */
  asChild?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({
  ref,
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : 'button';
  return (
    <Comp
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}

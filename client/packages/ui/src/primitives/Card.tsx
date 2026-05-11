import type { HTMLAttributes, Ref } from 'react';
import { cn } from '../lib/utils.js';

interface DivProps extends HTMLAttributes<HTMLDivElement> {
  ref?: Ref<HTMLDivElement>;
}

export function Card({ ref, className, ...props }: DivProps) {
  return (
    <div
      ref={ref}
      className={cn('rounded-lg border border-border bg-surface shadow-sm', className)}
      {...props}
    />
  );
}

export function CardHeader({ ref, className, ...props }: DivProps) {
  return <div ref={ref} className={cn('flex flex-col gap-1 p-6', className)} {...props} />;
}

interface HeadingProps extends HTMLAttributes<HTMLHeadingElement> {
  ref?: Ref<HTMLHeadingElement>;
}

export function CardTitle({ ref, className, ...props }: HeadingProps) {
  return (
    <h3
      ref={ref}
      className={cn('text-lg font-semibold leading-tight text-fg', className)}
      {...props}
    />
  );
}

interface ParagraphProps extends HTMLAttributes<HTMLParagraphElement> {
  ref?: Ref<HTMLParagraphElement>;
}

export function CardDescription({ ref, className, ...props }: ParagraphProps) {
  return <p ref={ref} className={cn('text-sm text-fg-muted', className)} {...props} />;
}

export function CardContent({ ref, className, ...props }: DivProps) {
  return <div ref={ref} className={cn('p-6 pt-0', className)} {...props} />;
}

export function CardFooter({ ref, className, ...props }: DivProps) {
  return (
    <div ref={ref} className={cn('flex items-center gap-2 p-6 pt-0', className)} {...props} />
  );
}

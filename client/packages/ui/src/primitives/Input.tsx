import type { InputHTMLAttributes, Ref, TextareaHTMLAttributes } from 'react';
import { cn } from '../lib/utils.js';

const FIELD_BASE = [
  'flex w-full rounded-md border border-border bg-surface text-sm text-fg',
  'placeholder:text-fg-subtle',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-focus focus-visible:ring-offset-2 focus-visible:ring-offset-bg',
  'disabled:cursor-not-allowed disabled:opacity-50',
  'aria-[invalid=true]:border-danger aria-[invalid=true]:focus-visible:ring-danger',
].join(' ');

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  ref?: Ref<HTMLInputElement>;
}

export function Input({ ref, className, type = 'text', ...props }: InputProps) {
  return (
    <input
      ref={ref}
      type={type}
      className={cn(FIELD_BASE, 'h-10 px-3', className)}
      {...props}
    />
  );
}

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  ref?: Ref<HTMLTextAreaElement>;
}

export function Textarea({ ref, className, ...props }: TextareaProps) {
  return (
    <textarea
      ref={ref}
      className={cn(FIELD_BASE, 'min-h-[80px] px-3 py-2', className)}
      {...props}
    />
  );
}

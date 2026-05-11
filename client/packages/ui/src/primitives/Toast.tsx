import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ComponentProps,
  type ReactNode,
} from 'react';
import * as ToastPrimitive from '@radix-ui/react-toast';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../lib/utils.js';

export const ToastProviderRadix = ToastPrimitive.Provider;

export function ToastViewportRadix({
  className,
  ...props
}: ComponentProps<typeof ToastPrimitive.Viewport>) {
  return (
    <ToastPrimitive.Viewport
      className={cn(
        'fixed top-4 right-4 z-toast flex max-h-screen w-full max-w-[420px] flex-col gap-2 outline-none',
        className,
      )}
      {...props}
    />
  );
}

const toastVariants = cva(
  [
    'group pointer-events-auto relative flex w-full items-start gap-3 overflow-hidden rounded-md border p-4 pr-8 shadow-md',
    'data-[state=open]:animate-in data-[state=closed]:animate-out',
  ].join(' '),
  {
    variants: {
      variant: {
        info: 'border-border bg-surface text-fg',
        success: 'border-success/40 bg-success/10 text-fg',
        warning: 'border-warning/40 bg-warning/10 text-fg',
        danger: 'border-danger/40 bg-danger/10 text-fg',
      },
    },
    defaultVariants: { variant: 'info' },
  },
);

export interface ToastItem extends VariantProps<typeof toastVariants> {
  id: string;
  title: string;
  description?: string;
  durationMs?: number;
}

interface ToastContextValue {
  push: (toast: Omit<ToastItem, 'id'>) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const push = useCallback((toast: Omit<ToastItem, 'id'>) => {
    setToasts((prev) => [...prev, { ...toast, id: crypto.randomUUID() }]);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        {toasts.map((toast) => (
          <ToastPrimitive.Root
            key={toast.id}
            duration={toast.durationMs ?? 5000}
            className={cn(toastVariants({ variant: toast.variant }))}
            onOpenChange={(open) => {
              if (!open) setToasts((prev) => prev.filter((t) => t.id !== toast.id));
            }}
          >
            <div className="flex flex-col gap-1">
              <ToastPrimitive.Title className="text-sm font-medium">
                {toast.title}
              </ToastPrimitive.Title>
              {toast.description && (
                <ToastPrimitive.Description className="text-sm text-fg-muted">
                  {toast.description}
                </ToastPrimitive.Description>
              )}
            </div>
            <ToastPrimitive.Close
              className="absolute right-2 top-2 rounded p-1 text-fg-muted hover:text-fg focus:outline-none focus:ring-2 focus:ring-border-focus"
              aria-label="Dismiss"
            >
              ✕
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastViewportRadix />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast() called outside <ToastProvider>.');
  return ctx;
}

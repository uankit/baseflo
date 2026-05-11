import type {
  FieldError,
  FieldErrors,
  FieldValues,
  Resolver,
} from 'react-hook-form';

type ZodIssueLike = {
  path: PropertyKey[];
  code: string;
  message: string;
};

type SafeParseResult<TValues> =
  | { success: true; data: TValues }
  | { success: false; error: { issues: ZodIssueLike[] } };

type ZodLikeSchema<TValues> = {
  safeParseAsync: (values: unknown) => Promise<SafeParseResult<TValues>>;
};

export function zodResolver<TValues extends FieldValues>(
  schema: ZodLikeSchema<TValues>,
): Resolver<TValues> {
  return async (values) => {
    const parsed = await schema.safeParseAsync(values);
    if (parsed.success) {
      return { values: parsed.data, errors: {} };
    }

    return {
      values: {} as TValues,
      errors: issuesToFieldErrors<TValues>(parsed.error.issues),
    };
  };
}

function issuesToFieldErrors<TValues extends FieldValues>(
  issues: ZodIssueLike[],
): FieldErrors<TValues> {
  const errors: FieldErrors<TValues> = {};
  for (const issue of issues) {
    const path = issue.path.length > 0 ? issue.path.map(String) : ['root'];
    assignError(errors as Record<string, unknown>, path, {
      type: issue.code,
      message: issue.message,
    });
  }
  return errors;
}

function assignError(
  target: Record<string, unknown>,
  path: string[],
  error: FieldError,
): void {
  const [head, ...tail] = path;
  if (!head) return;

  if (tail.length === 0) {
    if (target[head] === undefined) {
      target[head] = error;
    }
    return;
  }

  const next = target[head];
  if (typeof next !== 'object' || next === null || 'message' in next) {
    target[head] = {};
  }
  assignError(target[head] as Record<string, unknown>, tail, error);
}

import { WebErrorCode, type ErrorEntry } from './error-codes.js';

/**
 * Frontend error copy registry. Source of truth for what every error code
 * shows the user. Adding a code: register it here AND in WebErrorCode.
 *
 * Voice rules per docs/40-features/WEB-APP.md §7.4:
 *  - Direct verbs.
 *  - Name the action and the recovery.
 *  - No raw exceptions, stack traces, or backend internals.
 */
const REGISTRY: Record<string, ErrorEntry> = {
  [WebErrorCode.Offline]: {
    code: WebErrorCode.Offline,
    title: "You're offline",
    message: "We'll resume when your connection is back.",
    severity: 'warning',
    rendering: 'banner',
    retriable: false,
  },
  [WebErrorCode.Server5xx]: {
    code: WebErrorCode.Server5xx,
    title: 'Something went wrong on our end',
    message: 'Try again. If it keeps happening, let us know.',
    severity: 'error',
    rendering: 'inline',
    actionLabel: 'Retry',
    retriable: true,
  },
  [WebErrorCode.Server4xxUnhandled]: {
    code: WebErrorCode.Server4xxUnhandled,
    title: "We couldn't process that request",
    message: 'Check the values and try again.',
    severity: 'error',
    rendering: 'inline',
    retriable: false,
  },
  [WebErrorCode.SseDisconnected]: {
    code: WebErrorCode.SseDisconnected,
    title: 'Reconnecting…',
    message: 'Waiting for live updates to come back.',
    severity: 'info',
    rendering: 'inline',
    retriable: false,
  },
  [WebErrorCode.SseReconnectExhausted]: {
    code: WebErrorCode.SseReconnectExhausted,
    title: 'Lost connection to live updates',
    message: 'Refresh the page to resume.',
    severity: 'error',
    rendering: 'banner',
    actionLabel: 'Refresh',
    retriable: false,
  },
  [WebErrorCode.InvalidUrlParams]: {
    code: WebErrorCode.InvalidUrlParams,
    title: "That link doesn't look right",
    message: "We've returned you to a safe page.",
    severity: 'warning',
    rendering: 'toast',
    retriable: false,
  },
  [WebErrorCode.BrowserUnsupported]: {
    code: WebErrorCode.BrowserUnsupported,
    title: 'Update your browser',
    message: 'Baseflo needs a modern browser. Use the latest Chrome, Safari, Firefox, or Edge.',
    severity: 'fatal',
    rendering: 'page',
    retriable: false,
  },
  [WebErrorCode.MobileUnsupported]: {
    code: WebErrorCode.MobileUnsupported,
    title: 'Optimized for desktop',
    message:
      'Workspace inspection needs a wider screen. Email yourself a link to open on a desktop.',
    severity: 'info',
    rendering: 'page',
    actionLabel: 'Email me a desktop link',
    retriable: false,
  },
  [WebErrorCode.RevealPiiDenied]: {
    code: WebErrorCode.RevealPiiDenied,
    title: "You can't reveal this field",
    message: 'Ask an admin to grant access.',
    severity: 'warning',
    rendering: 'inline',
    actionLabel: 'Ask your admin',
    retriable: false,
  },
  [WebErrorCode.StaleQueryFailure]: {
    code: WebErrorCode.StaleQueryFailure,
    title: 'Data is stuck',
    message: "We're retrying in the background.",
    severity: 'info',
    rendering: 'banner',
    retriable: true,
  },
  [WebErrorCode.FormValidationFailed]: {
    code: WebErrorCode.FormValidationFailed,
    title: 'Some fields need attention',
    message: 'Fix the highlighted fields and try again.',
    severity: 'warning',
    rendering: 'inline',
    retriable: false,
  },
  [WebErrorCode.OptimisticUpdateRolledBack]: {
    code: WebErrorCode.OptimisticUpdateRolledBack,
    title: "We couldn't save that",
    message: 'Your change was rolled back. Try again.',
    severity: 'error',
    rendering: 'toast',
    actionLabel: 'Retry',
    retriable: true,
  },
  [WebErrorCode.LoginRedirectLoop]: {
    code: WebErrorCode.LoginRedirectLoop,
    title: 'Sign-in loop detected',
    message: "Cleared your session. Sign in again.",
    severity: 'error',
    rendering: 'page',
    actionLabel: 'Sign in',
    retriable: false,
  },
  [WebErrorCode.OauthStateMismatch]: {
    code: WebErrorCode.OauthStateMismatch,
    title: "Sign-in didn't complete safely",
    message: 'Start over from the sign-in page.',
    severity: 'error',
    rendering: 'page',
    actionLabel: 'Start over',
    retriable: false,
  },
  [WebErrorCode.SagaNotFound]: {
    code: WebErrorCode.SagaNotFound,
    title: 'This build is no longer available',
    message: 'Open the project to see the latest workspace.',
    severity: 'warning',
    rendering: 'page',
    retriable: false,
  },
  [WebErrorCode.RefinementDiscarded]: {
    code: WebErrorCode.RefinementDiscarded,
    title: 'Refinement discarded',
    message: 'No new version was created.',
    severity: 'info',
    rendering: 'toast',
    retriable: false,
  },
  [WebErrorCode.AdminUiSpecMalformed]: {
    code: WebErrorCode.AdminUiSpecMalformed,
    title: "Workspace didn't load cleanly",
    message: 'Refresh. If this persists, contact support.',
    severity: 'error',
    rendering: 'inline',
    actionLabel: 'Refresh',
    retriable: true,
  },
  [WebErrorCode.ExportTimedOut]: {
    code: WebErrorCode.ExportTimedOut,
    title: 'Export taking longer than usual',
    message: "We'll email you when it's ready.",
    severity: 'info',
    rendering: 'inline',
    actionLabel: 'Email me when ready',
    retriable: false,
  },
  [WebErrorCode.ShareLinkRevoked]: {
    code: WebErrorCode.ShareLinkRevoked,
    title: 'This share link was revoked',
    message: 'Ask the owner for a new link.',
    severity: 'warning',
    rendering: 'page',
    retriable: false,
  },
  [WebErrorCode.ShareLinkExpired]: {
    code: WebErrorCode.ShareLinkExpired,
    title: 'This share link has expired',
    message: 'Ask the owner for a new link.',
    severity: 'warning',
    rendering: 'page',
    retriable: false,
  },
  [WebErrorCode.SagaTerminalFailure]: {
    code: WebErrorCode.SagaTerminalFailure,
    title: 'The build hit a hard error',
    message: "Start over with the same prompt or adjust and retry.",
    severity: 'error',
    rendering: 'page',
    actionLabel: 'Start over',
    retriable: false,
  },
  [WebErrorCode.MultiTabConflict]: {
    code: WebErrorCode.MultiTabConflict,
    title: 'Another tab edited this',
    message: 'Reload to see the latest, or discard your changes.',
    severity: 'warning',
    rendering: 'modal',
    actionLabel: 'Reload',
    retriable: false,
  },
  [WebErrorCode.PlanLimitReached]: {
    code: WebErrorCode.PlanLimitReached,
    title: "You've hit your plan limit",
    message: 'Upgrade to keep going.',
    severity: 'warning',
    rendering: 'modal',
    actionLabel: 'Upgrade',
    retriable: false,
  },
  [WebErrorCode.StorageQuotaExceeded]: {
    code: WebErrorCode.StorageQuotaExceeded,
    title: 'Browser storage is full',
    message: "Preferences may not save until you free up space.",
    severity: 'info',
    rendering: 'toast',
    retriable: false,
  },
  [WebErrorCode.ViewTransitionUnavailable]: {
    code: WebErrorCode.ViewTransitionUnavailable,
    title: 'Animation skipped',
    message: 'Your browser does not support this transition.',
    severity: 'info',
    rendering: 'toast',
    retriable: false,
  },
  [WebErrorCode.Unknown]: {
    code: WebErrorCode.Unknown,
    title: 'Something went wrong',
    message: 'Refresh the page. If it keeps happening, contact support.',
    severity: 'error',
    rendering: 'inline',
    actionLabel: 'Contact support',
    retriable: false,
  },
};

export function getErrorEntry(code: string): ErrorEntry {
  return REGISTRY[code] ?? REGISTRY[WebErrorCode.Unknown]!;
}

export function isRegistered(code: string): boolean {
  return Object.prototype.hasOwnProperty.call(REGISTRY, code);
}

export function listRegisteredCodes(): string[] {
  return Object.keys(REGISTRY);
}

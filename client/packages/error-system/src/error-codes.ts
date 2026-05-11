/**
 * Frontend-only error codes. Matches docs/40-features/WEB-APP.md §15.2.
 * Backend BF-AREA-NNN codes are PROXIED, never re-coded — see
 * error-normalizer.ts.
 */
export const WebErrorCode = {
  Offline: 'BF-WEB-001',
  Server5xx: 'BF-WEB-002',
  Server4xxUnhandled: 'BF-WEB-003',
  SseDisconnected: 'BF-WEB-004',
  SseReconnectExhausted: 'BF-WEB-005',
  InvalidUrlParams: 'BF-WEB-006',
  BrowserUnsupported: 'BF-WEB-007',
  MobileUnsupported: 'BF-WEB-008',
  RevealPiiDenied: 'BF-WEB-009',
  StaleQueryFailure: 'BF-WEB-010',
  FormValidationFailed: 'BF-WEB-011',
  OptimisticUpdateRolledBack: 'BF-WEB-012',
  LoginRedirectLoop: 'BF-WEB-013',
  OauthStateMismatch: 'BF-WEB-014',
  SagaNotFound: 'BF-WEB-015',
  RefinementDiscarded: 'BF-WEB-016',
  AdminUiSpecMalformed: 'BF-WEB-017',
  ExportTimedOut: 'BF-WEB-018',
  ShareLinkRevoked: 'BF-WEB-019',
  ShareLinkExpired: 'BF-WEB-020',
  SagaTerminalFailure: 'BF-WEB-021',
  MultiTabConflict: 'BF-WEB-022',
  PlanLimitReached: 'BF-WEB-023',
  StorageQuotaExceeded: 'BF-WEB-024',
  ViewTransitionUnavailable: 'BF-WEB-025',
  Unknown: 'BF-WEB-UNKNOWN-001',
} as const;
export type WebErrorCodeValue = (typeof WebErrorCode)[keyof typeof WebErrorCode];

export type ErrorSeverity = 'fatal' | 'error' | 'warning' | 'info';
export type ErrorRendering = 'inline' | 'toast' | 'banner' | 'modal' | 'page';

export interface ErrorEntry {
  code: string;
  title: string;
  message: string;
  severity: ErrorSeverity;
  rendering: ErrorRendering;
  /** Action label, if a recovery action is available. */
  actionLabel?: string;
  /** Whether the action triggers an automatic retry of the originating call. */
  retriable?: boolean;
}

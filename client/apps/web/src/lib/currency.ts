import type { Connector } from '@baseflo/contracts';

export type CurrencyCode = 'USD' | 'EUR' | 'GBP' | 'INR' | 'JPY' | 'CAD' | 'AUD' | 'SGD';

const DEFAULT_CURRENCY: CurrencyCode = 'USD';

const LOCALE_CURRENCY_MAP: Record<string, CurrencyCode> = {
  'en-US': 'USD',
  'en-CA': 'CAD',
  'en-GB': 'GBP',
  'en-IN': 'INR',
  'en-AU': 'AUD',
  'en-SG': 'SGD',
  'ja-JP': 'JPY',
  'de-DE': 'EUR',
  'de-AT': 'EUR',
  'de-CH': 'EUR',
  'fr-FR': 'EUR',
  'fr-BE': 'EUR',
  'es-ES': 'EUR',
  'it-IT': 'EUR',
  'nl-NL': 'EUR',
  'pt-PT': 'EUR',
};

export function detectCurrency(
  locale?: string,
  connectors?: Connector[],
): CurrencyCode {
  // 1. Try to detect from Stripe connector account currency
  if (connectors && connectors.length > 0) {
    const hasStripe = connectors.some((c) => c.kind === 'stripe');
    if (hasStripe) {
      const userLocale =
        locale ??
        (typeof navigator !== 'undefined' ? navigator.language : undefined);
      if (userLocale) {
        const matched = Object.keys(LOCALE_CURRENCY_MAP).find((l) =>
          userLocale.startsWith(l),
        );
        if (matched) return LOCALE_CURRENCY_MAP[matched]!;
      }
      return 'USD';
    }
  }

  // 2. Fall back to user locale
  const userLocale =
    locale ??
    (typeof navigator !== 'undefined' ? navigator.language : undefined);
  if (userLocale) {
    const matched = Object.keys(LOCALE_CURRENCY_MAP).find((l) =>
      userLocale.startsWith(l),
    );
    if (matched) return LOCALE_CURRENCY_MAP[matched]!;
  }

  // 3. Default to USD
  return DEFAULT_CURRENCY;
}

export function formatCurrency(
  value: number,
  currency: CurrencyCode,
  compact = false,
): string {
  const localeMap: Record<CurrencyCode, string> = {
    USD: 'en-US',
    EUR: 'de-DE',
    GBP: 'en-GB',
    INR: 'en-IN',
    JPY: 'ja-JP',
    CAD: 'en-CA',
    AUD: 'en-AU',
    SGD: 'en-SG',
  };

  const locale = localeMap[currency] ?? 'en-US';

  if (compact) {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      notation: 'compact',
      maximumFractionDigits: 0,
    }).format(value);
  }

  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

const CURRENCY_SYMBOLS = /[$€£¥₹]/;

export function parseNumericValue(value: string): number | null {
  const cleaned = value.replace(CURRENCY_SYMBOLS, '').replace(/,/g, '').replace(/\s/g, '').trim();
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : null;
}

export function isCurrencyValue(value: string, unit?: string | null): boolean {
  if (unit && ['$', '€', '£', '¥', '₹', 'USD', 'EUR', 'GBP', 'INR', 'JPY', 'CAD', 'AUD', 'SGD'].includes(unit)) return true;
  return CURRENCY_SYMBOLS.test(value);
}

export function formatKpiValue(value: string, unit: string | null, currency: CurrencyCode): string {
  const num = parseNumericValue(value);
  if (num === null) return value;
  if (isCurrencyValue(value, unit)) {
    return formatCurrency(num, currency, true);
  }
  return new Intl.NumberFormat('en-US').format(num);
}

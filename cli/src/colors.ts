/** Tiny ANSI colour helpers — no dependency. */

const isTty = process.stdout.isTTY;

function wrap(code: string): (s: string) => string {
  if (!isTty) return (s) => s;
  return (s) => `\x1b[${code}m${s}\x1b[0m`;
}

export const colors = {
  bold: wrap("1"),
  dim: wrap("2"),
  red: wrap("31"),
  green: wrap("32"),
  yellow: wrap("33"),
  blue: wrap("34"),
  magenta: wrap("35"),
  cyan: wrap("36"),
  gray: wrap("90"),
};

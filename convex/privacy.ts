const EMAIL = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const PHONE = /(?<!\w)(?:\+?\d[\d(). -]{7,}\d)(?!\w)/g;
const STREET_ADDRESS = /\b\d{1,6}\s+(?:[A-Z0-9.'-]+\s+){0,5}(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|way)\b/gi;
const LONG_DIGITS = /\b\d{6,}\b/g;

export function scrubPii(value: string): string {
  return value
    .replace(EMAIL, "[email redacted]")
    .replace(PHONE, "[phone redacted]")
    .replace(STREET_ADDRESS, "[address redacted]")
    .replace(LONG_DIGITS, "[digits redacted]");
}

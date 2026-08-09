import type { Scan } from "./types";

const now = Date.now();

export const seededScans: Scan[] = [
  {
    _id: "seed-danger-1",
    userId: "margaret-demo",
    surface: "email",
    verdict: "DANGER",
    domain: "paypa1-secure.ru",
    screenshotUrl: "https://placehold.co/1200x675/0b2730/dcf8f2.webp?text=Suspicious+PayPal+security+alert",
    findingCodes: ["LINK_TEXT_MISMATCH", "YOUNG_DOMAIN"],
    findingsRedacted: [
      { code: "LINK_TEXT_MISMATCH", severity: 4, title: "Link destination does not match its label", evidence: "Displayed PayPal link opens a different domain" },
      { code: "YOUNG_DOMAIN", severity: 3, title: "This domain was registered recently", evidence: "Domain age is under 30 days" },
    ],
    acknowledged: false,
    createdAt: now - 40_000,
  },
  {
    _id: "seed-caution-1",
    userId: "margaret-demo",
    surface: "download",
    verdict: "CAUTION",
    domain: "invoice-docs.example",
    findingCodes: ["UNEXPECTED_DOWNLOAD"],
    findingsRedacted: [
      { code: "UNEXPECTED_DOWNLOAD", severity: 2, title: "Unexpected executable download", evidence: "The download type does not match the button label" },
    ],
    acknowledged: true,
    createdAt: now - 3 * 24 * 60 * 60 * 1000,
  },
  {
    _id: "seed-safe-1",
    userId: "margaret-demo",
    surface: "web",
    verdict: "SAFE",
    domain: "amazon.com",
    findingCodes: [],
    findingsRedacted: [],
    acknowledged: true,
    createdAt: now - 8 * 24 * 60 * 60 * 1000,
  },
  {
    _id: "seed-danger-2",
    userId: "margaret-demo",
    surface: "crypto",
    verdict: "DANGER",
    domain: "wallet-recovery.example",
    findingCodes: ["SEED_PHRASE_REQUEST"],
    findingsRedacted: [
      { code: "SEED_PHRASE_REQUEST", severity: 4, title: "A site asked for a wallet recovery phrase", evidence: "Legitimate support never asks for a recovery phrase" },
    ],
    acknowledged: true,
    createdAt: now - 16 * 24 * 60 * 60 * 1000,
  },
];

export const seededCircle = [{
  _id: "seed-circle-logan",
  protectedUserId: "margaret-demo",
  protectedName: "Logan",
  guardianUserId: "dan-demo",
  alertOn: ["DANGER", "CAUTION"],
  consentGivenAt: now - 42 * 24 * 60 * 60 * 1000,
}];

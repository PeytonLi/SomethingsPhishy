export type Verdict = "SAFE" | "CAUTION" | "DANGER";

export type RedactedFinding = {
  code: string;
  severity: number;
  title: string;
  evidence: string;
};

export type Scan = {
  _id: string;
  userId: string;
  surface: string;
  verdict: Verdict;
  domain?: string;
  screenshotUrl?: string;
  findingCodes: string[];
  findingsRedacted: RedactedFinding[];
  acknowledged: boolean;
  createdAt: number;
};

export type GuardianLink = {
  _id: string;
  protectedUserId: string;
  protectedName?: string;
  guardianUserId: string;
  alertOn: string[];
  consentGivenAt: number;
};

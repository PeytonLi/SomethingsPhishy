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
  findingCodes: string[];
  findingsRedacted: RedactedFinding[];
  acknowledged: boolean;
  createdAt: number;
};

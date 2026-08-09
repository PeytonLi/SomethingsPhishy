import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "convex/react";
import { api } from "./convex-api";
import { seededScans } from "./seed";
import type { Scan, Verdict } from "./types";

type AppProps = { connected: boolean };
type ViewMode = "guardian" | "protected";

const verdictMeta: Record<Verdict, { glyph: string; label: string; message: string }> = {
  DANGER: { glyph: "⛔", label: "Danger", message: "Needs attention now" },
  CAUTION: { glyph: "⚠", label: "Caution", message: "Worth a closer look" },
  SAFE: { glyph: "✓", label: "Safe", message: "No danger signals found" },
};

function relativeTime(timestamp: number, now: number) {
  const seconds = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (seconds < 60) return `${seconds} second${seconds === 1 ? "" : "s"} ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function normalizeScans(value: unknown): Scan[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Scan => {
    if (!item || typeof item !== "object") return false;
    const scan = item as Partial<Scan>;
    return typeof scan._id === "string" && typeof scan.createdAt === "number" &&
      (scan.verdict === "SAFE" || scan.verdict === "CAUTION" || scan.verdict === "DANGER");
  });
}

function LiveDashboard({ mode, guardianUserId }: { mode: ViewMode; guardianUserId: string }) {
  const queryResult = useQuery(api.scans.guardianFeed, { guardianUserId });
  const acknowledge = useMutation(api.scans.acknowledge);
  const scans = useMemo(() => normalizeScans(queryResult), [queryResult]);

  return (
    <DashboardContent
      mode={mode}
      scans={scans}
      loading={queryResult === undefined}
      sourceLabel="Live via Convex"
      onAcknowledge={mode === "guardian" ? async (scanId) => { await acknowledge({ scanId }); } : undefined}
    />
  );
}

function SeededDashboard({ mode }: { mode: ViewMode }) {
  const [scans, setScans] = useState(seededScans);
  const acknowledge = async (scanId: string) => {
    await new Promise((resolve) => window.setTimeout(resolve, 240));
    setScans((current) => current.map((scan) => scan._id === scanId ? { ...scan, acknowledged: true } : scan));
  };

  return (
    <DashboardContent
      mode={mode}
      scans={scans}
      loading={false}
      sourceLabel="Demo data"
      onAcknowledge={mode === "guardian" ? acknowledge : undefined}
    />
  );
}

function DashboardContent({ mode, scans, loading, sourceLabel, onAcknowledge }: {
  mode: ViewMode;
  scans: Scan[];
  loading: boolean;
  sourceLabel: string;
  onAcknowledge?: (scanId: string) => Promise<void>;
}) {
  const [now, setNow] = useState(() => Date.now());
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [errorId, setErrorId] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  const sortedScans = useMemo(() => [...scans].sort((a, b) => b.createdAt - a.createdAt), [scans]);
  const activeAlerts = sortedScans.filter((scan) => scan.verdict === "DANGER" && !scan.acknowledged);
  const monthStart = new Date(now).setDate(1);
  const targetedThisMonth = sortedScans.filter((scan) => scan.verdict === "DANGER" && scan.createdAt >= monthStart).length;
  const headline = activeAlerts.length > 0
    ? `${activeAlerts.length} alert${activeAlerts.length === 1 ? "" : "s"} need attention`
    : "Your circle is clear";

  const handleAcknowledge = async (scanId: string) => {
    if (!onAcknowledge) return;
    setPendingId(scanId);
    setErrorId(null);
    try {
      await onAcknowledge(scanId);
    } catch {
      setErrorId(scanId);
    } finally {
      setPendingId(null);
    }
  };

  return (
    <>
      <section className={`status-hero ${activeAlerts.length > 0 ? "status-hero--danger" : "status-hero--clear"}`} aria-live="polite">
        <div className="status-mark" aria-hidden="true">{activeAlerts.length > 0 ? "⛔" : "✓"}</div>
        <div>
          <p className="eyebrow">Right now</p>
          <h2>{loading ? "Checking your circle…" : headline}</h2>
          <p>{activeAlerts.length > 0 ? "A dangerous scan was shared with both people in this safety circle." : "No unacknowledged danger alerts. New scans appear here automatically."}</p>
        </div>
        <div className="live-chip"><span />{sourceLabel}</div>
      </section>

      <section className="metrics" aria-label="Safety circle summary">
        <article><strong>{targetedThisMonth}</strong><span>targeted this month</span></article>
        <article><strong>{activeAlerts.length}</strong><span>need attention now</span></article>
        <article><strong>2</strong><span>people in this circle</span></article>
      </section>

      <section className="feed-section">
        <div className="section-heading">
          <div><p className="eyebrow">Shared activity</p><h2>What we both see</h2></div>
          <p>Domains and finding titles only. Never messages, screenshots, or clipboard contents.</p>
        </div>

        {loading ? <div className="empty-state"><div className="empty-orbit" /><h3>Connecting to the safety circle</h3><p>Convex will deliver new scans here without refreshing.</p></div> : null}
        {!loading && sortedScans.length === 0 ? <div className="empty-state"><div className="empty-icon">✓</div><h3>Nothing needs your attention</h3><p>When a scan is shared, it will appear here for both people at the same time.</p></div> : null}

        <div className="feed">
          {sortedScans.map((scan) => {
            const meta = verdictMeta[scan.verdict];
            const canAcknowledge = scan.verdict === "DANGER" && !scan.acknowledged && onAcknowledge;
            return (
              <article className={`scan-card scan-card--${scan.verdict.toLowerCase()} ${scan.acknowledged ? "scan-card--acknowledged" : ""}`} key={scan._id}>
                <div className="verdict-block">
                  <span className="verdict-glyph" aria-hidden="true">{meta.glyph}</span>
                  <div><span className="verdict-label">{meta.label}</span><span className="verdict-message">{meta.message}</span></div>
                </div>
                <div className="scan-detail">
                  <div className="scan-meta"><span>{scan.surface}</span><time dateTime={new Date(scan.createdAt).toISOString()}>{relativeTime(scan.createdAt, now)}</time></div>
                  <h3>{scan.domain ?? "No domain available"}</h3>
                  {scan.findingsRedacted.length > 0 ? (
                    <ul>{scan.findingsRedacted.map((finding) => <li key={`${scan._id}-${finding.code}`}><span aria-hidden="true">→</span>{finding.title}</li>)}</ul>
                  ) : <p className="no-findings">No danger signals were found.</p>}
                </div>
                <div className="card-action">
                  {canAcknowledge ? <button disabled={pendingId === scan._id} onClick={() => void handleAcknowledge(scan._id)}>{pendingId === scan._id ? "Acknowledging…" : "I’m on it"}</button> : null}
                  {scan.acknowledged && scan.verdict === "DANGER" ? <span className="acknowledged"><span aria-hidden="true">✓</span>Acknowledged</span> : null}
                  {mode === "protected" && !scan.acknowledged && scan.verdict === "DANGER" ? <span className="waiting">Waiting for guardian</span> : null}
                  {errorId === scan._id ? <span className="action-error" role="alert">Couldn’t acknowledge. Try again.</span> : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </>
  );
}

export function App({ connected }: AppProps) {
  const initialMode = new URLSearchParams(window.location.search).get("view") === "protected" ? "protected" : "guardian";
  const [mode, setMode] = useState<ViewMode>(initialMode);
  const guardianUserId = (import.meta.env.VITE_GUARDIAN_USER_ID as string | undefined) ?? "dan-demo";

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("view", mode);
    window.history.replaceState({}, "", url);
  }, [mode]);

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="/" aria-label="Something's Phishy home"><span className="brand-mark">SP</span><span>Something’s Phishy</span></a>
        <div className="view-switcher" role="group" aria-label="Choose dashboard perspective">
          <button className={mode === "guardian" ? "active" : ""} aria-pressed={mode === "guardian"} onClick={() => setMode("guardian")}>Guardian · Dan</button>
          <button className={mode === "protected" ? "active" : ""} aria-pressed={mode === "protected"} onClick={() => setMode("protected")}>My view · Margaret</button>
        </div>
        <div className="consent-pill"><span aria-hidden="true">◆</span>Shared by mutual consent</div>
      </header>

      <div className="page-shell">
        <section className="intro">
          <div><p className="eyebrow">{mode === "guardian" ? "Dan’s guardian view" : "Margaret’s own view"}</p><h1>{mode === "guardian" ? "Margaret’s safety circle" : "My safety circle"}</h1></div>
          <p>{mode === "guardian" ? "You see the same safety signals Margaret sees—nothing more." : "Dan can see exactly these same safety signals—nothing more."}</p>
        </section>
        {connected ? <LiveDashboard mode={mode} guardianUserId={guardianUserId} /> : <SeededDashboard mode={mode} />}
        <footer><span>Private by design</span><p>This is a two-sided safety net, not monitoring. Either person can leave the circle.</p></footer>
      </div>
    </main>
  );
}

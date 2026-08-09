import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery } from "convex/react";
import {
  ArrowRight, BellRinging, Check, CheckCircle, ClockCounterClockwise, Pulse,
  Eye, EyeSlash, Link as LinkIcon, LockKey, Plus, ShieldCheck, Trash, UserCircle,
  UsersThree, Warning, WarningCircle, X,
} from "@phosphor-icons/react";
import { api } from "./convex-api";
import { seededCircle, seededScans } from "./seed";
import type { GuardianLink, Scan, Verdict } from "./types";

type AppProps = { connected: boolean };
type ViewMode = "guardian" | "protected";
type Section = "active" | "history" | "circle";

type DashboardProps = {
  mode: ViewMode;
  section: Section;
  guardianUserId: string;
  onSectionChange: (section: Section) => void;
};

const verdictMeta: Record<Verdict, { label: string; message: string }> = {
  DANGER: { label: "Danger", message: "Needs attention now" },
  CAUTION: { label: "Caution", message: "Worth a closer look" },
  SAFE: { label: "Safe", message: "No danger signals found" },
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

function normalizeCircle(value: unknown): GuardianLink[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is GuardianLink => {
    if (!item || typeof item !== "object") return false;
    const link = item as Partial<GuardianLink>;
    return typeof link._id === "string" && typeof link.protectedUserId === "string" &&
      typeof link.guardianUserId === "string" && Array.isArray(link.alertOn);
  });
}

function LiveDashboard(props: DashboardProps) {
  const feedResult = useQuery(api.scans.guardianFeed, { guardianUserId: props.guardianUserId });
  const circleResult = useQuery(api.guardians.myCircle, { guardianUserId: props.guardianUserId });
  const acknowledge = useMutation(api.scans.acknowledge);
  const link = useMutation(api.guardians.link);
  const unlink = useMutation(api.guardians.unlink);

  return (
    <DashboardContent
      {...props}
      scans={useMemo(() => normalizeScans(feedResult), [feedResult])}
      circle={useMemo(() => normalizeCircle(circleResult), [circleResult])}
      loading={feedResult === undefined}
      circleLoading={circleResult === undefined}
      sourceLabel="Live via Convex"
      onAcknowledge={props.mode === "guardian" ? async (scanId) => acknowledge({ scanId }) : undefined}
      onLink={async (person) => link({ ...person, guardianUserId: props.guardianUserId, consentGiven: true, alertOn: ["DANGER", "CAUTION"] })}
      onUnlink={async (protectedUserId) => unlink({ protectedUserId, guardianUserId: props.guardianUserId })}
    />
  );
}

function SeededDashboard(props: DashboardProps) {
  const [scans, setScans] = useState(seededScans);
  const [circle, setCircle] = useState(seededCircle);

  return (
    <DashboardContent
      {...props}
      scans={scans}
      circle={circle}
      loading={false}
      circleLoading={false}
      sourceLabel="Seeded offline mode"
      onAcknowledge={props.mode === "guardian" ? async (scanId) => {
        await new Promise((resolve) => window.setTimeout(resolve, 360));
        setScans((current) => current.map((scan) => scan._id === scanId ? { ...scan, acknowledged: true } : scan));
      } : undefined}
      onLink={async ({ protectedUserId, protectedName }) => {
        await new Promise((resolve) => window.setTimeout(resolve, 240));
        setCircle((current) => [...current.filter((person) => person.protectedUserId !== protectedUserId), {
          _id: `local-${protectedUserId}`,
          protectedUserId,
          protectedName,
          guardianUserId: props.guardianUserId,
          alertOn: ["DANGER", "CAUTION"],
          consentGivenAt: Date.now(),
        }]);
      }}
      onUnlink={async (protectedUserId) => {
        await new Promise((resolve) => window.setTimeout(resolve, 240));
        setCircle((current) => current.filter((person) => person.protectedUserId !== protectedUserId));
      }}
    />
  );
}

function StatusIcon({ verdict }: { verdict: Verdict }) {
  if (verdict === "DANGER") return <WarningCircle weight="fill" aria-hidden="true" />;
  if (verdict === "CAUTION") return <Warning weight="fill" aria-hidden="true" />;
  return <CheckCircle weight="fill" aria-hidden="true" />;
}

function DashboardContent({ mode, section, scans, circle, loading, circleLoading, sourceLabel, onAcknowledge, onLink, onUnlink, onSectionChange }: DashboardProps & {
  scans: Scan[];
  circle: GuardianLink[];
  loading: boolean;
  circleLoading: boolean;
  sourceLabel: string;
  onAcknowledge?: (scanId: string) => Promise<unknown>;
  onLink: (person: { protectedUserId: string; protectedName: string }) => Promise<unknown>;
  onUnlink: (protectedUserId: string) => Promise<unknown>;
}) {
  const [now, setNow] = useState(() => Date.now());
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [leavingId, setLeavingId] = useState<string | null>(null);
  const [errorId, setErrorId] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 10_000);
    return () => window.clearInterval(timer);
  }, []);

  const sorted = useMemo(() => [...scans].sort((a, b) => b.createdAt - a.createdAt), [scans]);
  const active = sorted.filter((scan) => !scan.acknowledged && (scan.verdict === "DANGER" || scan.verdict === "CAUTION"));
  const shown = section === "active" ? active : sorted;
  const dangerCount = active.filter((scan) => scan.verdict === "DANGER").length;
  const cautionCount = active.length - dangerCount;

  const handleAcknowledge = async (scanId: string) => {
    if (!onAcknowledge) return;
    setPendingId(scanId);
    setErrorId(null);
    try {
      setLeavingId(scanId);
      await Promise.all([
        onAcknowledge(scanId),
        new Promise((resolve) => window.setTimeout(resolve, 340)),
      ]);
    } catch {
      setLeavingId(null);
      setErrorId(scanId);
    } finally {
      setPendingId(null);
      window.setTimeout(() => setLeavingId(null), 420);
    }
  };

  if (section === "circle") {
    return <CircleView mode={mode} circle={circle} loading={circleLoading} sourceLabel={sourceLabel} onLink={onLink} onUnlink={onUnlink} />;
  }

  return (
    <>
      <section className={`status-hero ${dangerCount ? "status-hero--danger" : cautionCount ? "status-hero--caution" : "status-hero--clear"}`} aria-live="polite">
        <div className="status-symbol"><StatusIcon verdict={dangerCount ? "DANGER" : cautionCount ? "CAUTION" : "SAFE"} /></div>
        <div className="status-copy">
          <p className="eyebrow">Circle status</p>
          <h2>{loading ? "Checking the horizon" : active.length ? `${active.length} alert${active.length === 1 ? "" : "s"} need attention` : "All quiet right now"}</h2>
          <p>{active.length ? "These are shared safety signals, visible to both sides of the circle." : "No unacknowledged danger or caution signals are waiting."}</p>
        </div>
        <div className="live-chip"><span aria-hidden="true" />{sourceLabel}</div>
      </section>

      <section className="metrics" aria-label="Current safety summary">
        <article><span className="metric-icon"><BellRinging aria-hidden="true" /></span><div><strong>{active.length}</strong><span>Active alerts</span></div></article>
        <article><span className="metric-icon metric-icon--danger"><WarningCircle aria-hidden="true" /></span><div><strong>{dangerCount}</strong><span>Need priority</span></div></article>
        <article><span className="metric-icon"><UsersThree aria-hidden="true" /></span><div><strong>{circle.length + 1}</strong><span>People connected</span></div></article>
      </section>

      <section className="feed-section">
        <div className="section-heading">
          <div><p className="eyebrow">{section === "active" ? "Attention queue" : "Shared record"}</p><h2>{section === "active" ? "Active signals" : "Alert history"}</h2></div>
          <p>{section === "active" ? "Only unacknowledged danger and caution alerts appear here." : "A transparent timeline of every shared signal, including resolved alerts."}</p>
        </div>

        {loading ? <LoadingState /> : null}
        {!loading && shown.length === 0 ? <EmptyState title={section === "active" ? "The horizon is clear" : "No shared activity yet"} body={section === "active" ? "New danger or caution signals will surface here automatically." : "When a scan is shared, it will be recorded here for both people."} action={section === "active" && sorted.length ? <button className="text-button" onClick={() => onSectionChange("history")}>Review history <ArrowRight aria-hidden="true" /></button> : undefined} /> : null}

        <div className="feed" aria-label={section === "active" ? "Active alerts" : "Alert history"}>
          {shown.map((scan) => {
            const meta = verdictMeta[scan.verdict];
            const canAcknowledge = !scan.acknowledged && scan.verdict !== "SAFE" && onAcknowledge;
            return <article className={`scan-card scan-card--${scan.verdict.toLowerCase()} ${scan.screenshotUrl ? "scan-card--has-screenshot" : ""} ${scan.acknowledged ? "scan-card--acknowledged" : ""} ${leavingId === scan._id ? "scan-card--leaving" : ""}`} key={scan._id}>
              <div className="verdict-block"><span className="verdict-glyph"><StatusIcon verdict={scan.verdict} /></span><div><span className="verdict-label">{meta.label}</span><span className="verdict-message">{meta.message}</span></div></div>
              {scan.screenshotUrl ? <a className="scan-screenshot" href={scan.screenshotUrl} target="_blank" rel="noreferrer" aria-label={`Open full screenshot of alert from ${scan.domain ?? scan.surface} in a new tab`}>
                <img src={scan.screenshotUrl} alt={`Screenshot shared with this alert from ${scan.domain ?? scan.surface}`} loading="lazy" decoding="async" />
                <span className="privacy-label"><LockKey aria-hidden="true" />Shared by protected person</span>
                <span className="image-action">Open full image <ArrowRight aria-hidden="true" /></span>
              </a> : null}
              <div className="scan-detail">
                <div className="scan-meta"><span>{scan.surface}</span><time dateTime={new Date(scan.createdAt).toISOString()}>{relativeTime(scan.createdAt, now)}</time></div>
                <h3>{scan.domain ?? "No domain available"}</h3>
                {scan.findingsRedacted.length ? <ul>{scan.findingsRedacted.map((finding) => <li key={`${scan._id}-${finding.code}`}><ArrowRight aria-hidden="true" />{finding.title}</li>)}</ul> : <p className="no-findings"><Check aria-hidden="true" /> No danger signals were found.</p>}
              </div>
              <div className="card-action">
                {canAcknowledge ? <button className="primary-button" disabled={pendingId === scan._id} onClick={() => void handleAcknowledge(scan._id)}><CheckCircle aria-hidden="true" />{pendingId === scan._id ? "Acknowledging" : "Acknowledge"}</button> : null}
                {scan.acknowledged && scan.verdict !== "SAFE" ? <span className="acknowledged"><CheckCircle aria-hidden="true" />Acknowledged</span> : null}
                {mode === "protected" && !scan.acknowledged && scan.verdict !== "SAFE" ? <span className="waiting"><ClockCounterClockwise aria-hidden="true" />Visible to Peyton</span> : null}
                {errorId === scan._id ? <span className="action-error" role="alert">Couldn’t acknowledge. Try again.</span> : null}
              </div>
            </article>;
          })}
        </div>
      </section>
    </>
  );
}

function LoadingState() {
  return <div className="empty-state" aria-live="polite"><div className="loading-orbit"><Pulse aria-hidden="true" /></div><h3>Connecting to your circle</h3><p>Securely listening for the latest shared signals.</p></div>;
}

function EmptyState({ title, body, action }: { title: string; body: string; action?: React.ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><ShieldCheck aria-hidden="true" /></div><h3>{title}</h3><p>{body}</p>{action}</div>;
}
function CircleView({ mode, circle, loading, sourceLabel, onLink, onUnlink }: {
  mode: ViewMode;
  circle: GuardianLink[];
  loading: boolean;
  sourceLabel: string;
  onLink: (person: { protectedUserId: string; protectedName: string }) => Promise<unknown>;
  onUnlink: (protectedUserId: string) => Promise<unknown>;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const [confirming, setConfirming] = useState<GuardianLink | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const remove = async () => {
    if (!confirming) return;
    setPending(true);
    setError("");
    try {
      await onUnlink(confirming.protectedUserId);
      setConfirming(null);
    } catch {
      setError("Couldn’t remove this person. Please try again.");
    } finally {
      setPending(false);
    }
  };

  return <section className="circle-section">
    <div className="circle-heading">
      <div><p className="eyebrow">Shared by mutual consent</p><h2>Your safety circle</h2><p>Every connection is visible, limited, and reversible. Screenshots are shared only when the protected person explicitly alerts their guardian; messages and browsing history stay private.</p></div>
      {mode === "guardian" ? <button className="primary-button" onClick={() => setModalOpen(true)}><Plus aria-hidden="true" />Add a person</button> : null}
    </div>
    <div className="transparency-note"><Eye aria-hidden="true" /><div><strong>Transparent by design</strong><span>{mode === "protected" ? "This is the complete list of people connected to this guardian view." : "People in your circle see the same alert details you do—nothing more."}</span></div><span className="source-badge">{sourceLabel}</span></div>
    {loading ? <LoadingState /> : null}
    {!loading && !circle.length ? <EmptyState title="Your circle is open" body="Add someone with their explicit consent to begin sharing danger and caution signals." /> : null}
    <div className="roster">
      {circle.map((person) => <article className="person-card" key={person._id}>
        <div className="avatar"><UserCircle weight="duotone" aria-hidden="true" /></div>
        <div className="person-copy"><p className="eyebrow">Protected person</p><h3>{person.protectedName || person.protectedUserId}</h3><span className="person-id">ID: {person.protectedUserId}</span></div>
        <div className="alert-access"><span><WarningCircle aria-hidden="true" />Danger</span><span><Warning aria-hidden="true" />Caution</span></div>
        <div className="consent-status"><ShieldCheck aria-hidden="true" /><div><strong>Consent active</strong><span>Since {new Date(person.consentGivenAt).toLocaleDateString()}</span></div></div>
        {mode === "guardian" ? <button className="icon-button danger-button" aria-label={`Remove ${person.protectedName || person.protectedUserId} from circle`} onClick={() => { setError(""); setConfirming(person); }}><Trash aria-hidden="true" /></button> : null}
      </article>)}
    </div>
    {modalOpen ? <AddPersonModal onClose={() => setModalOpen(false)} onSubmit={onLink} /> : null}
    {confirming ? <ConfirmModal person={confirming} pending={pending} error={error} onClose={() => !pending && setConfirming(null)} onConfirm={() => void remove()} /> : null}
  </section>;
}

function ModalShell({ titleId, onClose, children }: { titleId: string; onClose: () => void; children: React.ReactNode }) {
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKeyDown);
    panelRef.current?.querySelector<HTMLElement>("button, input")?.focus();
    return () => { document.removeEventListener("keydown", onKeyDown); previous?.focus(); };
  }, [onClose]);
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={panelRef}>{children}</div></div>;
}

function AddPersonModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (person: { protectedUserId: string; protectedName: string }) => Promise<unknown> }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const protectedName = String(data.get("name") ?? "").trim();
    const protectedUserId = String(data.get("id") ?? "").trim();
    if (!protectedName || !protectedUserId) return;
    setPending(true);
    setError("");
    try {
      await onSubmit({ protectedName, protectedUserId });
      onClose();
    } catch {
      setError("Couldn’t add this person. Check the ID and try again.");
      setPending(false);
    }
  };
  return <ModalShell titleId="add-person-title" onClose={onClose}>
    <div className="modal-icon"><LinkIcon aria-hidden="true" /></div><button className="modal-close" aria-label="Close dialog" onClick={onClose}><X aria-hidden="true" /></button>
    <p className="eyebrow">Mutual connection</p><h2 id="add-person-title">Add a person</h2><p>Only connect after they have agreed to share danger and caution alerts with you.</p>
    <form onSubmit={(event) => void submit(event)}><label htmlFor="person-name">Their name</label><input id="person-name" name="name" autoComplete="name" required placeholder="Logan" /><label htmlFor="person-id">Protected user ID</label><input id="person-id" name="id" required placeholder="margaret-demo" /><label className="consent-check" htmlFor="mutual-consent"><input id="mutual-consent" name="consent" type="checkbox" required /><ShieldCheck aria-hidden="true" /><span>Both people have explicitly agreed to share DANGER + CAUTION alerts.</span></label>{error ? <p className="form-error" role="alert">{error}</p> : null}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={pending}><LinkIcon aria-hidden="true" />{pending ? "Connecting" : "Connect person"}</button></div></form>
  </ModalShell>;
}
function ConfirmModal({ person, pending, error, onClose, onConfirm }: { person: GuardianLink; pending: boolean; error: string; onClose: () => void; onConfirm: () => void }) {
  return <ModalShell titleId="remove-person-title" onClose={onClose}>
    <div className="modal-icon modal-icon--danger"><Trash aria-hidden="true" /></div><button className="modal-close" aria-label="Close dialog" onClick={onClose}><X aria-hidden="true" /></button>
    <p className="eyebrow">End connection</p><h2 id="remove-person-title">Remove {person.protectedName || "this person"}?</h2><p>Future alerts will stop appearing in this guardian view. This does not delete their scan history.</p>
    {error ? <p className="form-error" role="alert">{error}</p> : null}<div className="modal-actions"><button className="secondary-button" disabled={pending} onClick={onClose}>Keep connection</button><button className="primary-button primary-button--danger" disabled={pending} onClick={onConfirm}><Trash aria-hidden="true" />{pending ? "Removing" : "Remove person"}</button></div>
  </ModalShell>;
}

export function App({ connected }: AppProps) {
  const params = new URLSearchParams(window.location.search);
  const initialMode = params.get("view") === "protected" ? "protected" : "guardian";
  const initialSection = params.get("section");
  const [mode, setMode] = useState<ViewMode>(initialMode);
  const [section, setSection] = useState<Section>(initialSection === "history" || initialSection === "circle" ? initialSection : "active");
  const guardianUserId = (import.meta.env.VITE_GUARDIAN_USER_ID as string | undefined) ?? "dan-demo";

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("view", mode);
    url.searchParams.set("section", section);
    window.history.replaceState({}, "", url);
  }, [mode, section]);

  const nav = [
    { id: "active" as const, label: "Active", icon: BellRinging },
    { id: "history" as const, label: "History", icon: ClockCounterClockwise },
    { id: "circle" as const, label: "Circle", icon: UsersThree },
  ];
  const dashboardProps = { mode, section, guardianUserId, onSectionChange: setSection };

  return <main>
    <header className="topbar">
      <a className="brand" href="/" aria-label="Something's Phishy home"><span className="brand-mark"><ShieldCheck weight="fill" aria-hidden="true" /></span><span>Something’s Phishy</span></a>
      <nav className="primary-nav" aria-label="Dashboard sections">{nav.map(({ id, label, icon: Icon }) => <button key={id} className={section === id ? "active" : ""} aria-current={section === id ? "page" : undefined} onClick={() => setSection(id)}><Icon aria-hidden="true" />{label}</button>)}</nav>
      <div className="view-switcher" role="group" aria-label="Choose dashboard perspective"><button className={mode === "guardian" ? "active" : ""} aria-pressed={mode === "guardian"} onClick={() => setMode("guardian")}><Eye aria-hidden="true" />Peyton</button><button className={mode === "protected" ? "active" : ""} aria-pressed={mode === "protected"} onClick={() => setMode("protected")}><EyeSlash aria-hidden="true" />Logan</button></div>
    </header>
    <div className="page-shell">
      <section className="intro"><div><p className="eyebrow">{mode === "guardian" ? "Peyton’s guardian view" : "Logan’s protected view"}</p><h1>{section === "circle" ? "Connected with care" : mode === "guardian" ? "Logan’s safety, at a glance" : "Your safety, fully visible"}</h1></div><p>{mode === "guardian" ? "A calm place to notice what matters and respect everything that doesn’t." : "Peyton sees these same safety signals. Screenshots are shared only when you explicitly alert your guardian; messages and other activity stay private."}</p></section>
      {connected ? <LiveDashboard {...dashboardProps} /> : <SeededDashboard {...dashboardProps} />}
      <footer><div><LockKey aria-hidden="true" /><span>Private by design</span></div><p>A two-sided safety net, never surveillance. Either person can leave.</p></footer>
    </div>
  </main>;
}

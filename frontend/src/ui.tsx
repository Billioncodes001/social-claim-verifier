import {
  cloneElement,
  createContext,
  useContext,
  useId,
  useState,
  type ButtonHTMLAttributes,
  type ReactElement,
  type ReactNode,
} from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  ChevronRight,
  FileSearch,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { stamp, safeUrl } from "./api";
import type { CaseSummary, User, Workspace } from "./types";
import { platformNames } from "./types";

export const AppContext = createContext<{
  user: User;
  workspace: Workspace;
  notify: (message: string) => void;
}>({
  user: { username: "", role: "reviewer" },
  workspace: {
    name: "Claim Verifier",
    organization: "Moderation workspace",
    demo_daily_limit: 20,
  },
  notify: () => {},
});
export const useApp = () => useContext(AppContext);
export function Button({
  children,
  variant = "primary",
  busy = false,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      {...props}
      disabled={props.disabled || busy}
      className={`button button-${variant} ${className}`}
    >
      {busy && <LoaderCircle className="size-4 animate-spin" />}
      {children}
    </button>
  );
}
export function Action({
  children,
  onAction,
  variant = "secondary",
  className = "",
  ...props
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> & {
  onAction: () => Promise<unknown>;
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const [busy, setBusy] = useState(false);
  const { notify } = useApp();
  return (
    <Button
      {...props}
      variant={variant}
      className={className}
      busy={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await onAction();
        } catch (e) {
          notify((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      {children}
    </Button>
  );
}
export function Form({
  children,
  onSubmit,
  className = "",
  id,
}: {
  children: ReactNode;
  onSubmit: (data: FormData, form: HTMLFormElement) => Promise<unknown>;
  className?: string;
  id?: string;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <form
      id={id}
      className={className}
      onSubmit={async (event) => {
        event.preventDefault();
        if (busy) return;
        const form = event.currentTarget;
        const values = new FormData(form);
        setBusy(true);
        setError("");
        try {
          await onSubmit(values, form);
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
      aria-busy={busy}
    >
      <fieldset disabled={busy} className="min-w-0 space-y-5">
        {children}
      </fieldset>
      {busy && (
        <p
          className="mt-4 flex items-center gap-2 text-sm text-slate-500"
          role="status"
        >
          <LoaderCircle className="size-4 animate-spin" />
          Working on your request…
        </p>
      )}
      {error && (
        <Notice tone="error" className="mt-4">
          {error}
        </Notice>
      )}
    </form>
  );
}
export function Field({
  label,
  children,
  hint,
  className = "",
}: {
  label: string;
  children: ReactElement<{ id?: string }>;
  hint?: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={`field ${className}`}>
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, { id })}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}
export function Checkbox({
  children,
  name,
  defaultChecked = false,
  onChange,
  checked,
}: {
  children: ReactNode;
  name?: string;
  defaultChecked?: boolean;
  checked?: boolean;
  onChange?: (value: boolean) => void;
}) {
  return (
    <label className="checkbox">
      <input
        type="checkbox"
        name={name}
        {...(checked === undefined ? { defaultChecked } : { checked })}
        onChange={(e) => onChange?.(e.target.checked)}
      />
      <span>{children}</span>
    </label>
  );
}
export function Consent({
  external = false,
  search = false,
}: {
  external?: boolean;
  search?: boolean;
}) {
  return (
    <div className="space-y-3">
      <Checkbox name="external" defaultChecked={external}>
        Allow configured hosted AI to process this content
      </Checkbox>
      <Checkbox name="search" defaultChecked={search}>
        Allow searches through the configured evidence provider
      </Checkbox>
    </div>
  );
}
export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`card ${className}`}>{children}</section>;
}
export function SectionTitle({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function PageHead({
  title,
  description,
  eyebrow = "Verification workspace",
  action,
}: {
  title: string;
  description: string;
  eyebrow?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Notice({
  children,
  tone = "info",
  className = "",
}: {
  children: ReactNode;
  tone?: "info" | "error" | "success";
  className?: string;
}) {
  return (
    <div
      className={`notice notice-${tone} ${className}`}
      role={tone === "error" ? "alert" : undefined}
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <div>{children}</div>
    </div>
  );
}
const labels: Record<string, string> = {
  needs_review: "Ready for review",
  processing: "In progress",
  queued: "Queued",
  blocked: "Needs attention",
  reviewed: "Reviewed",
  not_checkable: "Not checkable",
  missing_context: "Missing context",
  outdated_context: "Outdated context",
  conflicting_evidence: "Conflicting evidence",
  contradicted: "Contradicted",
  supported: "Supported",
  unresolved: "Unresolved",
};
export function Badge({
  value,
  children,
}: {
  value: string;
  children?: ReactNode;
}) {
  const tone = [
    "supported",
    "complete",
    "active",
    "retrieved",
    "ready",
    "reviewed",
  ].includes(value)
    ? "green"
    : ["contradicted", "blocked", "expired", "connection_failed"].includes(
          value,
        )
      ? "red"
      : ["processing", "queued"].includes(value)
        ? "blue"
        : [
              "needs_review",
              "unresolved",
              "missing_context",
              "outdated_context",
            ].includes(value)
          ? "amber"
          : "neutral";
  return (
    <span className={`badge badge-${tone}`}>
      <span className="badge-dot" />
      {children || labels[value] || value.replaceAll("_", " ")}
    </span>
  );
}
export function External({
  url,
  children,
  className = "",
}: {
  url?: string;
  children: ReactNode;
  className?: string;
}) {
  return safeUrl(url) ? (
    <a
      className={`external ${className}`}
      href={url}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
      <ArrowUpRight className="inline size-3.5 shrink-0" />
    </a>
  ) : (
    <span>{children}</span>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <FileSearch className="size-6" />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div
      className="space-y-6 py-4"
      role="status"
      aria-label="Loading workspace"
    >
      <div className="skeleton h-9 w-60" />
      <div className="skeleton h-5 w-80 max-w-full" />
      <div className="skeleton h-64 w-full" />
      <span className="sr-only">Loading…</span>
    </div>
  );
}
export function QueryState({
  loading,
  error,
}: {
  loading: boolean;
  error: Error | null;
}) {
  if (error)
    return (
      <Notice tone="error">
        {error.message}{" "}
        <button className="text-link ml-2" onClick={() => location.reload()}>
          Reload
        </button>
      </Notice>
    );
  return loading ? <Loading /> : null;
}
export function PlatformMark({
  platform,
  className = "",
}: {
  platform: string;
  className?: string;
}) {
  return (
    <span
      className={`platform-mark platform-${platform} ${className}`}
      aria-hidden="true"
    >
      {platform === "facebook" ? (
        "f"
      ) : platform === "instagram" ? (
        <svg
          width="19"
          height="19"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
        >
          <rect x="3" y="3" width="18" height="18" rx="5" />
          <circle cx="12" cy="12" r="4" />
          <circle cx="17.5" cy="6.5" r=".8" fill="currentColor" />
        </svg>
      ) : platform === "x" ? (
        "𝕏"
      ) : platform === "rss" ? (
        "↗"
      ) : (
        <FileSearch className="size-4" />
      )}
    </span>
  );
}
export function CaseList({
  cases,
  compact = false,
  action,
}: {
  cases: CaseSummary[];
  compact?: boolean;
  action?: (c: CaseSummary) => ReactNode;
}) {
  if (!cases.length)
    return (
      <Empty title="A clear starting point">
        Your investigations will appear here when you submit a post.
      </Empty>
    );
  return (
    <div className="case-list">
      {cases.map((c) => (
        <div className="case-list-item" key={c.id}>
          <a className="case-link group" href={"#case/" + c.id}>
            <PlatformMark platform={c.platform} />
            <div className="min-w-0 flex-1">
              <p className={compact ? "line-clamp-1" : "line-clamp-2"}>
                {c.text || "Content removed"}
              </p>
              <div className="case-meta">
                {platformNames[c.platform] || c.platform}
                <span>·</span>
                {stamp(c.created)}
                {Boolean(c.is_demo) && (
                  <>
                    <span>·</span>Demo
                  </>
                )}
              </div>
            </div>
            <Badge value={c.status} />
            <ChevronRight className="size-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5" />
          </a>
          {action?.(c)}
        </div>
      ))}
    </div>
  );
}
export function Logo({
  name = "Claim Verifier",
  small = false,
}: {
  name?: string;
  small?: boolean;
}) {
  return (
    <div className="brand">
      <span className="brand-mark">
        <ShieldCheck className="size-6" strokeWidth={1.6} />
      </span>
      <div>
        <strong>{name}</strong>
        {!small && <span>TRUST OPERATIONS</span>}
      </div>
    </div>
  );
}
export function PageMotion({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.22, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
export function CheckLine({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <Check className="mt-0.5 size-4 shrink-0 text-emerald-700" />
      <span>{children}</span>
    </div>
  );
}

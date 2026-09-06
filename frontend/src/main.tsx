import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import {
  ArrowRight,
  Building2,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  FlaskConical,
  LayoutDashboard,
  Link2,
  LogOut,
  Menu,
  Network,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Workflow,
  X,
} from "lucide-react";
import "@fontsource-variable/dm-sans";
import "@fontsource-variable/newsreader";
import "@fontsource-variable/newsreader/wght-italic.css";
import "./styles.css";
import { api, field, navigate, queryClient, send, useResource } from "./api";
import {
  AppContext,
  Button,
  Card,
  Field,
  Form,
  Loading,
  Logo,
  Notice,
  PageMotion,
} from "./ui";
import type { User, WorkspaceConfig } from "./types";
import {
  Overview,
  Queue,
  Investigation,
  Investigate,
} from "./pages/investigations";
import { Demo } from "./pages/demo";
import {
  Agents,
  Connections,
  Integrations,
  PolicyPage,
  Audit,
  WorkspaceSetup,
  PlatformApps,
} from "./pages/settings";

const navigation = [
  { id: "overview", title: "Overview", icon: LayoutDashboard },
  { id: "demo", title: "Demo lab", icon: FlaskConical },
  { id: "queue", title: "Review queue", icon: ClipboardList },
  { id: "investigate", title: "Investigate", icon: Search },
  { id: "agents", title: "Agent team", icon: Workflow },
];
const administration = [
  { id: "deployment", title: "Workspace setup", icon: Settings2 },
  { id: "socialapps", title: "Platform apps", icon: Network },
  { id: "connections", title: "AI connections", icon: Link2 },
  { id: "integrations", title: "Integrations", icon: Building2 },
  { id: "policy", title: "Review policy", icon: SlidersHorizontal },
  { id: "audit", title: "Audit trail", icon: ClipboardList },
];
const getRoute = () => location.hash.slice(1).split("?")[0] || "overview";
function Auth({
  setup,
  onUser,
}: {
  setup: boolean;
  onUser: (user: User) => void;
}) {
  return (
    <div className="auth-layout">
      <section className="auth-editorial">
        <img
          src="/assets/apollo-earthrise.jpg"
          alt="Earth above the lunar horizon, photographed during Apollo 11"
        />
        <div className="auth-overlay" />
        <div className="relative z-10 flex h-full flex-col justify-between">
          <Logo />
          <div>
            <div className="eyebrow text-white/70">
              Perspective changes everything.
            </div>
            <h1>
              Clarity begins
              <br />
              with evidence.
            </h1>
            <p>
              A considered approach to checking claims, understanding context
              and earning trust.
            </p>
          </div>
          <div className="image-credit">Apollo 11 · NASA, AS11-44-6550</div>
        </div>
      </section>
      <section className="auth-content">
        <div className="w-full max-w-sm">
          <div className="mb-12 lg:hidden">
            <Logo />
          </div>
          <span className="eyebrow">YOUR VERIFICATION WORKSPACE</span>
          <h2 className="font-editorial mt-4 mb-3 text-4xl">
            {setup ? "Start with trust." : "Welcome back."}
          </h2>
          <p className="mb-8 text-sm leading-6 text-slate-500">
            {setup
              ? "Create your administrator account and bring your verification team together."
              : "Sign in to your organization’s verification workspace."}
          </p>
          <Form
            onSubmit={async (f) => {
              const user = await send<User>(
                "/auth/" + (setup ? "setup" : "login"),
                {
                  username: field(f, "username"),
                  password: String(f.get("password")),
                },
              );
              onUser(user);
            }}
          >
            <Field label="Username">
              <input
                name="username"
                autoComplete="username"
                minLength={3}
                required
              />
            </Field>
            <Field label="Password">
              <input
                name="password"
                type="password"
                autoComplete={setup ? "new-password" : "current-password"}
                minLength={12}
                required
              />
            </Field>
            <Button type="submit" className="w-full">
              {setup ? "Create workspace" : "Sign in"}
              <ArrowRight className="size-4" />
            </Button>
          </Form>
          <p className="mt-8 flex items-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="size-4" />
            Private deployment. Human review at every decision.
          </p>
        </div>
      </section>
    </div>
  );
}
function Workspace({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [route, setRoute] = useState(getRoute),
    [open, setOpen] = useState(false),
    [toast, setToast] = useState(""),
    [search, setSearch] = useState("");
  const config = useResource<WorkspaceConfig>("/workspace");
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const menu = document.getElementById("workspace-navigation");
    const focusable = () =>
      Array.from(
        menu?.querySelectorAll<HTMLElement>("a[href],button:not(:disabled)") ||
          [],
      ).filter((el) => el.getClientRects().length > 0);
    focusable()[0]?.focus();
    const trap = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const items = focusable(),
        first = items[0],
        last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    menu?.addEventListener("keydown", trap);
    return () => {
      menu?.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, [open]);
  useEffect(() => {
    const change = () => {
      setRoute(getRoute());
      setOpen(false);
      document.getElementById("main-content")?.scrollTo(0, 0);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 6500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, []);
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);
  if (config.isPending)
    return (
      <div className="mx-auto max-w-5xl p-10">
        <Loading />
      </div>
    );
  if (!config.data)
    return (
      <div className="p-8">
        <Notice tone="error">
          {config.error?.message || "Workspace unavailable"}
        </Notice>
      </div>
    );
  const active = route.startsWith("case/") ? "queue" : route;
  const current =
    [...navigation, ...administration].find((x) => x.id === active)?.title ||
    "Overview";
  const LinkGroup = ({ items }: { items: typeof navigation }) => (
    <nav className="nav-group">
      {items.map(({ id, title, icon: Icon }) => (
        <a
          href={"#" + id}
          key={id}
          className={`nav-item ${active === id ? "active" : ""}`}
          aria-current={active === id ? "page" : undefined}
          onClick={() => setOpen(false)}
        >
          <Icon className="size-[18px]" strokeWidth={1.6} />
          <span>{title}</span>
          {id === "demo" && <span className="nav-new">TRY IT</span>}
        </a>
      ))}
    </nav>
  );
  const views: Record<string, React.ReactNode> = {
    overview: <Overview />,
    demo: <Demo />,
    queue: <Queue />,
    investigate: <Investigate />,
    agents: <Agents />,
    deployment: <WorkspaceSetup />,
    socialapps: <PlatformApps />,
    connections: <Connections />,
    integrations: <Integrations />,
    policy: <PolicyPage />,
    audit: <Audit />,
  };
  const restricted =
    administration.some((x) => x.id === active) && user.role !== "admin";
  return (
    <AppContext.Provider
      value={{ user, workspace: config.data.workspace, notify: setToast }}
    >
      <div className="workspace-shell">
        <a
          className="skip-link"
          href="#main-content"
          onClick={(e) => {
            e.preventDefault();
            document.getElementById("main-content")?.focus();
          }}
        >
          Skip to content
        </a>
        {open && (
          <button
            className="sidebar-backdrop"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          />
        )}
        <aside
          id="workspace-navigation"
          className={`sidebar ${open ? "is-open" : ""}`}
          aria-label="Workspace navigation"
          role={open ? "dialog" : undefined}
          aria-modal={open || undefined}
        >
          <div className="flex items-center justify-between">
            <a href="#overview" className="min-w-0">
              <Logo name={config.data.workspace.name} />
            </a>
            <button
              className="icon-button lg:hidden"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
            >
              <X className="size-5" />
            </button>
          </div>
          <div className="workspace-switch">
            <span className="workspace-initial">
              {config.data.workspace.organization.slice(0, 1)}
            </span>
            <div className="min-w-0">
              <strong>{config.data.workspace.organization}</strong>
              <span>Private workspace</span>
            </div>
          </div>
          <div className="nav-heading">WORKSPACE</div>
          <LinkGroup items={navigation} />
          {user.role === "admin" && (
            <>
              <div className="nav-heading mt-8">ADMINISTRATION</div>
              <LinkGroup items={administration} />
            </>
          )}
          <div className="sidebar-bottom">
            <div className="sidebar-note">
              <ShieldCheck className="size-5" />
              <p>
                <strong>Evidence before action.</strong>
                <span>Your team stays in control.</span>
              </p>
            </div>
            <p className="text-xs text-slate-500">
              Claim Verifier <span className="ml-2">v0.3</span>
            </p>
          </div>
        </aside>
        <div className="main-shell" inert={open}>
          <header className="topbar">
            <div className="flex min-w-0 items-center gap-3">
              <button
                className="icon-button lg:hidden"
                aria-label="Open navigation"
                aria-expanded={open}
                aria-controls="workspace-navigation"
                onClick={() => setOpen(!open)}
              >
                <Menu className="size-5" />
              </button>
              <span className="hidden text-slate-400 sm:inline">Workspace</span>
              <ChevronRight className="hidden size-3.5 text-slate-300 sm:block" />
              <span className="truncate font-medium">{current}</span>
            </div>
            <div className="flex items-center gap-5">
              <form
                className="topbar-search hidden xl:flex"
                onSubmit={(e) => {
                  e.preventDefault();
                  navigate("queue?search=" + encodeURIComponent(search));
                }}
              >
                <Search className="size-4" />
                <input
                  aria-label="Search investigations"
                  placeholder="Search investigations"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <kbd>↵</kbd>
              </form>
              <span className="review-indicator hidden md:flex">
                <span />
                Human review enabled
              </span>
              <div className="user-menu">
                <span className="avatar">{user.username[0].toUpperCase()}</span>
                <span className="hidden xl:block">{user.username}</span>
                <button
                  className="icon-button"
                  title="Sign out"
                  aria-label="Sign out"
                  onClick={async () => {
                    try {
                      await send("/auth/logout");
                      onLogout();
                    } catch (e) {
                      setToast((e as Error).message);
                    }
                  }}
                >
                  <LogOut className="size-4" />
                </button>
              </div>
            </div>
          </header>
          <main id="main-content" tabIndex={-1} className="main-content">
            <PageMotion key={route}>
              {restricted ? (
                <Notice tone="error">
                  Administrator access is required to manage these settings.
                </Notice>
              ) : route.startsWith("case/") ? (
                <Investigation id={route.split("/")[1]} />
              ) : (
                views[route] || views.overview
              )}
            </PageMotion>
            <footer className="workspace-footer">
              <span>Claim Verifier · Evidence-led decisions</span>
              <span>
                <ShieldCheck className="size-3.5" />
                Private workspace
              </span>
            </footer>
          </main>
        </div>
      </div>
      <AnimatePresence>
        {toast && (
          <motion.div
            role="status"
            className="toast"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
          >
            <Check className="size-4 shrink-0" />
            <span>{toast}</span>
            <button
              aria-label="Dismiss notification"
              onClick={() => setToast("")}
            >
              <X className="size-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </AppContext.Provider>
  );
}
function App() {
  const [user, setUser] = useState<User | null>(null),
    [setup, setSetup] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  useEffect(() => {
    api<{ user: User | null; setup_required: boolean }>("/auth/status")
      .then((s) => {
        setUser(s.user);
        setSetup(s.setup_required);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    const expire = () => {
      setUser(null);
      queryClient.clear();
    };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);
  if (loading)
    return (
      <div className="mx-auto max-w-4xl p-10">
        <Loading />
      </div>
    );
  if (error)
    return (
      <div className="p-10">
        <Notice tone="error">{error}</Notice>
      </div>
    );
  return user ? (
    <Workspace
      user={user}
      onLogout={() => {
        setUser(null);
        queryClient.clear();
      }}
    />
  ) : (
    <Auth setup={setup} onUser={setUser} />
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <App />
      </MotionConfig>
    </QueryClientProvider>
  </React.StrictMode>,
);

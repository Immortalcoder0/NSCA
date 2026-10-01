import React, { useState } from "react";
import { Link, useLocation, Outlet } from "react-router-dom";
import {
  ShieldCheck,
  FolderKanban,
  Server,
  AlertOctagon,
  GraduationCap,
  BookOpen,
  FileBarChart,
  Settings,
  UserCheck,
  Palette,
  Sparkles,
  Loader2,
} from "lucide-react";
import { useAuth } from "./auth-guard";
import { ROLE_LABELS, type UserRole } from "../shared/types/domain";
import { cn } from "../shared/lib/utils";
import { useSeedDemoData } from "../shared/api/hooks/useDemoSeed";

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  trackOwner: string;
}

const NAV_ITEMS: NavItem[] = [
  { name: "Campaigns", href: "/campaigns", icon: FolderKanban, trackOwner: "Track 1" },
  { name: "Estate", href: "/estate", icon: Server, trackOwner: "Track 1" },
  { name: "Findings", href: "/findings", icon: AlertOctagon, trackOwner: "Track 2" },
  { name: "Training Studio", href: "/training", icon: GraduationCap, trackOwner: "Track 3" },
  { name: "Knowledge", href: "/knowledge", icon: BookOpen, trackOwner: "Track 3" },
  { name: "Reports", href: "/reports", icon: FileBarChart, trackOwner: "Track 3" },
  { name: "Administration", href: "/admin", icon: Settings, trackOwner: "Track 3" },
];

export const Shell: React.FC = () => {
  const location = useLocation();
  const { role, setRole } = useAuth();
  const seedDemoData = useSeedDemoData();
  const [seedMessage, setSeedMessage] = useState<string | null>(null);

  const handleSeedDemoData = () => {
    setSeedMessage(null);
    seedDemoData.mutate(undefined, {
      onSuccess: (result) => {
        setSeedMessage(
          `Seeded ${result.campaign_id}: ${result.devices_uploaded} devices, ` +
            `${result.devices_assessed} assessed, report ${result.report_id ?? "n/a"}, ` +
            `${result.training_questions_seeded} training questions queued.`
        );
      },
      onError: (err) => {
        setSeedMessage(err instanceof Error ? `Seed failed: ${err.message}` : "Seed failed.");
      },
    });
  };

  const isCurrent = (path: string) => {
    if (path === "/campaigns" && (location.pathname === "/" || location.pathname.startsWith("/campaigns"))) {
      return true;
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* Top Application Header - Clean Minimalist Executive Nav */}
      <header className="sticky top-0 z-40 w-full border-b border-border/80 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="container flex h-14 max-w-screen-2xl items-center justify-between px-4 sm:px-6">
          {/* Logo & Product Brand */}
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="p-1.5 rounded-md bg-foreground text-background">
                <ShieldCheck size={16} className="stroke-[2.5]" />
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-bold tracking-tight text-foreground">
                    NSCA
                  </span>
                  <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono text-[9px] font-semibold">
                    AIR-GAP
                  </span>
                </div>
                <span className="text-[9px] text-muted-foreground font-mono leading-none">
                  Security Compliance
                </span>
              </div>
            </Link>

            {/* Main Navigation - Clean Underlined/Subtle Pill Tabs */}
            <nav className="hidden xl:flex items-center gap-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = isCurrent(item.href);
                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    title={`Owner: ${item.trackOwner}`}
                    className={cn(
                      "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors select-none",
                      active
                        ? "bg-secondary text-foreground font-semibold shadow-xs"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                    )}
                  >
                    <Icon size={14} className={cn("shrink-0", active ? "text-foreground" : "text-muted-foreground")} />
                    <span>{item.name}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Right Toolbar: Role Chip & Showcase Link */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={handleSeedDemoData}
              disabled={seedDemoData.isPending}
              title="Populate the app with a complete, real demo dataset — one campaign, 8 multi-platform devices, a real assessment, an issued report, and a live training queue, all created through the real API (not fake client-side data)."
              className={cn(
                "hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition-colors border",
                seedDemoData.isPending
                  ? "border-border/60 text-muted-foreground cursor-wait"
                  : "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20"
              )}
            >
              {seedDemoData.isPending ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Sparkles size={13} />
              )}
              <span>{seedDemoData.isPending ? "Seeding…" : "Fill With Demo Data"}</span>
            </button>

            <Link
              to="/_showcase"
              title="Design Tokens & Badge Showcase"
              className={cn(
                "hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors border border-border/60",
                location.pathname === "/_showcase" && "bg-secondary text-foreground font-semibold"
              )}
            >
              <Palette size={13} />
              <span>Design System</span>
            </Link>

            {/* Dev Role Switcher Chip */}
            <div className="flex items-center gap-1.5 bg-secondary/80 px-2.5 py-1 rounded-md border border-border/80 text-xs">
              <UserCheck size={13} className="text-muted-foreground shrink-0" />
              <span className="text-muted-foreground hidden md:inline text-[11px]">Role:</span>
              <select
                aria-label="Dev RBAC Role Switcher"
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="bg-transparent font-semibold text-foreground text-xs focus:outline-none cursor-pointer pr-1"
              >
                {(Object.keys(ROLE_LABELS) as UserRole[]).map((r) => (
                  <option key={r} value={r} className="bg-popover text-popover-foreground">
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Medium Screen Navigation Bar */}
        <nav className="flex xl:hidden overflow-x-auto border-t border-border/60 px-4 py-1.5 gap-1 bg-secondary/30">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isCurrent(item.href);
            return (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs whitespace-nowrap font-medium transition-colors",
                  active
                    ? "bg-secondary text-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon size={13} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </header>

      {seedMessage && (
        <div
          className={cn(
            "w-full px-4 sm:px-6 py-2 text-xs font-mono border-b",
            seedDemoData.isError
              ? "bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400"
              : "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400"
          )}
        >
          <div className="container max-w-screen-2xl mx-auto flex items-center justify-between gap-4">
            <span>{seedMessage}</span>
            <button
              type="button"
              onClick={() => setSeedMessage(null)}
              className="text-current opacity-70 hover:opacity-100 shrink-0"
              aria-label="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Main Content Workspace */}
      <main className="flex-1 container max-w-screen-2xl py-6 px-4 sm:px-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-border/60 py-3.5 px-6 text-center text-xs text-muted-foreground bg-card/50">
        <div className="flex flex-col sm:flex-row items-center justify-between max-w-screen-2xl mx-auto gap-2">
          <span>NSCA · National Security Compliance Architecture</span>
          <span className="font-mono text-[11px]">Air-Gapped Operation · Zero External Egress</span>
        </div>
      </footer>
    </div>
  );
};

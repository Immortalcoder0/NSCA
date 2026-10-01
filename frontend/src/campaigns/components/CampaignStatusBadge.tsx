import React from "react";
import {
  FileEdit,
  DownloadCloud,
  Cpu,
  SearchCheck,
  Lock,
  Archive,
} from "lucide-react";
import type { CampaignLifecycleState } from "../types";
import { cn } from "../../shared/lib/utils";

interface CampaignStatusBadgeProps {
  status: CampaignLifecycleState | string;
  className?: string;
}

export const CampaignStatusBadge: React.FC<CampaignStatusBadgeProps> = ({
  status,
  className,
}) => {
  const normalized = (status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()) as CampaignLifecycleState;

  const config: Record<
    CampaignLifecycleState,
    { label: string; icon: React.ComponentType<{ size?: number; className?: string }>; color: string }
  > = {
    Draft: {
      label: "Draft",
      icon: FileEdit,
      color: "bg-slate-100 text-slate-800 border-slate-300 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-700",
    },
    Collecting: {
      label: "Collecting",
      icon: DownloadCloud,
      color: "bg-sky-50 text-sky-800 border-sky-300 dark:bg-sky-950/60 dark:text-sky-300 dark:border-sky-800",
    },
    Assessing: {
      label: "Assessing",
      icon: Cpu,
      color: "bg-purple-50 text-purple-800 border-purple-300 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800",
    },
    Review: {
      label: "In Review",
      icon: SearchCheck,
      color: "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800",
    },
    Issued: {
      label: "Issued (Immutable)",
      icon: Lock,
      color: "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800 font-bold",
    },
    Closed: {
      label: "Closed",
      icon: Archive,
      color: "bg-zinc-100 text-zinc-700 border-zinc-300 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-800",
    },
  };

  const current = config[normalized] || config.Draft;
  const Icon = current.icon;

  return (
    <span
      role="status"
      aria-label={`Campaign Status: ${current.label}`}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-xs select-none",
        current.color,
        className
      )}
    >
      <Icon size={12} className="shrink-0" />
      <span>{current.label}</span>
    </span>
  );
};

import React, { useState } from "react";
import { X, Plus, ShieldCheck, Calendar, Filter } from "lucide-react";
import type { CampaignFramework } from "../types";
import { ScopeResolverSummary } from "./ScopeResolverSummary";

interface CampaignCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (campaignData: {
    name: string;
    scope: { type: string; expression: string };
    frameworks: CampaignFramework[];
    owner: string;
    window: { start: string; end: string };
  }) => void;
}

const AVAILABLE_FRAMEWORKS: Array<{
  id: string;
  name: string;
  framework: string;
  benchmark?: string;
  catalog?: string;
  revision?: string;
  version?: string;
  release?: string;
}> = [
  {
    id: "cis-cisco-15",
    name: "CIS Cisco IOS 15 Benchmark v4.1.0",
    framework: "cis",
    benchmark: "cisco_ios_15",
    version: "4.1.0",
  },
  {
    id: "nist-800-53",
    name: "NIST SP 800-53 Rev5 Security Controls",
    framework: "nist",
    catalog: "800-53",
    revision: "Rev5",
  },
  {
    id: "stig-2026-01",
    name: "DoD DISA STIG Network Release 2026-01",
    framework: "stig",
    release: "2026-01",
  },
  {
    id: "iso-27001",
    name: "ISO/IEC 27001:2022 Annex A",
    framework: "iso",
    version: "2022",
  },
];

const PRESET_EXPRESSIONS = [
  {
    label: "Internet-Facing & Access Sample (Priya Default)",
    expression: "exposure == 'internet_facing' or (role == 'access' and sample(0.10))",
  },
  {
    label: "Core & Distribution Tier",
    expression: "role in ['core', 'distribution']",
  },
  {
    label: "Full Estate Scope (100%)",
    expression: "exposure in ['internet_facing', 'internal', 'isolated']",
  },
];

export const CampaignCreateModal: React.FC<CampaignCreateModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
}) => {
  const [name, setName] = useState("Q3-2026 Core Infrastructure Audit");
  const [owner, setOwner] = useState("p.sharma");
  const [startDate, setStartDate] = useState("2026-09-01");
  const [endDate, setEndDate] = useState("2026-09-30");
  const [expression, setExpression] = useState(
    "exposure == 'internet_facing' or (role == 'access' and sample(0.10))"
  );
  const [selectedFrameworkIds, setSelectedFrameworkIds] = useState<string[]>([
    "cis-cisco-15",
    "nist-800-53",
    "stig-2026-01",
  ]);

  if (!isOpen) return null;

  const toggleFramework = (id: string) => {
    setSelectedFrameworkIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const selectedFrameworks = AVAILABLE_FRAMEWORKS.filter((f) =>
      selectedFrameworkIds.includes(f.id)
    ).map(({ id: _id, name: _name, ...rest }) => rest);

    onSubmit({
      name,
      owner,
      scope: {
        type: "filter",
        expression,
      },
      frameworks: selectedFrameworks,
      window: {
        start: startDate,
        end: endDate,
      },
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-xl border border-border bg-card shadow-2xl p-6 space-y-6 my-8">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-primary" />
            <h2 className="text-lg font-bold">Create Security Audit Campaign</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Campaign Name & Owner */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="campaign-name" className="font-semibold text-foreground">
                Campaign Name
              </label>
              <input
                id="campaign-name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="campaign-owner" className="font-semibold text-foreground">
                Lead Assessor Owner
              </label>
              <input
                id="campaign-owner"
                type="text"
                required
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          {/* Audit Window Dates */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="start-date" className="font-semibold text-foreground flex items-center gap-1.5">
                <Calendar size={13} className="text-muted-foreground" />
                Audit Window Start
              </label>
              <input
                id="start-date"
                type="date"
                required
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="end-date" className="font-semibold text-foreground flex items-center gap-1.5">
                <Calendar size={13} className="text-muted-foreground" />
                Audit Window End
              </label>
              <input
                id="end-date"
                type="date"
                required
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          {/* Scope Filter Expression */}
          <div className="space-y-2 pt-2 border-t">
            <div className="flex items-center justify-between">
              <label htmlFor="scope-expr" className="font-semibold text-foreground flex items-center gap-1.5">
                <Filter size={13} className="text-primary" />
                Target Scope Filter Expression
              </label>
              <span className="text-[11px] text-muted-foreground font-mono">
                Expression DSL
              </span>
            </div>

            <textarea
              id="scope-expr"
              rows={2}
              required
              value={expression}
              onChange={(e) => setExpression(e.target.value)}
              className="w-full px-3 py-2 rounded-md border border-input bg-background font-mono text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            />

            {/* Presets */}
            <div className="flex flex-wrap gap-1.5">
              {PRESET_EXPRESSIONS.map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setExpression(preset.expression)}
                  className="px-2 py-1 rounded bg-secondary hover:bg-secondary/80 text-[11px] text-muted-foreground hover:text-foreground transition-colors border border-border"
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Scope Resolution Preview */}
            <ScopeResolverSummary expression={expression} resolvedCount={412} totalInventoryCount={500} />
          </div>

          {/* Compliance Frameworks Selection (Multi-Framework) */}
          <div className="space-y-2 pt-2 border-t">
            <label className="font-semibold text-foreground block">
              Audited Standards & Control Frameworks (Multi-Select)
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {AVAILABLE_FRAMEWORKS.map((fw) => {
                const isSelected = selectedFrameworkIds.includes(fw.id);
                return (
                  <label
                    key={fw.id}
                    htmlFor={`framework-${fw.id}`}
                    className={`p-2.5 rounded-lg border cursor-pointer select-none transition-colors flex items-start gap-2.5 ${
                      isSelected
                        ? "border-primary bg-primary/5 text-foreground font-medium"
                        : "border-border hover:bg-secondary/40 text-muted-foreground"
                    }`}
                  >
                    <input
                      id={`framework-${fw.id}`}
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleFramework(fw.id)}
                      className="mt-0.5 rounded cursor-pointer"
                    />
                    <div>
                      <div className="text-xs font-semibold">{fw.name}</div>
                      <div className="text-[10px] text-muted-foreground font-mono mt-0.5 uppercase">
                        {fw.framework} · {fw.version || fw.revision || fw.release}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Modal Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-md border border-border text-xs font-medium hover:bg-secondary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={selectedFrameworkIds.length === 0}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              <Plus size={14} />
              <span>Initialize Campaign (Draft)</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

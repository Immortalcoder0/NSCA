import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, ShieldAlert, Network, ExternalLink, AlertTriangle } from "lucide-react";
import { AttackPathGraph } from "../components/AttackPathGraph";
import { AttackPathPayoffCard } from "../components/AttackPathPayoffCard";
import { AttackPathEstateSummaryBanner } from "../components/AttackPathEstateSummaryBanner";
import { SeverityBadge } from "../../shared/components/SeverityBadge";
import { EvidenceExcerpt } from "../../shared/components/EvidenceExcerpt";
import { useCampaignAttackPaths } from "../../shared/api/hooks/useAttackPaths";
import { DEFAULT_CAMPAIGN_ID } from "../../findings/hooks";
import type { AttackPathModel } from "../types";

const SAMPLE_ATTACK_PATHS: AttackPathModel[] = [
  {
    id: "AP-CORE-01",
    name: "Perimeter Ingress to Core Distribution Control Plane",
    entry_point: "EDGE-FW-01 (Internet Ingress)",
    target_asset: "CORE-SW-01 (Management Plane)",
    criticality: "CRITICAL",
    length: 3,
    nodes: [
      { id: "node-1", hostname: "EDGE-FW-01", ip: "198.51.100.1", role: "Perimeter Firewall", zone: "Internet / Ext", is_entry: true },
      { id: "node-2", hostname: "DIST-SW-02", ip: "10.40.1.2", role: "Distribution Switch", zone: "VLAN 400 Transit" },
      { id: "node-3", hostname: "CORE-SW-01", ip: "10.40.7.19", role: "Core Catalyst Switch", zone: "Core Mgmt Plane", is_target: true },
    ],
    links: [
      {
        id: "link-1-2",
        source: "node-1",
        target: "node-2",
        contributing_finding_id: "F-2026Q3-000413",
        control_id: "NSCA-MGMT-002",
        finding_title: "HTTP plaintext web interface permitted on management interface",
        severity: "CRITICAL",
        protocol: "HTTP",
        port: 80,
      },
      {
        id: "link-2-3",
        source: "node-2",
        target: "node-3",
        contributing_finding_id: "F-2026Q3-000412",
        control_id: "NSCA-MGMT-002",
        finding_title: "Plaintext management protocols enabled on VTY lines",
        severity: "CRITICAL",
        protocol: "Telnet",
        port: 23,
      },
    ],
    payoff: {
      critical_links_count: 2,
      recommended_break_finding_id: "F-2026Q3-000412",
      recommended_break_device: "CORE-SW-01",
      unreachable_findings_count: 4,
      cost_estimate: "1 command (transport input ssh)",
    },
  },
  {
    id: "AP-MGMT-03",
    name: "Partner VPN Ingress to Database Subnet",
    entry_point: "VPN-GW-01 (Partner Tunnel)",
    target_asset: "DB-RACK-SW-01 (Data Center)",
    criticality: "HIGH",
    length: 2,
    nodes: [
      { id: "node-p1", hostname: "VPN-GW-01", ip: "198.51.100.14", role: "VPN Gateway", zone: "Partner Ext", is_entry: true },
      { id: "node-p2", hostname: "CORE-SW-01", ip: "10.40.7.19", role: "Core Switch", zone: "Internal Backbone" },
      { id: "node-p3", hostname: "DB-RACK-SW-01", ip: "10.50.0.1", role: "DC Switch", zone: "PCI-DSS Data Center", is_target: true },
    ],
    links: [
      {
        id: "link-p1-p2",
        source: "node-p1",
        target: "node-p2",
        contributing_finding_id: "F-2026Q3-000518",
        control_id: "NSCA-NET-004",
        finding_title: "Permissive wildcard rule in partner access ACL",
        severity: "HIGH",
        protocol: "IP",
        port: 0,
      },
      {
        id: "link-p2-p3",
        source: "node-p2",
        target: "node-p3",
        contributing_finding_id: "F-2026Q3-000603",
        control_id: "NSCA-AUTH-001",
        finding_title: "Type 7 reversible credential in transit",
        severity: "HIGH",
        protocol: "TACACS+",
        port: 49,
      },
    ],
    payoff: {
      critical_links_count: 2,
      recommended_break_finding_id: "F-2026Q3-000518",
      recommended_break_device: "CORE-SW-01",
      unreachable_findings_count: 3,
      cost_estimate: "1 ACL modification",
    },
  },
];

export const AttackPathExplorerPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const campaignId = searchParams.get("campaign") || DEFAULT_CAMPAIGN_ID;

  // Real network call: `GET /campaigns/{id}/attack-paths`. **Verified live
  // against the M5 server (see this track's M5 report): it is still the
  // M0 stub** — the response below is identical regardless of
  // `campaignId`, and regardless of whether that campaign has ever been
  // assessed. The real per-campaign attack-path graph
  // (`nsca_engine.risk.attack_paths.compute_attack_paths`, wired into
  // `assess_campaign` since M5) is computed server-side but never
  // persisted or served — `services/assessment.py.run_assessment` caches
  // only the campaign's `Graph` (for dispute reachability), and discards
  // `CampaignAssessment.attack_paths` entirely. There is therefore no real
  // endpoint today that returns a graph-renderable multi-node attack path
  // for any campaign, seeded or not. `SAMPLE_ATTACK_PATHS` below (kept from
  // Phase 1) is used for the actual dagre rendering, and the raw stub
  // response is surfaced honestly in the panel beneath the path selector so
  // the mismatch is visible rather than silently absorbed.
  const { data: rawAttackPaths, isLoading: isLoadingReal, isError: isRealError } =
    useCampaignAttackPaths(campaignId);

  const [paths] = useState<AttackPathModel[]>(SAMPLE_ATTACK_PATHS);
  const [selectedPathId, setSelectedPathId] = useState<string>("AP-CORE-01");
  const [selectedLinkId, setSelectedLinkId] = useState<string | undefined>("link-2-3");

  const currentPath = paths.find((p) => p.id === selectedPathId) || paths[0];
  const selectedLink = currentPath.links.find((l) => l.id === selectedLinkId);

  const rawEntries = (rawAttackPaths?.attack_paths as
    | Array<{ id: string; severity: string; source: string; target: string; hops: number; findings: string[] }>
    | undefined) ?? [];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link to="/findings" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft size={13} />
          <span>Findings Workbench</span>
        </Link>
        <span>/</span>
        <span className="font-semibold text-foreground">Attack Path Explorer</span>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <Network size={22} />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Attack Path Explorer</h1>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Deterministic DAG visualization tracing how chained vulnerabilities enable adversary traversal across network zones.
          </p>
        </div>

        {/* Path Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-muted-foreground">Active Attack Path:</span>
          <select
            value={selectedPathId}
            onChange={(e) => {
              setSelectedPathId(e.target.value);
              setSelectedLinkId(undefined);
            }}
            className="px-3 py-1.5 rounded-md border border-input bg-background font-mono text-xs font-bold focus:outline-none focus:ring-1 focus:ring-ring cursor-pointer"
          >
            {paths.map((p) => (
              <option key={p.id} value={p.id}>
                {p.id}: {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Real API round trip, surfaced honestly — see the hook's docstring
          and the comment above: this endpoint is verified live to still be
          the M0 stub, so its content is shown for transparency rather than
          used to drive the graph below (which needs node/link detail no
          real endpoint returns yet). */}
      <div className="p-3.5 rounded-xl border border-amber-300/70 bg-amber-50/70 dark:bg-amber-950/30 dark:border-amber-800/60 text-[11px] text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
        <AlertTriangle size={14} className="shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <span className="font-bold block">
            Live GET /campaigns/{campaignId}/attack-paths
            {isLoadingReal ? " — loading…" : isRealError ? " — request failed" : ""}
          </span>
          {rawEntries.length > 0 ? (
            <span>
              Backend returned {rawEntries.length} entr{rawEntries.length === 1 ? "y" : "ies"}, e.g.{" "}
              <strong className="font-mono">
                {rawEntries[0].id} ({rawEntries[0].severity}) {rawEntries[0].source} → {rawEntries[0].target},{" "}
                {rawEntries[0].hops} hops
              </strong>{" "}
              — this is the server's fixed M0 example, unrelated to campaign {campaignId}'s actual (real,
              two-device) estate. The graph below renders a local reference fixture instead, since no endpoint
              yet returns per-link node/severity detail for a real campaign. Flagged for Backend Track B.
            </span>
          ) : (
            <span>No entries returned; graph below renders a local reference fixture.</span>
          )}
        </div>
      </div>

      {/* Estate-Level Rollup — SystemicFindingBanner's sibling summary for
          attack paths (12-ux-specification.md §4's "3 attack paths reach
          the core management plane" banner). Shown first per U4 ("lead
          with action") since it answers the estate-wide question before
          the payoff card answers the per-path question. */}
      <AttackPathEstateSummaryBanner paths={paths} />

      {/* Top Payoff Callout Card */}
      <AttackPathPayoffCard path={currentPath} />

      {/* DAG Graph Canvas */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-foreground flex items-center gap-1.5">
            <ShieldAlert size={14} className="text-red-500" />
            <span>Deterministic DAG Chain Layout (Dagre Render)</span>
          </span>
          <span className="text-muted-foreground text-[11px]">
            Click any edge or finding badge to inspect vulnerability details
          </span>
        </div>

        <AttackPathGraph
          path={currentPath}
          selectedLinkId={selectedLinkId}
          onSelectLink={(id) => setSelectedLinkId(id)}
        />
      </div>

      {/* Selected Link Inspector — per-link evidence reuses EvidenceExcerpt's
          counterexample sub-component (09-findings-lifecycle.md §3.2's
          packet + rule-chain shape), the same renderer used by the dispute
          screen's REFUTED outcome, rather than a third bespoke
          implementation of the same "no single line is wrong" evidence
          class. */}
      {selectedLink && (() => {
        const sourceNode = currentPath.nodes.find((n) => n.id === selectedLink.source);
        const targetNode = currentPath.nodes.find((n) => n.id === selectedLink.target);
        return (
          <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs">
            <div className="flex items-center justify-between border-b pb-2">
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-foreground">{selectedLink.control_id}</span>
                <span className="text-muted-foreground font-mono text-[11px]">({selectedLink.contributing_finding_id})</span>
                <SeverityBadge severity={selectedLink.severity} size="sm" />
              </div>

              <Link
                to={`/findings/${selectedLink.contributing_finding_id}`}
                className="flex items-center gap-1 text-primary hover:underline font-semibold text-xs"
              >
                <span>View Full Finding Detail</span>
                <ExternalLink size={12} />
              </Link>
            </div>

            <p className="font-semibold text-foreground text-sm">{selectedLink.finding_title}</p>

            <EvidenceExcerpt
              content={`# Emergent finding — no single configuration line is non-compliant.\n# The violation is the reachable combination traced below.`}
              filename={`${selectedLink.contributing_finding_id} — graph-derived evidence`}
              counterexample={{
                packet: `${selectedLink.protocol || "TCP"}/${selectedLink.port ?? "-"}`,
                source: sourceNode?.hostname,
                destination: targetNode?.hostname,
                ruleChain: [
                  { device: sourceNode?.hostname || selectedLink.source, rule: selectedLink.control_id, action: "permit" },
                  { device: targetNode?.hostname || selectedLink.target, rule: selectedLink.finding_title, action: "permit" },
                ],
              }}
            />
          </div>
        );
      })()}
    </div>
  );
};

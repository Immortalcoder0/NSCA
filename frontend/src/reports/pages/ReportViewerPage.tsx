import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Cpu,
  Lock,
  Server,
  FileText,
  CheckCircle2,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { UnassessedSectionBox } from "../components/UnassessedSectionBox";
import { ReportVerifyModal } from "../components/ReportVerifyModal";
import { ExportFormatDropdown } from "../components/ExportFormatDropdown";
import { EvidenceExcerpt } from "../../shared/components/EvidenceExcerpt";
import { useReportDocument, useReportManifest, useReportMeta } from "../../shared/api/hooks";
import type { ReportFindingJson } from "../../shared/api/hooks/useReports";

const SECTIONS = [
  { id: "sec-1", title: "1. Identification & Pinning" },
  { id: "sec-2", title: "2. Executive Summary" },
  { id: "sec-3", title: "3. Detailed Findings" },
  { id: "sec-4", title: "4. Emergent Clusters" },
  { id: "sec-5", title: "5. Remediation Playbook" },
  { id: "sec-6", title: "6. Unassessed Scope" },
  { id: "sec-7", title: "7. Assessor Notes" },
  { id: "sec-8", title: "8. Appendix" },
];

function ratioPct(num: number, den: number): number {
  return den > 0 ? Math.round((num / den) * 100) : 0;
}

const VERDICT_STYLES: Record<string, string> = {
  FAIL: "bg-red-100 dark:bg-red-950 text-red-800 dark:text-red-300",
  PASS: "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300",
  PASS_PARTIAL: "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300",
  NOT_APPLICABLE: "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300",
};

const FindingBlock: React.FC<{ f: ReportFindingJson; hostname: string }> = ({ f, hostname }) => {
  const lines = f.evidence.lines;
  const content = lines.map((l) => l.text).join("\n");
  const startLine = lines.length > 0 ? lines[0].number : 1;
  const highlightLines = lines.filter((l) => l.highlighted).map((l) => l.number);

  return (
    <div className="p-4 rounded-lg border bg-background space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-foreground">{f.control_id}</span>
          <span className={`px-2 py-0.5 rounded font-mono font-bold text-[10px] ${VERDICT_STYLES[f.verdict] ?? "bg-secondary text-foreground"}`}>
            {f.verdict} · {f.severity.effective.toUpperCase()}
          </span>
          <span className="text-muted-foreground font-mono text-[11px] flex items-center gap-1">
            <Server size={12} />
            {hostname}
          </span>
          {f.rule_status !== "ratified" && (
            <span className="px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300">
              PROVISIONAL RULE
            </span>
          )}
        </div>
      </div>

      <h4 className="font-semibold text-foreground text-sm">{f.title}</h4>

      {lines.length > 0 ? (
        <EvidenceExcerpt content={content} startLineNumber={startLine} highlightLines={highlightLines} filename={f.evidence.artifact ?? undefined} />
      ) : (
        <p className="text-[11px] text-muted-foreground italic">No evidence lines captured for this finding.</p>
      )}

      {f.facts.length > 0 && (
        <p className="text-[11px] text-muted-foreground">Facts: {f.facts.join(" · ")}</p>
      )}
    </div>
  );
};

export const ReportViewerPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [isVerifyModalOpen, setIsVerifyModalOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("sec-1");

  const metaQuery = useReportMeta(id);
  const docQuery = useReportDocument(id);
  const manifestQuery = useReportManifest(id);

  const scrollToSection = (secId: string) => {
    setActiveSection(secId);
    const el = document.getElementById(secId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  if (!id) {
    return (
      <div className="p-6 rounded-xl border border-border/80 bg-card text-xs text-muted-foreground text-center max-w-2xl mx-auto">
        No report id given. Open a report from the{" "}
        <Link to="/reports" className="text-primary hover:underline">
          Reports Library
        </Link>
        .
      </div>
    );
  }

  if (docQuery.isLoading || metaQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground p-10 justify-center">
        <Loader2 size={16} className="animate-spin" />
        <span>Loading report {id}…</span>
      </div>
    );
  }

  if (docQuery.isError || !docQuery.data) {
    return (
      <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2 max-w-2xl mx-auto">
        <AlertTriangle size={15} className="shrink-0" />
        <span>
          Failed to load report {id}:{" "}
          {docQuery.error instanceof Error ? docQuery.error.message : "unknown error"}
        </span>
      </div>
    );
  }

  const doc = docQuery.data;
  const meta = metaQuery.data;
  const scores = doc.scores;
  const kb = doc.knowledge_base;

  const narrative =
    `Compliance assessment for ${doc.device.hostname}: ${scores.pass_count} pass, ${scores.fail_count} fail, ` +
    `${scores.unknown_count} unknown, ${scores.not_applicable_count} not applicable, out of ` +
    `${scores.coverage.denominator} applicable controls.`;

  return (
    <div className="space-y-5 pb-12">
      {/* Top Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/70 pb-3.5">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Link to="/reports" className="hover:text-foreground flex items-center gap-1">
            <ArrowLeft size={13} />
            <span>Reports Library</span>
          </Link>
          <span>/</span>
          <span className="font-mono text-foreground font-bold">{id}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsVerifyModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 text-foreground text-xs font-semibold transition-colors"
          >
            <Cpu size={14} className="text-primary" />
            <span>Verify Cryptographic Digest</span>
          </button>
          <ExportFormatDropdown reportId={id} availableFormats={meta?.formats_available} />
        </div>
      </div>

      {/* 2-Column Responsive Document Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Sticky Table of Contents Navigator */}
        <div className="lg:col-span-3 lg:sticky lg:top-20 space-y-3">
          <div className="p-4 rounded-xl border border-border/80 bg-card space-y-2.5 text-xs">
            <span className="font-bold text-muted-foreground uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <FileText size={13} />
              Document Sections
            </span>
            <nav className="flex flex-col gap-1">
              {SECTIONS.map((sec) => (
                <button
                  key={sec.id}
                  onClick={() => scrollToSection(sec.id)}
                  className={`text-left px-2.5 py-1.5 rounded-md transition-colors font-medium flex items-center justify-between ${
                    activeSection === sec.id
                      ? "bg-secondary text-foreground font-bold"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                  }`}
                >
                  <span>{sec.title}</span>
                  <CheckCircle2 size={12} className="opacity-40" />
                </button>
              ))}
            </nav>
          </div>

          <div className="p-4 rounded-xl border border-border/80 bg-card space-y-1.5 text-xs">
            <span className="font-bold text-foreground block">SHA256 Hash Digest</span>
            <span className="font-mono text-[10px] text-muted-foreground break-all block">
              {doc.report_hash ?? meta?.hash ?? "—"}
            </span>
          </div>
        </div>

        {/* Right Main Document Paper View */}
        <div className="lg:col-span-9 space-y-6">
          {/* SECTION 1: Cover & Identification */}
          <div id="sec-1" className="p-6 rounded-xl border border-border bg-card space-y-4 text-xs scroll-mt-20">
            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <span className="font-mono text-muted-foreground uppercase font-bold text-[10px]">
                SECTION 1 · FORMAL AUDIT IDENTIFICATION & INTEGRITY PIN
              </span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-mono font-bold text-[10px] flex items-center gap-1">
                <Lock size={10} />
                {doc.mode.toUpperCase()}
              </span>
            </div>

            <h1 className="text-xl font-black tracking-tight text-foreground">
              {doc.campaign.name} — {doc.device.hostname}
            </h1>
            <p className="text-muted-foreground">
              {doc.device.model ?? "Model NOT DETERMINED"} · {doc.device.os_version ?? "OS version NOT DETERMINED"}
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-3 border-t border-border/60 text-xs">
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Assessor</span>
                <span className="font-bold text-foreground">{doc.campaign.assessor}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Generated At</span>
                <span className="font-bold text-foreground">{new Date(doc.generated_at).toLocaleString()}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Campaign ID</span>
                <span className="font-mono font-bold text-foreground">{meta?.campaign_id ?? "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Engine Pin</span>
                <span className="font-mono text-muted-foreground text-[10px]">{kb.engine}</span>
              </div>
            </div>
          </div>

          {/* SECTION 2: Executive Summary */}
          <div id="sec-2" className="p-6 rounded-xl border border-border bg-card space-y-4 text-xs scroll-mt-20">
            <span className="font-mono text-muted-foreground uppercase font-bold text-[10px]">
              SECTION 2 · EXECUTIVE SUMMARY & POSTURE RATIOS
            </span>
            <p className="text-foreground leading-relaxed text-sm">{narrative}</p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 border-t border-border/60 text-center">
              <div className="p-3 rounded-lg bg-secondary/50 border border-border/40">
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Compliance</span>
                <span className="text-2xl font-black text-foreground">
                  {ratioPct(scores.compliance.numerator, scores.compliance.denominator)}%
                </span>
              </div>
              <div className="p-3 rounded-lg bg-secondary/50 border border-border/40">
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Coverage</span>
                <span className="text-2xl font-black text-foreground">
                  {ratioPct(scores.coverage.numerator, scores.coverage.denominator)}%
                </span>
              </div>
              <div className="p-3 rounded-lg bg-secondary/50 border border-border/40">
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Meaningful</span>
                <span className="text-2xl font-black text-foreground">
                  {ratioPct(scores.meaningful.numerator, scores.meaningful.denominator)}%
                </span>
              </div>
              <div className="p-3 rounded-lg bg-secondary/50 border border-border/40">
                <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Security Posture</span>
                <span className="text-2xl font-black text-foreground">
                  {ratioPct(scores.security_posture.numerator, scores.security_posture.denominator)}%
                </span>
              </div>
            </div>
          </div>

          {/* SECTION 3: Findings */}
          <div id="sec-3" className="p-6 rounded-xl border border-border bg-card space-y-4 text-xs scroll-mt-20">
            <span className="font-mono text-muted-foreground uppercase font-bold text-[10px]">
              SECTION 3 · DETAILED AUDIT FINDINGS WITH CONFIGURATION PROVENANCE
            </span>
            {doc.findings.length === 0 && <p className="text-muted-foreground">No findings recorded.</p>}
            {doc.findings.map((f) => (
              <FindingBlock key={f.finding_id} f={f} hostname={doc.device.hostname} />
            ))}
          </div>

          {/* SECTION 4: Emergent Findings */}
          <div id="sec-4" className="p-6 rounded-xl border border-border bg-card space-y-3 text-xs scroll-mt-20">
            <span className="font-mono text-muted-foreground uppercase font-bold text-[10px]">
              SECTION 4 · EMERGENT & SYSTEMIC FINDING CLUSTERS
            </span>
            {doc.emergent_findings.length === 0 ? (
              <p className="text-muted-foreground">No emergent (multi-device) findings for this device.</p>
            ) : (
              doc.emergent_findings.map((ef) => <FindingBlock key={ef.finding_id} f={ef} hostname={doc.device.hostname} />)
            )}
          </div>

          {/* SECTION 5: Remediation Playbook */}
          <div id="sec-5" className="p-6 rounded-xl border border-border bg-card space-y-3 text-xs scroll-mt-20">
            <span className="font-mono text-muted-foreground uppercase font-bold text-[10px]">
              SECTION 5 · SAFETY-CLASSIFIED REMEDIATION PLAYBOOK
            </span>
            {/* reporting/exports.py:to_json (the only machine-readable format
                this viewer can fetch) does not include the remediation
                playbook — it is only rendered into the PDF/DOCX document
                tree (reporting/document_model.py:_build_remediation_section).
                Flagged rather than fabricated. */}
            <p className="text-muted-foreground italic">
              Not available via this report's JSON export — the remediation playbook is only rendered into the
              PDF/DOCX formats today, not the machine-readable JSON this viewer reads from. Download the PDF or
              DOCX above to see it.
            </p>
          </div>

          {/* SECTION 6: Unassessed (Mandatory Prominence) */}
          <div id="sec-6" className="scroll-mt-20">
            <UnassessedSectionBox
              determinedPercentage={ratioPct(scores.coverage.numerator, scores.coverage.denominator)}
              undeterminedPercentage={100 - ratioPct(scores.coverage.numerator, scores.coverage.denominator)}
              items={doc.unassessed.flatMap((u) =>
                u.control_ids.map((cid) => ({ control_id: cid, title: cid, reason: u.cause }))
              )}
            />
          </div>

          {/* SECTION 7 & 8: Notes and Appendix */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div id="sec-7" className="p-6 rounded-xl border border-border bg-card space-y-2 text-xs scroll-mt-20">
              <span className="font-mono text-muted-foreground uppercase font-bold text-[10px]">
                SECTION 7 · LEAD ASSESSOR NOTES
              </span>
              {/* Same real gap as Section 5 — to_json omits assessor_notes. */}
              <p className="text-muted-foreground italic">
                No assessor notes are exposed via this report's JSON export.
              </p>
            </div>

            <div id="sec-8" className="p-6 rounded-xl border border-border bg-card space-y-2 text-xs scroll-mt-20">
              <span className="font-mono text-muted-foreground uppercase font-bold text-[10px]">
                SECTION 8 · APPENDIX & CRYPTOGRAPHIC PINNING
              </span>
              <p className="text-muted-foreground leading-relaxed">
                Engine {kb.engine} · Rulepack {kb.rulepack.id}@{kb.rulepack.version} ({kb.rulepack.trust_tier}) ·
                Control pack {kb.control_pack.id}@{kb.control_pack.version} · Schema {kb.schema_registry}
              </p>
              {manifestQuery.data && (
                <p className="text-muted-foreground leading-relaxed italic">{manifestQuery.data.statement}</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Verify Modal */}
      <ReportVerifyModal isOpen={isVerifyModalOpen} reportId={id} onClose={() => setIsVerifyModalOpen(false)} />
    </div>
  );
};

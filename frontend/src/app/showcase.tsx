import React, { useState } from "react";
import { VerdictBadge } from "../shared/components/VerdictBadge";
import { SeverityBadge } from "../shared/components/SeverityBadge";
import { TrustTierBadge } from "../shared/components/TrustTierBadge";
import { CoverageBar } from "../shared/components/CoverageBar";
import {
  VERDICT_TOKENS,
  SEVERITY_TOKENS,
  TRUST_TIER_TOKENS,
  type VerdictType,
  type SeverityType,
  type TrustTierType,
} from "../shared/theme/tokens";

export const Showcase: React.FC = () => {
  const [monochromeMode, setMonochromeMode] = useState(false);

  const verdicts: VerdictType[] = [
    "PASS",
    "PASS_PARTIAL",
    "PASS_VACUOUS",
    "FAIL",
    "UNKNOWN",
    "NOT_APPLICABLE",
  ];

  const severities: SeverityType[] = [
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
    "INFORMATIONAL",
  ];

  const trustTiers: TrustTierType[] = [
    "CERTIFIED",
    "COMMUNITY",
    "SYNTHESIZED",
    "UNVERIFIED",
  ];

  return (
    <div className="space-y-10 max-w-5xl mx-auto">
      <div className="flex items-center justify-between border-b pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">NSCA Visual Language & Token Showcase</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Standard visual vocabulary covering verdicts (U3), severity (U7), and trust tiers (U10).
          </p>
        </div>
        <button
          onClick={() => setMonochromeMode(!monochromeMode)}
          className="px-3 py-1.5 rounded border text-xs font-semibold hover:bg-secondary transition-colors"
        >
          {monochromeMode ? "Disable Monochrome Simulation" : "Simulate Monochrome Printout"}
        </button>
      </div>

      {/* 1. Verdict Treatments (UX Spec §10.1 / Principle U3) */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span>Verdict Visual States (§10.1)</span>
            <span className="text-xs font-normal text-muted-foreground">
              (Guarantee U3: UNKNOWN is never styled like PASS)
            </span>
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {verdicts.map((v) => {
            const token = VERDICT_TOKENS[v];
            return (
              <div
                key={v}
                className="p-4 rounded-lg border bg-card text-card-foreground flex flex-col justify-between space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-muted-foreground">{token.id}</span>
                  <VerdictBadge verdict={v} size="md" monochromePrint={monochromeMode} />
                </div>
                <p className="text-xs text-muted-foreground">{token.description}</p>
                <div className="text-[11px] font-mono text-muted-foreground/80 flex items-center justify-between border-t pt-2">
                  <span>Glyph: {token.glyph}</span>
                  <span>Print: {token.monochrome.glyphSymbol}</span>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 2. Severity Treatments (UX Spec §10.2 / Principle U7) */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <span>Severity Visual States (§10.2)</span>
            <span className="text-xs font-normal text-muted-foreground">
              (Guarantee U7: Severity is never colour alone; glyph paired)
            </span>
          </h2>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
          {severities.map((s) => {
            const token = SEVERITY_TOKENS[s];
            return (
              <div
                key={s}
                className="p-4 rounded-lg border bg-card text-card-foreground flex flex-col items-center justify-center space-y-2 text-center"
              >
                <SeverityBadge severity={s} size="md" monochromePrint={monochromeMode} />
                <span className="text-xs font-mono text-muted-foreground">Weight: {token.weight}</span>
                <span className="text-[11px] text-muted-foreground font-mono">Glyph: {token.glyphSymbol}</span>
              </div>
            );
          })}
        </div>
      </section>

      {/* 3. Rulepack Trust Tiers (§10.3) */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Rulepack Trust Indicators (§10.3)</h2>
          <p className="text-xs text-muted-foreground">
            Findings derived from non-certified or synthesized rulepacks carry persistent markers.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {trustTiers.map((t) => {
            const token = TRUST_TIER_TOKENS[t];
            return (
              <div key={t} className="p-4 rounded-lg border bg-card space-y-2">
                <div className="flex items-center justify-between">
                  <TrustTierBadge tier={t} size="sm" />
                </div>
                <p className="text-xs text-muted-foreground">{token.description}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* 4. Coverage Visualisation */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Stacked Coverage Bar</h2>
          <p className="text-xs text-muted-foreground">
            Multi-verdict aggregation bar for campaigns and estate compliance.
          </p>
        </div>

        <div className="p-6 rounded-lg border bg-card space-y-6">
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              Representative Estate (389 devices)
            </h3>
            <CoverageBar
              breakdown={{
                pass: 245,
                passPartial: 32,
                passVacuous: 18,
                fail: 64,
                unknown: 21,
                notApplicable: 9,
              }}
              size="lg"
            />
          </div>

          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              High Unknown Ratio (Missing artifacts)
            </h3>
            <CoverageBar
              breakdown={{
                pass: 50,
                fail: 10,
                unknown: 140,
              }}
              size="md"
            />
          </div>
        </div>
      </section>
    </div>
  );
};

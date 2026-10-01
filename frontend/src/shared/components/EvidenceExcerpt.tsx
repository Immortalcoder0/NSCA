import React, { useState } from "react";
import { Copy, Check, ShieldAlert, ArrowRight, FileCode } from "lucide-react";
import { cn } from "../lib/utils";

export interface CounterexampleTrace {
  packet: string;
  source?: string;
  destination?: string;
  ruleChain: Array<{
    device: string;
    rule: string;
    action: "permit" | "deny" | string;
    line?: number;
  }>;
}

export interface EvidenceExcerptProps {
  content: string;
  startLineNumber?: number;
  highlightLines?: number[] | { start: number; end: number };
  maskedPatterns?: string[];
  filename?: string;
  counterexample?: CounterexampleTrace;
  maxHeight?: string;
  className?: string;
}

export const EvidenceExcerpt: React.FC<EvidenceExcerptProps> = ({
  content,
  startLineNumber = 1,
  highlightLines,
  maskedPatterns = ["password", "secret", "community", "key", "hash"],
  filename,
  counterexample,
  maxHeight = "max-h-96",
  className,
}) => {
  const [copied, setCopied] = useState(false);

  const lines = content.split(/\r?\n/);

  const isLineHighlighted = (lineNum: number): boolean => {
    if (!highlightLines) return false;
    if (Array.isArray(highlightLines)) {
      return highlightLines.includes(lineNum);
    }
    return lineNum >= highlightLines.start && lineNum <= highlightLines.end;
  };

  // Plain-text secret mask renderer (preserves structure without syntax parsing)
  const renderLineContent = (text: string): React.ReactNode => {
    let maskedText = text;
    let hasMask = false;

    // Mask sensitive assignments matching pattern list
    const patternGroup = maskedPatterns.join("|");
    const secretRegex = new RegExp(
      `((?:${patternGroup}|key-string|preshared-key|auth-key)\\s+(?:\\d+\\s+)?)([^\\s\\r\\n]+)`,
      "gi"
    );

    if (secretRegex.test(text)) {
      hasMask = true;
      maskedText = text.replace(
        secretRegex,
        `$1<MASK>***SECRET_MASKED***</MASK>`
      );
    }

    if (hasMask && maskedText.includes("<MASK>")) {
      const parts = maskedText.split(/(<MASK>.*?<\/MASK>)/g);
      return (
        <span>
          {parts.map((p, idx) => {
            if (p.startsWith("<MASK>") && p.endsWith("<\/MASK>")) {
              const cleanMask = p.replace(/<\/?MASK>/g, "");
              return (
                <span
                  key={idx}
                  title="Secret redacted per security policy (FR-ADM-005)"
                  className="bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1.5 py-0.5 rounded font-mono font-bold text-[11px]"
                >
                  {cleanMask}
                </span>
              );
            }
            return <span key={idx}>{p}</span>;
          })}
        </span>
      );
    }

    // Subtle syntax tinting for network configs
    const trimmed = text.trim();
    if (trimmed.startsWith("!") || trimmed.startsWith("#")) {
      return <span className="text-slate-500 italic">{text}</span>;
    }
    if (trimmed.startsWith("set ") || trimmed.startsWith("interface ") || trimmed.startsWith("router ") || trimmed.startsWith("line ")) {
      return <span className="text-sky-300 font-medium">{text}</span>;
    }

    return <span>{text}</span>;
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        "rounded-xl border border-slate-800/90 bg-[#0d1117] text-slate-100 font-mono text-xs overflow-hidden shadow-lg transition-all",
        className
      )}
    >
      {/* Modern IDE Header bar with Window Dots */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#161b22] border-b border-slate-800 text-slate-400 select-none">
        <div className="flex items-center gap-3">
          {/* macOS window controls */}
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
          </div>

          <div className="flex items-center gap-1.5 ml-1">
            <FileCode size={13} className="text-indigo-400" />
            <span className="font-semibold text-slate-200 font-sans text-xs">
              {filename || "Configuration Excerpt"}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-400">
              {lines.length} {lines.length === 1 ? "line" : "lines"}
            </span>
          </div>
        </div>

        <button
          onClick={handleCopy}
          aria-label="Copy configuration snippet"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-sans text-slate-300 hover:text-white bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 transition-all shadow-sm active:scale-95"
        >
          {copied ? (
            <>
              <Check size={13} className="text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied</span>
            </>
          ) : (
            <>
              <Copy size={13} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Counterexample Path Section (if present) */}
      {counterexample && (
        <div className="p-3.5 bg-red-950/40 border-b border-red-900/50 text-red-200 space-y-2">
          <div className="flex items-center gap-1.5 font-bold text-red-300 text-xs">
            <ShieldAlert size={14} />
            <span>Counterexample Verification Path</span>
          </div>
          <div className="text-[11px] text-red-300">
            Packet: <span className="font-bold text-red-100">{counterexample.packet}</span>
          </div>
          <div className="space-y-1">
            {counterexample.ruleChain.map((step, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 text-[11px] bg-red-950/70 p-1.5 rounded-md border border-red-900/40 shadow-sm"
              >
                <span className="font-bold text-slate-300">{step.device}</span>
                <ArrowRight size={10} className="text-red-400 shrink-0" />
                <span className="text-slate-200">{step.rule}</span>
                <span
                  className={cn(
                    "ml-auto px-2 py-0.5 rounded font-bold uppercase text-[10px]",
                    step.action === "permit"
                      ? "bg-red-800/80 text-red-100 border border-red-700"
                      : "bg-slate-800 text-slate-300"
                  )}
                >
                  {step.action}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Code / Configuration Lines */}
      <div
        className={cn(
          "overflow-auto p-3 divide-y divide-transparent select-text font-mono text-[11px] leading-relaxed",
          maxHeight
        )}
      >
        {lines.map((lineText, idx) => {
          const currentLineNum = startLineNumber + idx;
          const isHighlighted = isLineHighlighted(currentLineNum);

          return (
            <div
              key={idx}
              className={cn(
                "flex items-start gap-4 px-2.5 py-0.5 rounded-md transition-colors",
                isHighlighted
                  ? "bg-amber-500/15 text-amber-200 border-l-2 border-amber-400 font-semibold shadow-inner"
                  : "hover:bg-slate-900/60 text-slate-300"
              )}
            >
              <span
                className={cn(
                  "w-8 shrink-0 text-right select-none text-[10px]",
                  isHighlighted ? "text-amber-400 font-bold" : "text-slate-600"
                )}
                aria-hidden="true"
              >
                {currentLineNum}
              </span>
              <span className="flex-1 whitespace-pre-wrap break-all">
                {renderLineContent(lineText)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

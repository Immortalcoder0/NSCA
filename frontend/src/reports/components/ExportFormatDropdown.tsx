import React, { useState } from "react";
import { Download, ChevronDown, FileText, Check, Loader2, AlertTriangle } from "lucide-react";
import type { ReportFormatType } from "../types";
import { downloadReportFile } from "../../shared/api/hooks";

interface ExportFormatDropdownProps {
  reportId?: string;
  /** Real formats this report actually has stored (`meta.formats_available`
   * — WeasyPrint/python-docx aren't always installed, so pdf/docx aren't
   * guaranteed). Undefined means "unknown yet", in which case every format
   * is offered and a 404 just surfaces inline. */
  availableFormats?: string[];
  className?: string;
}

export const ExportFormatDropdown: React.FC<ExportFormatDropdownProps> = ({
  reportId,
  availableFormats,
  className,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [pendingFormat, setPendingFormat] = useState<string | null>(null);
  const [downloadedFormat, setDownloadedFormat] = useState<string | null>(null);
  const [errorFormat, setErrorFormat] = useState<string | null>(null);

  const formats: Array<{ id: ReportFormatType; label: string; ext: string; desc: string }> = [
    { id: "pdf", label: "Executive & Technical PDF", ext: ".pdf", desc: "Sealed monochrome-optimized report" },
    { id: "docx", label: "Microsoft Word (DOCX)", ext: ".docx", desc: "Editable audit documentation" },
    { id: "oscal", label: "NIST OSCAL Assessment Results", ext: ".json", desc: "Machine-readable compliance artifact" },
    { id: "json", label: "Raw JSON Findings Ledger", ext: ".json", desc: "Full AST evaluation export" },
    { id: "csv", label: "Tabular Findings CSV", ext: ".csv", desc: "Spreadsheet inventory export" },
  ];

  const handleDownload = async (format: ReportFormatType) => {
    if (!reportId) return;
    setErrorFormat(null);
    setPendingFormat(format);
    setIsOpen(false);
    try {
      await downloadReportFile(reportId, format, `${reportId}${formats.find((f) => f.id === format)?.ext ?? ""}`);
      setDownloadedFormat(format);
      setTimeout(() => setDownloadedFormat(null), 3000);
    } catch {
      setErrorFormat(format);
    } finally {
      setPendingFormat(null);
    }
  };

  return (
    <div className={`relative inline-block text-left ${className || ""}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={!reportId}
        className="flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold hover:opacity-90 disabled:opacity-50 transition-opacity shadow-sm"
      >
        {pendingFormat ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
        <span>Export Report</span>
        <ChevronDown size={14} />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 rounded-xl border border-border bg-card shadow-2xl p-1.5 z-40 space-y-1 text-xs animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2 py-1 text-[10px] font-mono uppercase text-muted-foreground font-bold">
            Available Export Formats
          </div>

          {formats.map((f) => {
            const isKnownUnavailable = availableFormats && !availableFormats.includes(f.id);
            return (
              <button
                key={f.id}
                onClick={() => handleDownload(f.id)}
                disabled={isKnownUnavailable}
                className="w-full text-left p-2 rounded-lg hover:bg-secondary disabled:opacity-40 disabled:hover:bg-transparent flex items-start gap-2.5 transition-colors"
              >
                <FileText size={15} className="text-primary shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <div className="font-semibold text-foreground">{f.label}</div>
                  <div className="text-[10px] text-muted-foreground">
                    {isKnownUnavailable ? "Not rendered for this report" : f.desc}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {downloadedFormat && (
        <span className="text-[11px] text-emerald-600 font-medium ml-2 inline-flex items-center gap-1">
          <Check size={12} />
          {downloadedFormat.toUpperCase()} downloaded
        </span>
      )}
      {errorFormat && (
        <span className="text-[11px] text-red-600 font-medium ml-2 inline-flex items-center gap-1">
          <AlertTriangle size={12} />
          {errorFormat.toUpperCase()} download failed
        </span>
      )}
    </div>
  );
};

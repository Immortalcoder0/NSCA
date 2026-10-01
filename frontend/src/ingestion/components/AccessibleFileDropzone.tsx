import React, { useState, useRef } from "react";
import { UploadCloud, File, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "../../shared/lib/utils";
import type { StagedFile } from "../../shared/components/FileDropzone";

export type { StagedFile };

export interface AccessibleFileDropzoneProps {
  onFilesSelected?: (files: StagedFile[]) => void;
  acceptedExtensions?: string[];
  maxFiles?: number;
  className?: string;
}

const DEFAULT_EXTENSIONS = [".txt", ".cfg", ".conf", ".xml", ".json", ".zip", ".tar.gz", ".tar", ".gz", ".log"];

/**
 * Local, keyboard-accessible drop zone for the ingestion upload flow.
 *
 * shared/components/FileDropzone.tsx (Track 0, frozen) renders its
 * drop target as a plain `<div onClick>` with no `tabIndex`/`onKeyDown`,
 * and its file `<input>` is `className="hidden"` (display:none), which
 * removes it from the tab order entirely -- a keyboard-only user cannot
 * reach or activate it at all. That breaks the "full keyboard navigation
 * through the upload flow" testing obligation in
 * plans/frontend-01-ingestion-campaigns-estate.md §4 (NFR-USE-008).
 *
 * Since shared/ is frozen for this track, this component reproduces
 * FileDropzone's props/behavior (StagedFile shape, onFilesSelected
 * callback) as a drop-in, but makes the drop target a real focusable
 * `role="button"` that responds to Enter/Space, and keeps the file
 * `<input>` reachable (visually hidden via sr-only clipping instead of
 * `display:none`, and still triggerable via the visible button).
 */
export const AccessibleFileDropzone: React.FC<AccessibleFileDropzoneProps> = ({
  onFilesSelected,
  acceptedExtensions = DEFAULT_EXTENSIONS,
  maxFiles = 500,
  className,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;

    const newFiles: StagedFile[] = Array.from(fileList).map((f) => ({
      id: `${f.name}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      file: f,
      name: f.name,
      size: f.size,
      type: f.type || "text/plain",
      status: "staged",
    }));

    const updated = [...stagedFiles, ...newFiles].slice(0, maxFiles);
    setStagedFiles(updated);
    onFilesSelected?.(updated);
  };

  const handleRemove = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = stagedFiles.filter((f) => f.id !== id);
    setStagedFiles(updated);
    onFilesSelected?.(updated);
  };

  const openPicker = () => inputRef.current?.click();

  // input.click() dispatches a real click event that bubbles up to this
  // div (the input is its descendant), which would otherwise re-enter
  // this handler and open the picker a second time for one interaction.
  // Ignore clicks whose target is the input itself -- those only happen
  // as a result of our own programmatic trigger, never a direct user
  // click (the input is visually hidden).
  const handleZoneClick = (e: React.MouseEvent) => {
    if (e.target === inputRef.current) return;
    openPicker();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
      e.preventDefault();
      openPicker();
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className={cn("space-y-4", className)}>
      <div
        role="button"
        tabIndex={0}
        aria-label="Drop configuration files here, or activate to browse for files"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleZoneClick}
        onKeyDown={handleKeyDown}
        className={cn(
          "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors flex flex-col items-center justify-center gap-3",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
          isDragOver
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-secondary/30 bg-card/60"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={acceptedExtensions.join(",")}
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
          aria-label="Upload configuration files"
          tabIndex={-1}
        />

        <div className="p-3 rounded-full bg-primary/10 text-primary">
          <UploadCloud size={28} />
        </div>

        <div>
          <p className="text-sm font-semibold">
            Drop configuration files or archives here, or <span className="text-primary underline">browse</span>
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Text · XML · JSON · .zip · .tar.gz · show-tech exports (up to {maxFiles} files)
          </p>
          <p className="text-[11px] text-muted-foreground mt-1">
            Keyboard: Tab to this area, then press Enter or Space to open the file browser.
          </p>
        </div>
      </div>

      {/* Staged File List */}
      {stagedFiles.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-3 space-y-2 max-h-60 overflow-y-auto">
          <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground pb-1 border-b">
            <span>Staged Artifacts ({stagedFiles.length})</span>
            <span>{formatFileSize(stagedFiles.reduce((acc, f) => acc + f.size, 0))}</span>
          </div>

          <div className="space-y-1.5">
            {stagedFiles.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-2 rounded bg-secondary/40 text-xs hover:bg-secondary/70 transition-colors"
              >
                <div className="flex items-center gap-2 truncate pr-2">
                  <File size={14} className="text-muted-foreground shrink-0" />
                  <span className="font-mono truncate">{item.name}</span>
                  <span className="text-muted-foreground text-[10px]">({formatFileSize(item.size)})</span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {item.status === "success" && <CheckCircle2 size={14} className="text-emerald-500" />}
                  {item.status === "error" && <AlertCircle size={14} className="text-red-500" />}
                  <button
                    onClick={(e) => handleRemove(item.id, e)}
                    aria-label={`Remove ${item.name}`}
                    className="text-muted-foreground hover:text-destructive transition-colors p-1"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

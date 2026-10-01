import React, { useState, useRef } from "react";
import { UploadCloud, File, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "../lib/utils";

export interface StagedFile {
  id: string;
  file: File;
  name: string;
  size: number;
  type: string;
  status: "staged" | "uploading" | "success" | "error";
  errorMessage?: string;
}

export interface FileDropzoneProps {
  onFilesSelected?: (files: StagedFile[]) => void;
  acceptedExtensions?: string[];
  maxFiles?: number;
  className?: string;
}

const DEFAULT_EXTENSIONS = [".txt", ".cfg", ".conf", ".xml", ".json", ".zip", ".tar.gz", ".tar", ".gz", ".log"];

export const FileDropzone: React.FC<FileDropzoneProps> = ({
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
    if (onFilesSelected) {
      onFilesSelected(updated);
    }
  };

  const handleRemove = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = stagedFiles.filter((f) => f.id !== id);
    setStagedFiles(updated);
    if (onFilesSelected) {
      onFilesSelected(updated);
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
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload configuration files — click, drop files, or press Enter to browse"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={cn(
          "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors flex flex-col items-center justify-center gap-3",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
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
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
          aria-label="Upload configuration files"
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

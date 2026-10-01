import type { TrainingQuestionExample } from "../../shared/api/hooks/useTraining";

export interface BuiltSnippet {
  startLine: number;
  content: string;
  highlightLines: number[];
}

/**
 * The real `GET /training/queue/{platform}/next` response (services/training.py
 * `_question_row_to_response`) returns up to 6 example lines with their real
 * source line numbers, but no filename and no guarantee of contiguity
 * (they are the matched statement lines for this question's template
 * group, not a contiguous excerpt of the file). `EvidenceExcerpt` (shared/)
 * expects one contiguous block of text with a start line number, so this
 * fills any gaps between the lowest and highest real line number with a
 * comment-styled placeholder rather than silently renumbering the real
 * lines or inventing filler text — line numbers shown are always the real
 * ones from the operator's corpus.
 */
export function buildTrainingSnippet(examples: TrainingQuestionExample[]): BuiltSnippet {
  const withLines = examples.filter(
    (e): e is { line: number; text: string } => typeof e.line === "number"
  );

  if (withLines.length === 0) {
    // No real line numbers were returned at all — still render the real
    // statement text (never fabricated), just without line-accurate
    // positioning.
    return {
      startLine: 1,
      content: examples.map((e) => e.text).join("\n") || "(no example lines returned)",
      highlightLines: examples.map((_e, i) => i + 1),
    };
  }

  const sorted = [...withLines].sort((a, b) => a.line - b.line);
  const startLine = sorted[0].line;
  const endLine = sorted[sorted.length - 1].line;

  const byLine = new Map(sorted.map((e) => [e.line, e.text]));
  const lines: string[] = [];
  for (let ln = startLine; ln <= endLine; ln++) {
    const text = byLine.get(ln);
    lines.push(text !== undefined ? text : "  # ⋯");
  }

  return {
    startLine,
    content: lines.join("\n"),
    highlightLines: sorted.map((e) => e.line),
  };
}

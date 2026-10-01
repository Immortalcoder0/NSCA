import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  CheckCircle2,
  RotateCw,
  Edit3,
  Ban,
  FastForward,
  ShieldCheck,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { EvidenceExcerpt } from "../../shared/components/EvidenceExcerpt";
import { QuestionProgressBar } from "../components/QuestionProgressBar";
import { PlainReadingBlock } from "../components/PlainReadingBlock";
import { PolarityCheckBlock } from "../components/PolarityCheckBlock";
import { buildTrainingSnippet } from "../lib/buildTrainingSnippet";
import { useAuth } from "../../app/auth-guard";
import {
  useTrainingNextQuestion,
  useTrainingQueuePlatform,
  useSubmitTrainingAnswer,
  useStartTrainingSession,
  useCompleteTrainingSession,
  type TrainingAnswerResponseKind,
  type TrainingQuestionApiModel,
} from "../../shared/api/hooks";
import type { TrainingPlainReading, TrainingPolarityCheck } from "../types";

// The only platform this environment has real seeded-corpus provenance for
// (nsca_platform/tests/fixtures/mikrotik.py's `ARTIFACT_ID`, seeded via
// nsca/platform/seed_training_queue.py). The real `/next` response carries
// no source-artifact filename, so this is the one place a genuine filename
// can be honestly supplied for rule-synthesis provenance
// (`POST /training/answer`'s `source_artifact`); for any other platform it
// is simply omitted — the answer still records and the queue still
// advances, synthesis just doesn't fire, exactly as
// services/training.py.submit_answer documents.
const KNOWN_SOURCE_ARTIFACTS: Record<string, string> = {
  routeros: "RTR-Pune-02.rsc",
};

function toPlainReading(q: TrainingQuestionApiModel): TrainingPlainReading {
  const firstExample = q.examples[0]?.text ?? q.pattern;
  return {
    raw_clause: firstExample,
    statement: q.proposal.description || "No plain-language description was returned for this proposal.",
    mapped_concept: q.proposal.mappings[0]?.fact ?? "(no fact mapping proposed)",
    normalized_property:
      q.proposal.mappings.length > 1 ? `${q.proposal.mappings.length} facts mapped` : "BOOLEAN",
  };
}

function toPolarityCheck(q: TrainingQuestionApiModel): TrainingPolarityCheck {
  const p = q.proposal.polarity;
  const indicator = p.indicator ?? "this token";
  return {
    requires_explicit_confirmation: p.requires_explicit_confirmation,
    prompt: `Does "${indicator}" invert the meaning of this setting (i.e. is the reading negated)?`,
    proposed_polarity: p.inverted ? "negative" : "positive",
    explanation:
      `The extractor found the negation-bearing token "${indicator}" in this construct and infers ` +
      `${p.inverted ? "an INVERTED" : "a direct, non-inverted"} boolean reading. Vendor syntax with negated ` +
      "keywords is the single highest-consequence error class in this product — confirm this reading is " +
      "correct before it becomes a compliance fact.",
  };
}

export const TrainingQuestionPage: React.FC = () => {
  const navigate = useNavigate();
  const { platform: routePlatform } = useParams<{ platform?: string }>();
  const [searchParams] = useSearchParams();
  // Mounted at both `/training/queue/:platform` (the real deep-link target
  // — e.g. the ingestion "platform not taught" invitation link, per
  // 15-api-specification.md §3's `training.url` shape) and the bare
  // `/training/questions` path (reached from the queue page's own [Begin]
  // action via a `?platform=` query string). Route param wins when present.
  const platform = routePlatform || searchParams.get("platform") || "mikrotik_routeros";
  const { user } = useAuth();

  const [isPolarityConfirmed, setIsPolarityConfirmed] = useState(false);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [confirmedControls, setConfirmedControls] = useState(0);
  const sessionStartRef = useRef<number>(Date.now());
  const navigatedRef = useRef(false);

  const nextQuery = useTrainingNextQuestion(platform);
  // Fetched once for a real (non-fabricated) denominator for the Result
  // screen's coverage-shift figure — see TrainingResultPage's router-state
  // contract below.
  const platformQueueQuery = useTrainingQueuePlatform(platform);
  const submitAnswer = useSubmitTrainingAnswer();

  // Real `transfer_metric_session` (TRD-08.4) — opened once per teaching
  // pass so `POST /training/answer`'s `session_id` and `GET
  // /training/metrics`'s learning curve have something real to point to.
  // Previously nothing in the UI ever called `POST /training/sessions`, so
  // every confirmation was recorded session-less and the curve stayed
  // permanently empty even after a full teach-and-ratify pass.
  const startSession = useStartTrainingSession();
  const completeSession = useCompleteTrainingSession();
  const sessionIdRef = useRef<string | null>(null);
  const sessionStartedRef = useRef(false);

  useEffect(() => {
    if (sessionStartedRef.current || !platform) return;
    sessionStartedRef.current = true;
    startSession.mutate(
      { platform },
      { onSuccess: (session) => { sessionIdRef.current = session.id; } }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform]);

  const currentQ = nextQuery.data ?? null;

  const totalControlsUnlocked = useMemo(() => {
    const questions = platformQueueQuery.data?.questions ?? [];
    return questions.reduce((sum, q) => sum + (q.impact?.controls_unlocked ?? 0), 0);
  }, [platformQueueQuery.data]);

  const requiresPolarity = currentQ?.proposal.polarity.requires_explicit_confirmation ?? false;
  const canRespondWithPolarity = !requiresPolarity || isPolarityConfirmed;

  const handleAnswer = useCallback(
    (response: TrainingAnswerResponseKind) => {
      if (!currentQ || submitAnswer.isPending) return;
      if ((response === "confirm" || response === "polarity_inverted") && !canRespondWithPolarity) {
        // Client-side gate — mirrors learning/polarity.py's
        // `TrainingAnswer.polarity_gate` 422 rejection with equal severity;
        // never lets a submit reach the network in the state the API would
        // reject anyway.
        return;
      }
      const controlsForThisQuestion = currentQ.impact.controls_unlocked;
      submitAnswer.mutate(
        {
          question_id: currentQ.question_id,
          response,
          polarity_confirmed: requiresPolarity ? isPolarityConfirmed : undefined,
          taught_by: user.id,
          source_artifact: KNOWN_SOURCE_ARTIFACTS[platform],
          session_id: sessionIdRef.current ?? undefined,
        },
        {
          onSuccess: () => {
            if (response === "confirm" || response === "polarity_inverted") {
              setConfirmedControls((c) => c + controlsForThisQuestion);
            }
            setAnsweredCount((c) => c + 1);
            setIsPolarityConfirmed(false);
          },
        }
      );
    },
    [currentQ, submitAnswer, canRespondWithPolarity, requiresPolarity, isPolarityConfirmed, user.id, platform]
  );

  // Queue exhausted (real 404 -> null, see useTrainingNextQuestion) after at
  // least one real answer was submitted this session -> the teaching
  // session is complete; hand off real, locally-measured session stats to
  // the Result screen (no backend endpoint aggregates "this session's"
  // elapsed time or coverage shift — see TrainingResultPage's own note).
  useEffect(() => {
    if (navigatedRef.current) return;
    if (nextQuery.isLoading || nextQuery.isFetching) return;
    if (nextQuery.data !== null) return;
    if (answeredCount === 0) return;
    navigatedRef.current = true;
    if (sessionIdRef.current) {
      completeSession.mutate({
        sessionId: sessionIdRef.current,
        wallClockMinutes: (Date.now() - sessionStartRef.current) / 60000,
      });
    }
    navigate(`/training/result?platform=${encodeURIComponent(platform)}`, {
      state: {
        platform,
        confirmations_count: answeredCount,
        confirmed_controls: confirmedControls,
        total_controls: totalControlsUnlocked,
        elapsed_ms: Date.now() - sessionStartRef.current,
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextQuery.data, nextQuery.isLoading, nextQuery.isFetching, answeredCount, confirmedControls, totalControlsUnlocked, navigate, platform]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (!currentQ || submitAnswer.isPending) return;

      if (e.key === "1" || e.key === "Enter") {
        handleAnswer("confirm");
      } else if (e.key === "2") {
        handleAnswer("polarity_inverted");
      } else if (e.key === "3") {
        handleAnswer("edit");
      } else if (e.key === "4") {
        handleAnswer("not_relevant");
      } else if (e.key === "5") {
        handleAnswer("skip");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentQ, submitAnswer.isPending, handleAnswer]);

  const snippet = useMemo(() => (currentQ ? buildTrainingSnippet(currentQ.examples) : null), [currentQ]);
  const plainReading = useMemo(() => (currentQ ? toPlainReading(currentQ) : null), [currentQ]);
  const polarity = useMemo(() => (currentQ ? toPolarityCheck(currentQ) : null), [currentQ]);

  const breadcrumb = (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <Link to="/training" className="hover:text-foreground flex items-center gap-1">
        <ArrowLeft size={13} />
        <span>Training Studio Queue</span>
      </Link>
      <span>/</span>
      <span className="font-mono text-foreground font-bold">{platform}</span>
      <span>/</span>
      <span className="font-semibold text-foreground">Interactive Teaching Console</span>
    </div>
  );

  if (nextQuery.isLoading) {
    return (
      <div className="space-y-5">
        {breadcrumb}
        <div className="flex items-center gap-2 text-xs text-muted-foreground p-8 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Loading the next training question…</span>
        </div>
      </div>
    );
  }

  if (nextQuery.isError) {
    return (
      <div className="space-y-5">
        {breadcrumb}
        <div className="p-4 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>
            Failed to load the training queue for {platform}:{" "}
            {nextQuery.error instanceof Error ? nextQuery.error.message : "unknown error"}
          </span>
        </div>
      </div>
    );
  }

  if (!currentQ) {
    return (
      <div className="space-y-5">
        {breadcrumb}
        <div className="p-6 rounded-xl border border-border/80 bg-card text-xs text-muted-foreground text-center">
          No pending training questions for <span className="font-mono font-bold">{platform}</span>. Every question
          has already been answered, or this platform has nothing queued.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Breadcrumb & Navigation */}
      {breadcrumb}

      {/* Progress Bar Header */}
      <QuestionProgressBar
        currentIndex={currentQ.position}
        totalCount={currentQ.total}
        timeRemaining={`${currentQ.total - currentQ.position + 1} question${
          currentQ.total - currentQ.position + 1 === 1 ? "" : "s"
        } remaining`}
      />

      {submitAnswer.isError && (
        <div className="p-3 rounded-lg border border-red-300 dark:border-red-900 bg-red-50/60 dark:bg-red-950/30 text-xs text-red-800 dark:text-red-300 flex items-center gap-2">
          <AlertTriangle size={14} className="shrink-0" />
          <span>{submitAnswer.error instanceof Error ? submitAnswer.error.message : "Failed to submit answer."}</span>
        </div>
      )}

      {/* 2-Column Responsive Teaching Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Real Config Excerpt & AST Translation */}
        <div className="lg:col-span-7 space-y-4">
          <div className="p-4 rounded-xl border border-border/80 bg-card space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="space-y-0.5">
                <span className="font-semibold text-foreground">Configuration Excerpt</span>
                <span className="text-[11px] text-muted-foreground block font-mono">
                  Section: {currentQ.section}
                </span>
              </div>
              {snippet && (
                <span className="text-[11px] font-mono text-muted-foreground">
                  Lines {snippet.startLine}–{snippet.startLine + snippet.content.split("\n").length - 1}
                </span>
              )}
            </div>

            {snippet && (
              <EvidenceExcerpt
                content={snippet.content}
                startLineNumber={snippet.startLine}
                highlightLines={snippet.highlightLines}
              />
            )}
          </div>

          {/* Plain Language Meaning Block */}
          {plainReading && <PlainReadingBlock reading={plainReading} />}

          {/* Impact Callout */}
          <div className="p-3.5 rounded-lg bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900 flex items-center justify-between text-xs text-emerald-900 dark:text-emerald-200">
            <div className="flex items-center gap-2 font-semibold">
              <ShieldCheck size={16} className="text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span>Confirming unlocks evaluation for {currentQ.impact.controls_unlocked} security controls.</span>
            </div>
            <span className="font-mono text-[10px] uppercase font-bold text-emerald-700 dark:text-emerald-300">
              {Math.round(currentQ.proposal.confidence * 100)}% Confidence
            </span>
          </div>
        </div>

        {/* Right Column: Decision & Polarity Validation Controls */}
        <div className="lg:col-span-5 space-y-4">
          {/* Polarity Ambiguity Gate Block (when applicable) */}
          {polarity && (
            <PolarityCheckBlock
              polarity={polarity}
              isConfirmed={isPolarityConfirmed}
              onToggleConfirm={() => setIsPolarityConfirmed(!isPolarityConfirmed)}
            />
          )}

          {/* Five Response Options Toolbar */}
          <div className="p-5 rounded-xl border border-border/80 bg-card space-y-3">
            <span className="text-xs font-bold text-foreground block">
              Teaching Actions (Keyboard 1–5):
            </span>

            <div className="space-y-2">
              {/* 1. Confirm */}
              <button
                onClick={() => handleAnswer("confirm")}
                disabled={!canRespondWithPolarity || submitAnswer.isPending}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-primary hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed text-primary-foreground font-bold text-xs transition-all shadow-xs"
              >
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} />
                  <span>Confirm Interpretation</span>
                </div>
                <span className="text-[10px] font-mono opacity-80">[1 / Enter]</span>
              </button>

              {/* 2. Inverted */}
              <button
                onClick={() => handleAnswer("polarity_inverted")}
                disabled={!canRespondWithPolarity || submitAnswer.isPending}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-amber-300 bg-amber-50/60 dark:bg-amber-950/40 hover:bg-amber-100 disabled:opacity-40 disabled:cursor-not-allowed text-amber-900 dark:text-amber-200 font-semibold text-xs transition-colors"
              >
                <div className="flex items-center gap-2">
                  <RotateCw size={15} className="text-amber-600" />
                  <span>Inverted Polarity</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">[2]</span>
              </button>

              {/* 3. Edit */}
              <button
                onClick={() => handleAnswer("edit")}
                disabled={submitAnswer.isPending}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-border bg-secondary hover:bg-secondary/80 disabled:opacity-40 disabled:cursor-not-allowed text-foreground font-semibold text-xs transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Edit3 size={15} className="text-muted-foreground" />
                  <span>Edit AST Property</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">[3]</span>
              </button>

              {/* 4. Not Relevant */}
              <button
                onClick={() => handleAnswer("not_relevant")}
                disabled={submitAnswer.isPending}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-border bg-secondary hover:bg-secondary/80 disabled:opacity-40 disabled:cursor-not-allowed text-foreground font-semibold text-xs transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Ban size={15} className="text-muted-foreground" />
                  <span>Not Security Relevant</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">[4]</span>
              </button>

              {/* 5. Skip */}
              <button
                onClick={() => handleAnswer("skip")}
                disabled={submitAnswer.isPending}
                className="w-full flex items-center justify-between p-3 rounded-lg border border-border bg-secondary hover:bg-secondary/80 disabled:opacity-40 disabled:cursor-not-allowed text-muted-foreground hover:text-foreground font-semibold text-xs transition-colors"
              >
                <div className="flex items-center gap-2">
                  <FastForward size={15} />
                  <span>Skip for Now</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">[5]</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

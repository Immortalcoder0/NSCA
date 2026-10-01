import type {
  FindingModel,
  FindingLifecycleState,
  FindingEvidenceSnippet,
  FindingFrameworkMapping,
} from "../types";
import type { SeverityType, VerdictType, TrustTierType } from "../../shared/theme/tokens";

/**
 * Real shape of `GET /campaigns/{id}/findings` items / `GET /findings/{id}`
 * (`nsca_platform/services/finding_lifecycle.py::_row_to_response`, verified
 * live against the M5 server — see `findings/hooks.ts`). Deliberately loose
 * (`Record<string, unknown>`-adjacent) rather than pretending this is a
 * generated OpenAPI type, per the shared hooks' own convention: the real
 * router has no `response_model=`.
 */
export interface ApiFindingRaw {
  id: string;
  control: string;
  verdict: string;
  severity: { base: string | null; effective: string | null; reason: string | null };
  evidence: Array<{
    artifact: string;
    lines: number[];
    highlight: number[];
    excerpt: string;
    facts?: string[];
  }>;
  frameworks: Array<{ id: string; framework: string }>;
  attack_paths: string[];
  rulepack_trust_tier: string | null;
  state: string;
  owner: string | null;
  due_date: string | null;
}

/** Best-effort hostname/platform resolved from a finding's primary evidence
 * artifact via `GET /artifacts/{id}` (see `useArtifact` in
 * `shared/api/hooks/useFindings.ts`) — the only real source of device
 * identity available today, since the finding response itself carries none. */
export interface ResolvedDeviceInfo {
  hostname?: string;
  platform?: string;
}

// 09-findings-lifecycle.md §4's nine real states collapsed onto this
// track's six-state `FindingLifecycleState` (built in Phase 1 against the
// UX spec's mock, which predates the real state machine backend-02 M2
// actually implemented). Flagged judgment call, not a silent 1:1 renaming:
// `Withdrawn` (dispute upheld — finding was not genuine) and `Closed`
// (fully done) both collapse to `Verified_Resolved` since the UI only
// distinguishes "still open in some form" vs "resolved," and neither
// `Withdrawn` nor `Closed` needs further action from this screen.
// `Assigned`/`Remediated` both map to `Remediation_Planned` for the same
// reason (both mean "someone is actively working the fix").
const STATE_MAP: Record<string, FindingLifecycleState> = {
  New: "Open",
  Confirmed: "Confirmed",
  Disputed: "Disputed",
  Withdrawn: "Verified_Resolved",
  "Risk Accepted": "Risk_Accepted",
  Assigned: "Remediation_Planned",
  Remediated: "Remediation_Planned",
  Verified: "Verified_Resolved",
  Closed: "Verified_Resolved",
};

function mapState(raw: string | undefined): FindingLifecycleState {
  if (!raw) return "Open";
  return STATE_MAP[raw] ?? "Open";
}

const VALID_VERDICTS: VerdictType[] = ["PASS", "PASS_PARTIAL", "PASS_VACUOUS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"];
function mapVerdict(raw: string | undefined): VerdictType {
  const upper = (raw ?? "UNKNOWN").toUpperCase() as VerdictType;
  return VALID_VERDICTS.includes(upper) ? upper : "UNKNOWN";
}

const VALID_SEVERITIES: SeverityType[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"];
function mapSeverity(raw: string | null | undefined): SeverityType {
  const upper = (raw ?? "MEDIUM").toUpperCase() as SeverityType;
  return VALID_SEVERITIES.includes(upper) ? upper : "MEDIUM";
}

const VALID_TIERS: TrustTierType[] = ["CERTIFIED", "COMMUNITY", "SYNTHESIZED", "UNVERIFIED"];
function mapTrustTier(raw: string | null | undefined): TrustTierType {
  const upper = (raw ?? "CERTIFIED").toUpperCase() as TrustTierType;
  return VALID_TIERS.includes(upper) ? upper : "CERTIFIED";
}

/**
 * Maps a real `ApiFindingRaw` onto this track's `FindingModel` (the shape
 * every Phase-1-built component — `FindingCard`, the workbench, the detail
 * page — already renders). The real API does not return `title`,
 * `description`, `rule_id`, `campaign_id`, `device_id`, `hostname`, or
 * `created_at` at all, so these are honestly synthesized rather than
 * fabricated as if they were real API text:
 *
 * - `title`/`rule_id`: derived from `control` (the only content identifier
 *   the API gives us — `GET /knowledge/controls` is also still an M0 stub
 *   returning one hardcoded example, so it cannot resolve a real title for
 *   an arbitrary control id either).
 * - `description`: left empty (never fabricated placeholder prose).
 * - `campaign_id`/`device_id`: filled from what the *caller* already knows
 *   (the campaign being browsed; the resolved artifact's device hostname,
 *   when available) rather than invented.
 * - `hostname`/`device_platform`: from `deviceInfo` (resolved via the
 *   primary evidence artifact — see `ResolvedDeviceInfo` above); falls back
 *   to an honest "Unknown device" label, never a guessed hostname.
 * - `created_at`: not returned by the API; left as an empty string (no
 *   component on this track currently renders it).
 */
export function mapApiFindingToModel(
  raw: ApiFindingRaw,
  campaignId: string,
  deviceInfo?: ResolvedDeviceInfo
): FindingModel {
  const evidence: FindingEvidenceSnippet[] = (raw.evidence ?? [])
    .filter((e) => e.artifact) // real payload includes empty-artifact placeholders for facts with no line reference
    .map((e) => {
      // Real evidence entries usually carry a single line number (the one
      // fact-bearing line — `lines: [27]`), not the `[start, end]` range
      // range this track's mock always used. Treat a single-element array
      // as a one-line range rather than collapsing it to the misleading
      // `[0, 0]` ("line 0") the naive `length >= 2` check produced.
      let lines: [number, number] = [0, 0];
      if (e.lines && e.lines.length >= 2) lines = [e.lines[0], e.lines[1]];
      else if (e.lines && e.lines.length === 1) lines = [e.lines[0], e.lines[0]];

      return {
        artifact: e.artifact,
        lines,
        highlight: e.highlight ?? [],
        excerpt: e.excerpt || "(no excerpt captured for this fact)",
        facts: e.facts,
      };
    });

  const frameworks: FindingFrameworkMapping[] = (raw.frameworks ?? []).map((fw) => ({
    framework: fw.framework,
    id: fw.id,
  }));

  const hostname = deviceInfo?.hostname ?? "Unknown device";
  const devicePlatform = deviceInfo?.platform ?? "unknown";

  return {
    id: raw.id,
    campaign_id: campaignId,
    device_id: hostname,
    hostname,
    device_platform: devicePlatform,
    control_id: raw.control,
    rule_id: raw.control,
    title: `${raw.control} — control evaluation`,
    description: "",
    verdict: mapVerdict(raw.verdict),
    severity: {
      base: mapSeverity(raw.severity?.base),
      effective: mapSeverity(raw.severity?.effective ?? raw.severity?.base),
      reason: raw.severity?.reason ?? undefined,
    },
    state: mapState(raw.state),
    rulepack_trust_tier: mapTrustTier(raw.rulepack_trust_tier),
    frameworks,
    evidence,
    attack_paths: raw.attack_paths ?? [],
    assigned_to: raw.owner ?? undefined,
    created_at: "",
  };
}

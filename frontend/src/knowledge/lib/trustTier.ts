import type { TrustTierType } from "../../shared/theme/tokens";

const KNOWN: readonly TrustTierType[] = ["CERTIFIED", "COMMUNITY", "SYNTHESIZED", "UNVERIFIED"];

/** The real API returns lowercase trust-tier strings (e.g. "certified",
 * "local", "provisional") that don't always match the shared
 * `TrustTierType` badge vocabulary ("local"/"provisional" have no
 * corresponding token) — falls back to UNVERIFIED for anything unrecognised
 * rather than crashing `TrustTierBadge`, and is honest about the fallback
 * via the returned flag. */
export function toTrustTierType(raw: string | undefined | null): { tier: TrustTierType; wasMapped: boolean } {
  if (!raw) return { tier: "UNVERIFIED", wasMapped: true };
  const upper = raw.toUpperCase() as TrustTierType;
  if (KNOWN.includes(upper)) return { tier: upper, wasMapped: false };
  return { tier: "UNVERIFIED", wasMapped: true };
}

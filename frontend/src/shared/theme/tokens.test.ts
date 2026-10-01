import { describe, it, expect } from "vitest";
import {
  VERDICT_TOKENS,
  SEVERITY_TOKENS,
  TRUST_TIER_TOKENS,
  type VerdictType,
  type SeverityType,
} from "./tokens";

describe("Design Tokens & Visual Vocabulary", () => {
  it("defines all 6 mandatory verdict states", () => {
    const expectedVerdicts: VerdictType[] = [
      "PASS",
      "PASS_PARTIAL",
      "PASS_VACUOUS",
      "FAIL",
      "UNKNOWN",
      "NOT_APPLICABLE",
    ];

    expectedVerdicts.forEach((v) => {
      expect(VERDICT_TOKENS[v]).toBeDefined();
      expect(VERDICT_TOKENS[v].label).toBeTruthy();
      expect(VERDICT_TOKENS[v].glyph).toBeTruthy();
      expect(VERDICT_TOKENS[v].monochrome.glyphSymbol).toBeTruthy();
    });
  });

  it("enforces U3: UNKNOWN is distinctly shaped and not styled like PASS", () => {
    const unknownToken = VERDICT_TOKENS.UNKNOWN;
    const passToken = VERDICT_TOKENS.PASS;

    expect(unknownToken.glyph).toBe("question");
    expect(unknownToken.glyph).not.toEqual(passToken.glyph);
    expect(unknownToken.color.hex).not.toEqual(passToken.color.hex);
    expect(unknownToken.monochrome.glyphSymbol).not.toEqual(passToken.monochrome.glyphSymbol);
  });

  it("defines all 5 severity levels with distinct glyphs per U7", () => {
    const expectedSeverities: SeverityType[] = [
      "CRITICAL",
      "HIGH",
      "MEDIUM",
      "LOW",
      "INFORMATIONAL",
    ];

    const glyphs = new Set<string>();
    const symbols = new Set<string>();

    expectedSeverities.forEach((s) => {
      const token = SEVERITY_TOKENS[s];
      expect(token).toBeDefined();
      expect(token.weight).toBeGreaterThan(0);
      expect(glyphs.has(token.glyph)).toBe(false);
      expect(symbols.has(token.glyphSymbol)).toBe(false);
      glyphs.add(token.glyph);
      symbols.add(token.glyphSymbol);
    });

    expect(glyphs.size).toBe(5);
    expect(symbols.size).toBe(5);
  });

  it("defines trust tier tokens with certified and uncertified distinctions", () => {
    expect(TRUST_TIER_TOKENS.CERTIFIED.isCertified).toBe(true);
    expect(TRUST_TIER_TOKENS.COMMUNITY.isCertified).toBe(false);
    expect(TRUST_TIER_TOKENS.SYNTHESIZED.isCertified).toBe(false);
    expect(TRUST_TIER_TOKENS.UNVERIFIED.isCertified).toBe(false);
  });
});

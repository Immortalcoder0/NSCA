# 08 · The Learning System

> The problem statement's hardest requirement:
>
> *"When the system encounters an unrecognized configuration structure, it will
> trigger an Interactive Training Interface... the administrator will map these
> commands to specific security categories. The AI engine will then update its
> internal **heuristics**, effectively 'learning' to parse this new vendor's
> logic **without requiring backend code redeployment**."*

---

## 1. Design position

Note the problem statement's own word: **heuristics**. Not weights. Not
retraining. The problem setter is describing rule and pattern updates.

That aligns with the only design that works in this context:

> **Learning is the accumulation of inspectable data, not the adjustment of model
> parameters.**

Why this is not merely a preference:

| Requirement | Data-based learning | Fine-tuned model |
|---|---|---|
| Operate in an air-gapped facility | Yes | Cannot train without infrastructure |
| Audit what was learned | Read the file | Not possible |
| Roll back one incorrect lesson | Revert one rule | Not possible |
| Attribute a lesson to a person | Recorded | Not possible |
| Share a fraction of the knowledge | Export one rulepack | Not possible |
| Determinism at assessment time | Guaranteed | Not guaranteed |

Every audit-integrity property in this product depends on that choice.

---

## 2. Where the model sits

```
   unknown configuration
            │
            ▼
   ┌──────────────────┐
   │ grammar inference│  ← statistical, no model
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ template mining  │  ← statistical, no model
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ relevance filter │  ← statistical, no model
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ candidate        │  ← lexical + structural priors,
   │ proposal         │     MODEL-ASSISTED
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ HUMAN CONFIRMS   │  ← the decision point
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ rule synthesis   │  ← deterministic
   │ + validation     │
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ ratification     │  ← second human
   └────────┬─────────┘
            ▼
    deterministic rulepack
    (used for ever after — zero model calls)
```

**The model appears once, produces a proposal, and is never consulted again for
that platform.** What is stored is a deterministic rule.

---

## 3. Stage 1 — Grammar inference

Before any human is involved, recover the file's **structure** statistically.

**Key separation: syntax is inferable automatically; semantics is not.**

### 3.1 Detection procedure

| Property | Method |
|---|---|
| **Comment character** | Which line prefix appears on lines that never contain assignment operators and exhibit high natural-language token entropy? |
| **Hierarchy paradigm** | Test each hypothesis against the file and score coverage: indentation distribution; brace balance; path-header lines carrying no value; paired block keywords; XML well-formedness |
| **Statement shape** | Tokenise non-header lines. Detect separator density (`=`, whitespace, `:`), quoting conventions, and repeated positional structure |
| **Verbs** | Recurring leading tokens across sections (`add`, `set`, `delete`, `config`) |
| **Selectors** | Bracketed or predicate-like sub-expressions that identify a target |

### 3.2 Worked example — MikroTik RouterOS

Input the system has never seen:

```
# aug/25/2026 14:32:11 by RouterOS 7.11.2
/ip service
set telnet disabled=no port=23
set ssh disabled=no port=22
/snmp community
set [ find default=yes ] name=public read-access=yes
/user
add name=admin group=full password=Str0ngP@ss
```

Inferred without any human input:

```yaml
comment_char: "#"
paradigm:     path_header
path_prefix:  "/"
verbs:        [set, add]
statement:    "<verb> [selector] <key>=<value> ..."
selector:     "[ ... ]"
quoting:      double_quote
coverage:     98.4%          # proportion of lines matched by the grammar
```

**Output: a complete parse tree with zero semantic understanding.** That is the
correct place to stop and involve a human.

### 3.3 Failure handling

If grammar inference achieves low coverage — a structurally hostile or
proprietary binary-adjacent format — the system does **not** guess. It reports:

```
⚠ Grammar inference achieved 43% line coverage on RTR-Pune-02.
  Structure could not be reliably determined.
  → Assisted grammar authoring required, or supply an alternative export format.
```

An unreliable grammar produces silently wrong facts, which is worse than no
facts at all.

---

## 4. Stage 2 — Reduce thousands of lines to a handful of questions

A real configuration is 3,000–6,000 lines. Presenting all unmatched lines is
unusable. Three reductions, applied in order.

### 4.1 Template collapse

Replace variable-looking tokens with slots, then cluster identical skeletons:

```
add address=10.0.0.1/24 interface=bridge1
add address=192.168.5.1/24 interface=bridge2      ─┐  one template
add address=172.16.0.1/30 interface=WAN            ─┘
        ↓
add address=<cidr> interface=<name>
```

Typical reduction: **4,000 lines → 60–120 templates.**

Slot detection: IP addresses and prefixes, integers, quoted strings, MAC
addresses, identifiers appearing in high-cardinality positions, timestamps.

### 4.2 Relevance filtering

Most templates are irrelevant to compliance:

```
add name=bridge1 protocol-mode=rstp            → no control cares
set [ find default-name=ether1 ] name=WAN      → no control cares
add address=10.0.0.1/24 interface=bridge1      → no control cares
```

The system knows exactly which schema facts its loaded controls require. Score
each template by lexical and semantic proximity to those fact names and their
known synonyms.

**High-scoring vocabulary:** `telnet`, `ssh`, `snmp`, `community`, `password`,
`user`, `group`, `privilege`, `radius`, `tacacs`, `log`, `syslog`, `ntp`,
`timeout`, `cipher`, `key`, `certificate`, `acl`, `filter`, `permit`, `deny`

**Low-scoring:** `description`, `comment`, `vlan`, `route`, `bandwidth`, `mtu`,
`name`, `color`

Typical reduction: **120 templates → ~15 candidates.**

> *"We do not ask you four thousand questions. We ask the ones that matter."*

### 4.3 Information-gain ordering

Of the remaining candidates, order by **expected information gain** — which
single answer resolves the most currently-undetermined controls.

```
Q1  /ip service        → 5 facts → unlocks  8 controls   ← ask first
Q2  /user              → 4 facts → unlocks  6 controls
Q3  /snmp community    → 3 facts → unlocks  5 controls
Q4  /system logging    → 2 facts → unlocks  4 controls
...
Q9  /user aaa          → 1 fact  → unlocks  1 control
```

**Net effect: 4,000 unknown lines become 9 questions, best-first, where the first
three deliver most of the coverage.**

This is an acquisition function over an active-learning objective — a principled
procedure, not a user-interface convenience.

---

## 5. Stage 3 — Guess before asking

Three independent, corroborating signals.

### 5.1 Lexical priors — the domain's structural gift

The system already knows Cisco's `transport input telnet` produces
`mgmt.protocols.telnet.enabled`, and FortiOS's `set admin-telnet disable`
produces the same fact.

The MikroTik line reads `set telnet disabled=no`. The token `telnet` is present.

> **Networking vocabulary is standardised even where syntax is not.** Every
> vendor writes `telnet`, `ssh`, `snmp`, `ntp`, `radius`, `tacacs` — they have no
> choice, because these are interoperability protocols defined in published RFCs.
> Vendors differentiate on syntax, never on protocol names.

Therefore **the vocabulary shared across all these dialects is precisely the
security-relevant vocabulary.** This is why cross-platform guessing works at all,
and it should be exploited aggressively.

### 5.2 Structural analogy

In previously taught platforms, this fact was extracted from a node semantically
located under "system services." Here the candidate sits under `/ip service`.
Position corroborates the lexical match. Two independent signals agreeing raises
confidence materially.

### 5.3 Value-shape and polarity analysis

`disabled=no` — value domain `{yes, no}`, therefore boolean. Target fact is
boolean. Type-compatible.

**But the key contains a negation.**

```
disabled = no    →    enabled = TRUE
```

**Polarity inversion is the highest-consequence error class in the entire
system.** Invert it and a device with Telnet wide open is certified compliant —
and unlike a parse failure, which surfaces as UNKNOWN, a polarity error surfaces
as a confident PASS.

Negation indicators: `disabled`, `deny`, `no-`, `off`, `shutdown`, `suppress`,
`inactive`, `block`.

**Policy: never infer polarity silently.** Always present it as its own explicit,
separately confirmable statement, and require a distinct confirmation when a
negation indicator is present.

### 5.4 The model's contribution

Given the raw section, the target schema, and the heuristic candidates, a
language model proposes mappings with justifications. It is genuinely good at
this: reading unfamiliar structured text and relating it to a described schema.

**Boundary conditions:**

- Model output is a **proposal for human confirmation**, never a stored fact
- Secrets, hashes and credentials are redacted before any model invocation
- A **local inference mode is mandatory**, so that no configuration content
  leaves the deployment
- The model is not consulted again for this platform once rules exist

---

## 6. Stage 4 — The confirmation interaction

```
┌────────────────────────────────────────────────────────┐
│  Training Studio · MikroTik RouterOS                   │
│  Question 1 of 9                    Coverage: 0% → ?   │
│                                                        │
│  Section:  /ip service                                 │
│  Pattern:  set <service> disabled=<yes|no> [port=<n>]  │
│                                                        │
│  Found in RTR-Pune-02.rsc (6 matching lines):          │
│      set telnet  disabled=no   port=23      line 14    │
│      set ssh     disabled=no   port=22      line 17    │
│      set www     disabled=no   port=80      line 16    │
│      set ftp     disabled=no   port=21      line 15    │
│      set api     disabled=yes               line 19    │
│                                                        │
│  ── Our reading ────────────────────────────────────   │
│  This appears to enable or disable management services │
│                                                        │
│      telnet  →  Telnet service          ENABLED        │
│      ssh     →  SSH service             ENABLED        │
│      www     →  HTTP management         ENABLED        │
│      ftp     →  FTP service             ENABLED        │
│      api     →  API service             disabled       │
│                                                        │
│  ⚠  POLARITY CHECK                                     │
│     "disabled=no" is read as the service being ON.     │
│     Is that correct?                                   │
│                                                        │
│  Confirming this will resolve 8 controls.              │
│                                                        │
│    [ Confirm ]   [ Polarity is inverted ]              │
│    [ Edit mapping ]   [ Not compliance-relevant ]      │
└────────────────────────────────────────────────────────┘
```

### 6.1 The design principle

> **Humans are fast and accurate at *"is this right?"* and slow and unreliable at
> *"write the correct rule."***

Every effective annotation interface exploits this asymmetry. Here it is what
allows a network engineer who has never written a regular expression to teach a
parser — which is exactly what the problem statement requires.

### 6.2 Interaction requirements

| Requirement | Reason |
|---|---|
| One question at a time | Reduces error rate; the alternative is a wall of decisions |
| Show real lines from *their* configuration | Concrete beats abstract; they recognise their own device |
| State the coverage impact before answering | Motivates completion; makes progress legible |
| Polarity as a separate confirmation | The highest-consequence error class |
| "Not compliance-relevant" as a first-class answer | Prevents forced incorrect mappings; the answer is itself information |
| Reversible | Any confirmation can be revisited before ratification |
| Estimated time remaining | Nine questions is tractable; unknown-length is not |

---

## 7. Stage 5 — Synthesis and validation

Confirmation synthesises a deterministic rule:

```yaml
extractor_id: mikrotik_routeros.ip_service.enabled
version:      1
status:       provisional
scope:
  section: "/ip service"
match: 'set (?P<svc>\S+).*disabled=(?P<state>yes|no)'
emit:
  fact:  "mgmt.protocols.{{ svc | service_map }}.enabled"
  value: "{{ state == 'no' }}"          # polarity inverted, human-confirmed
service_map:
  telnet: telnet
  ssh:    ssh
  www:    http
  ftp:    ftp
  api:    api
tests:                                   # frozen from confirmed examples
  - { input: "set telnet disabled=no port=23", expect: { telnet.enabled: true  } }
  - { input: "set api disabled=yes",           expect: { api.enabled:    false } }
provenance:
  taught_by:     r.kulkarni
  taught_at:     2026-09-14T10:22:00Z
  source_artifact: RTR-Pune-02.rsc
  confirmed_examples: 5
```

### 7.1 Validation gates — the rule must survive attack before acceptance

| Gate | Check | On failure |
|---|---|---|
| **Self-match** | Run against the source artifact; display every matched line | Show the operator; allow correction |
| **Corpus scope** | Run against the entire corpus. Does it fire on other platforms? | Reject or require narrowing |
| **Conflict** | Does another rule produce this fact with a different value? | Flag both; require resolution |
| **Type** | Does the emitted value match the schema type? | Reject |
| **Regression** | Do all existing frozen tests still pass? | Reject |
| **Coverage delta** | Report the effect on estate coverage | Informational |

### 7.2 Annotation and test suite are the same artifact

Every confirmed example becomes a permanent regression test.

Consequences:

- The system can never silently regress on something a human verified
- The test suite accumulates at zero marginal cost
- A rulepack's test count is a legible quality signal
- Teaching produces validation, not just capability

---

## 8. Stage 6 — Ratification

Because this is an audit tool, the rulepack is a control surface. A wrong rule
produces wrong findings that look identical to right ones.

**Two-person rule:**

```
Rule mikrotik_routeros.ip_service.enabled@1
  Taught by     r.kulkarni      2026-09-14 10:22
  Status        PROVISIONAL

  ⚠ Findings from provisional rules are flagged and excluded
    from issued reports.

  Requires ratification by a different authorised user.
  [ Review evidence ]   [ Ratify ]   [ Reject ]
```

| Status | Usable for exploration | Usable in an issued report |
|---|---|---|
| `provisional` | Yes, flagged | **No** |
| `ratified` | Yes | Yes |
| `deprecated` | No | No |

This is the same control the product recommends for network changes, applied to
itself.

---

## 9. Result

```
RTR-Pune-02 · MikroTik RouterOS 7.11.2

BEFORE                          AFTER  (8 min 12 s, 5 confirmations)
Coverage    0%                  Coverage   71%
PASS        0                   PASS        9
FAIL        0                   FAIL       12
UNKNOWN    70                   UNKNOWN    20
```

With real, evidence-bound findings:

```
FAIL  Plaintext management protocols   /ip service:14  set telnet disabled=no
FAIL  HTTP management enabled          /ip service:16  set www disabled=no
FAIL  Default SNMP community           /snmp community:31  name=public
FAIL  Privileged local account,        /user:44  group=full
      no central authentication        /user aaa:47  use-radius=no
PASS  SSH enabled                      /ip service:17
PASS  NTP client enabled               /system ntp client:52
UNKNOWN  Password complexity policy    no mapping yet → queued as Q10
UNKNOWN  Session idle timeout          no mapping yet → queued as Q11
```

**The remaining UNKNOWNs become the next round of questions. The loop is
self-directing** — coverage gaps generate their own curriculum.

---

## 10. Cross-platform transfer

By the seventh platform, the system has observed `telnet` mapped across six
syntaxes, `snmp community` across six, `radius` across six. Lexical and
structural priors are correspondingly sharper, so proposals are more often
correct and humans confirm more and correct less.

**This must be measured, because it is the product's central claim.**

```
Human confirmations required to reach 70% coverage

  1  Cisco IOS        ████████████████████████  47
  2  Juniper JunOS    ███████████████           31
  3  FortiOS          ███████████               22
  4  PAN-OS           ███████                   14
  5  Arista EOS       █████                     11
  6  MikroTik         ████                       8
  7  SONiC            ███                        6
```

A downward curve is evidence that the system accumulates **transferable**
knowledge rather than merely storing patterns. It is the measurable answer to the
problem statement's demand for *"Scalability & Adaptation"* — and it cannot be
fabricated, because the platform records every confirmation.

**Reported metrics:**

| Metric | Meaning |
|---|---|
| Confirmations to 70% coverage | Primary effort measure |
| Proposal acceptance rate | Proportion of proposals confirmed unchanged — measures guess quality |
| Polarity correction rate | Proportion of proposals whose polarity was corrected — a safety indicator |
| Wall-clock time to onboard | The headline claim: minutes, not months |

---

## 11. Handling genuinely novel capabilities

When a platform introduces a concept present in no framework anywhere,
category matching fails by definition. Two cases.

### 11.1 Novel instance of a known category

MikroTik's **Winbox** — proprietary, on TCP/8291, no other vendor has it — is
recognisably *a management service*.

The system generalises the intent of existing management-plane controls onto it:

```
This appears to be a management service.
Your management-plane controls require encryption, authentication,
source restriction and logging.

Apply the same requirements to `winbox`?
  [ Apply ]   [ Modify ]   [ Not a management service ]
```

One click authors a platform-specific control by generalising controls that
already exist. **Same confirm-don't-author pattern, one level up.**

### 11.2 Genuinely novel category

A container runtime on a switch. A programmable data plane. An on-device
configuration assistant. No analogy fits.

Route by **structural distance** from known categories:

| Distance | Route |
|---|---|
| Close to a known category | Generalise existing controls (§11.1) |
| Far, properties inferable | Apply property-derived controls ([06 §7](06-controls-and-frameworks.md)) |
| Far, properties unclear | Escalate to a human; report as **unassessed risk surface** |

The third outcome is not a failure. It is the honest output — and it exceeds what
any competing tool produces, because everyone else's coverage of a novel
capability is a *silent* zero.

### 11.3 Schema growth

A genuinely new concept requires **three** things to be learned, not one:

1. **Extraction rules** — how to read this platform's syntax
2. **Schema fields** — new concepts this platform introduced
3. **Controls** — what to demand of those new concepts

Most implementations consider only the first. The problem statement's phrase
*"support new vendors, **standards**, and OS versions"* asks for all three, which
is why the schema registry is runtime-extensible
([05 §7](05-security-baseline-model.md)).

---

## 12. Failure modes and defences

| Failure | Consequence | Defence |
|---|---|---|
| **Inverted polarity** | A vulnerable device certified compliant — the worst outcome in the system | Explicit separate confirmation; negation-word detection; second confirmation required; polarity correction rate tracked |
| Over-broad rule | Fires on unrelated platforms, corrupting their facts | Corpus scope gate rejects before acceptance |
| Wrong semantic mapping | Consistently wrong facts on that platform | Corpus validation; conflict detection; two-person ratification; full attribution and rollback |
| Grammar inference misfires | Silently wrong parse tree | Coverage threshold; refuse below it rather than guess |
| Rule regression | A later change breaks earlier behaviour | Frozen tests from every confirmation |
| Malicious imported rulepack | Corrupted findings, or code execution | Signature verification; declarative-only rulepacks; local corpus validation; trust tier displayed |
| Operator fatigue | Careless confirmations | Nine questions, not four thousand; relevance filtering; progress and impact shown |
| Model unavailable | Cannot propose | Heuristic-only mode degrades to plainer proposals; teaching still functions |

---

## 13. Requirements satisfied

| Problem statement phrase | How it is met |
|---|---|
| *"trigger an Interactive Training Interface"* | Training Studio, entered automatically on unrecognised structure |
| *"presented with the 'raw' unrecognized command lines"* | Real lines from the operator's own configuration, with line numbers |
| *"user-friendly, low-code interface"* | Confirm-don't-author; no regular expressions authored by the user |
| *"map these commands to specific security categories"* | Schema fact mapping with a plain-language description |
| *"update its internal heuristics"* | Rulepack data, versioned and revertible — the problem statement's own word |
| *"without requiring backend code redeployment"* | All three learned layers are runtime data |
| *"Pattern Recognition and NLP"* | Template mining is pattern recognition; semantic mapping is NLP |
| *"support any network device configuration"* | Grammar inference plus property-derived controls |

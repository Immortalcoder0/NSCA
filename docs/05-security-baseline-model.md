# 05 · The Security Baseline Model

> **This is the most important design artifact in the product.** Every component
> upstream converts *into* it; every component downstream reasons *over* it. A
> mistake here propagates everywhere and is expensive to correct later.
>
> Design this on paper, against real configurations from at least four platforms,
> before writing pipeline code.

---

## 1. Purpose

The Security Baseline Model (SBM) is a **vendor-neutral representation of a
device's security posture**. It is the intermediate representation of the
compiler described in [04-system-architecture.md](04-system-architecture.md).

It exists so that:

- **Controls are written once** and apply to every platform, present and future
- **Adding a platform** costs work only on the reading side
- **Multi-framework reporting** is a mapping exercise, not four engines
- **Evidence is preserved** — every fact knows where it came from
- **Uncertainty is representable** — the model can say *"I do not know"*

---

## 2. Design principles

| # | Principle | Consequence |
|---|---|---|
| SBM-1 | **Semantic, not syntactic** | No fact name may reference vendor terminology. `mgmt.protocols.telnet.enabled`, never `transport_input` |
| SBM-2 | **Every fact carries provenance** | A value without a source is unusable as audit evidence |
| SBM-3 | **Absence is representable and distinguishable** | Six distinct provenance sources; silence never becomes a value |
| SBM-4 | **Extensible at runtime** | A new platform may introduce a concept the schema lacks. Registering it must not require code changes |
| SBM-5 | **Normalised units and enumerations** | Timeouts in seconds, always. Algorithm names canonicalised. Comparison must not require per-platform logic |
| SBM-6 | **Absorbs both logical polarities** | Cisco enumerates permitted protocols; Fortinet flags disabled ones. The schema stores the positive assertion; extractors handle inversion |
| SBM-7 | **Lists are objects, not strings** | A cipher list is a list of canonical algorithm identifiers, not a raw string |
| SBM-8 | **Capabilities are first-class** | Anything that listens, authenticates or executes is representable even if no control exists for it yet |

---

## 3. The fact

The atomic unit of the model.

```yaml
path:  mgmt.protocols.telnet.enabled     # dotted address in the namespace
value: true                              # typed value
type:  boolean

provenance:
  source:     explicit
  artifact:   CORE-SW-01/running-config.txt
  lines:      [143]
  excerpt:    " transport input telnet ssh"
  extractor:  cisco_ios.vty.transport_input@v7
  confidence: 1.0
  layer:      null            # populated when source == inherited
```

### 3.1 The provenance source classification

**This is the single most important design decision in the schema.** It is what
allows the system to be honest about what it does not know.

| Source | Meaning | Downstream trust |
|---|---|---|
| `explicit` | Written in the configuration at a known line | Full |
| `default_known` | Absent; a verified default exists for this platform and version | Full |
| `default_inferred` | Absent; sibling devices of this platform express it, so it is presumed at default, but the default value itself is unverified | Partial — controls **MAY** treat as UNKNOWN under strict mode |
| `inherited` | Present via a parent configuration layer (template, group, device-group) | Full; the layer is cited |
| `default_unknown` | Absent, and no default is known for this platform | **None — forces UNKNOWN** |
| `not_applicable` | The platform has no such concept | No finding produced |

**The guarantee:** on an unfamiliar platform, silence resolves to
`default_unknown`, which forces every dependent control to `UNKNOWN`, which
lowers the coverage score, which appears in the report.

Silence never becomes compliance.

### 3.2 Why `not_applicable` is distinct from `default_unknown`

These are frequently conflated and the consequences differ:

- `default_unknown` means *"this device may or may not be secure in this respect
  and I could not tell."* → UNKNOWN, lowers coverage, is a gap.
- `not_applicable` means *"this device has no such capability, so the question is
  meaningless."* → excluded from the denominator entirely.

A layer-2 access switch with no routing engine should not be scored against
routing-protocol authentication controls — and should not be given free credit
for them either.

---

## 4. The namespace

Ten top-level domains. The four control families the problem statement
explicitly names — **insecure protocols, cryptographic suites, granular ACLs,
administrative access logging** — are all first-class.

```
device.*        identity and physical characteristics
mgmt.*          management-plane access
auth.*          identity, authentication, authorisation
crypto.*        cryptographic posture
logging.*       audit and telemetry
time.*          time synchronisation
snmp.*          network management protocol
filter.*        access control and traffic policy
topology.*      interfaces, zones, routing
services.*      extensible capability surface
```

---

### 4.1 `device.*` — identity

Populated primarily from `show version` and `show inventory` artifacts, not from
the running configuration. Required for the report's mandated device
identification section.

| Path | Type | Notes |
|---|---|---|
| `device.hostname` | string | |
| `device.vendor` | enum | |
| `device.platform` | enum | `cisco_ios`, `cisco_iosxe`, `cisco_nxos`, `juniper_junos`, `fortios`, `panos`, `arista_eos`, `mikrotik_routeros`, `sonic`, `aws_sg`, … |
| `device.os_version` | version | Normalised, comparable |
| `device.model` | string | |
| `device.serials[]` | object[] | `{component, serial}` — chassis, line cards, power supplies |
| `device.role` | enum | `core`, `distribution`, `access`, `edge`, `firewall`, `management`, `lab` |
| `device.exposure` | enum | `internet_facing`, `dmz`, `internal`, `isolated` — **computed from the graph, not read from configuration** |
| `device.uptime_sec` | integer | |
| `device.config_export_mode` | enum | `verbose`, `terse`, `unknown` — drives the completeness warning |

---

### 4.2 `mgmt.*` — management plane

The largest and most universally applicable domain. Approximately 60% of any
network benchmark concerns this area, and it is where breaches begin.

| Path | Type | Notes |
|---|---|---|
| `mgmt.protocols.<name>.enabled` | boolean | `telnet`, `ssh`, `http`, `https`, `ftp`, `tftp`, `snmp`, `netconf`, `restconf`, `api` |
| `mgmt.protocols.<name>.port` | integer | |
| `mgmt.protocols.<name>.version` | integer | |
| `mgmt.ssh.version` | integer | 1 or 2 |
| `mgmt.ssh.max_auth_tries` | integer | |
| `mgmt.ssh.rekey_interval_sec` | integer | |
| `mgmt.ssh.host_key_bits` | integer | |
| `mgmt.session.idle_timeout_sec` | integer | **Always seconds.** Platforms express minutes, seconds, or both |
| `mgmt.session.absolute_timeout_sec` | integer | |
| `mgmt.session.max_concurrent` | integer | |
| `mgmt.source_restriction.configured` | boolean | Is management access restricted by source address at all |
| `mgmt.source_restriction.allowed_sources[]` | cidr[] | |
| `mgmt.source_restriction.permits_any` | boolean | Derived — a critical convenience fact |
| `mgmt.banner.login_present` | boolean | |
| `mgmt.banner.motd_present` | boolean | |
| `mgmt.console.timeout_sec` | integer | |
| `mgmt.aux.enabled` | boolean | |

**Note on `mgmt.protocols.<name>`:** the `<name>` segment is an open enumeration
drawn from the schema registry. When a platform introduces a management protocol
nobody has seen before, it is registered here rather than discarded — and
immediately becomes visible to property-derived controls (§6).

---

### 4.3 `auth.*` — identity and authentication

| Path | Type | Notes |
|---|---|---|
| `auth.local_users[]` | object[] | `{name, privilege_level, storage_type, reversible, has_password, ssh_key_present}` |
| `auth.local_users[].storage_type` | enum | `plaintext`, `reversible`, `md5`, `pbkdf2`, `scrypt`, `bcrypt`, `unknown` |
| `auth.local_users[].reversible` | boolean | **Derived.** Cisco type 7 is reversible; type 8/9 are not. This distinction is itself a control |
| `auth.default_credentials_present` | boolean | Derived — a known-default username or community exists |
| `auth.central.configured` | boolean | |
| `auth.central.servers[]` | object[] | `{protocol, host, port, encrypted, shared_secret_present}` — protocol ∈ `radius`, `tacacs+`, `ldap`, `kerberos` |
| `auth.central.local_fallback` | boolean | Is a local account usable if the central server is unreachable |
| `auth.central.accounting_enabled` | boolean | |
| `auth.password_policy.min_length` | integer | |
| `auth.password_policy.complexity_required` | boolean | |
| `auth.password_policy.expiry_days` | integer | |
| `auth.password_policy.history_count` | integer | |
| `auth.password_policy.lockout_threshold` | integer | |
| `auth.privilege_levels_customised` | boolean | |
| `auth.mfa.enabled` | boolean | |

---

### 4.4 `crypto.*` — cryptographic posture

Explicitly named in the problem statement (*"enforcing strong cryptographic
suites"*). Harder than it appears: algorithm lists must be canonicalised so that
comparison against an allow/deny set does not require per-platform logic.

| Path | Type | Notes |
|---|---|---|
| `crypto.ssh.kex_algorithms[]` | algo[] | Canonical identifiers |
| `crypto.ssh.ciphers[]` | algo[] | |
| `crypto.ssh.macs[]` | algo[] | |
| `crypto.ssh.host_key_algorithms[]` | algo[] | |
| `crypto.tls.versions[]` | enum[] | `ssl3`, `tls1.0`, `tls1.1`, `tls1.2`, `tls1.3` |
| `crypto.tls.ciphers[]` | algo[] | |
| `crypto.ipsec.ike_proposals[]` | object[] | `{version, encryption, integrity, dh_group, lifetime_sec}` |
| `crypto.ipsec.esp_proposals[]` | object[] | |
| `crypto.certificates[]` | object[] | `{subject, issuer, key_bits, signature_algorithm, not_after, self_signed}` |
| `crypto.weak_algorithms_present[]` | algo[] | **Derived** — the intersection of configured algorithms with a maintained weak-algorithm list |
| `crypto.fips_mode` | boolean | |

**Algorithm canonicalisation is mandatory.** `aes128-cbc`, `AES-128-CBC` and
`aes-128-cbc` are the same algorithm. Without canonicalisation, control
assertions become per-platform string matching, which defeats the purpose of the
schema.

---

### 4.5 `logging.*` — audit and telemetry

Explicitly named in the problem statement (*"logging all administrative
access"*).

| Path | Type | Notes |
|---|---|---|
| `logging.enabled` | boolean | |
| `logging.remote_servers[]` | object[] | `{host, protocol, port, transport_encrypted}` |
| `logging.remote_configured` | boolean | Derived |
| `logging.severity_level` | enum | Normalised to syslog severities |
| `logging.admin_commands_logged` | boolean | Command accounting |
| `logging.auth_events_logged` | boolean | |
| `logging.config_changes_logged` | boolean | |
| `logging.timestamps_enabled` | boolean | |
| `logging.timestamps_include_timezone` | boolean | |
| `logging.local_buffer_bytes` | integer | |
| `logging.source_interface_set` | boolean | |

---

### 4.6 `time.*` — time synchronisation

Small but disproportionately important: log timestamps are worthless without
trustworthy time, which makes this a prerequisite for the entire logging family.

| Path | Type |
|---|---|
| `time.ntp.enabled` | boolean |
| `time.ntp.servers[]` | object[] — `{host, authenticated, preferred}` |
| `time.ntp.authentication_configured` | boolean |
| `time.ntp.server_count` | integer |
| `time.timezone` | string |
| `time.clock_source` | enum |

---

### 4.7 `snmp.*` — network management protocol

| Path | Type | Notes |
|---|---|---|
| `snmp.enabled` | boolean | |
| `snmp.versions[]` | enum[] | `v1`, `v2c`, `v3` |
| `snmp.communities[]` | object[] | `{name, access, acl_applied, is_default}` |
| `snmp.communities[].is_default` | boolean | **Derived** — `public`, `private`, `cisco` and similar |
| `snmp.v3_users[]` | object[] | `{name, auth_protocol, priv_protocol, security_level}` |
| `snmp.traps_enabled` | boolean | |
| `snmp.trap_receivers[]` | object[] | |
| `snmp.write_access_present` | boolean | Derived |

---

### 4.8 `filter.*` — access control

Explicitly named in the problem statement (*"configuring granular ACLs"*). This
domain feeds the configuration graph.

| Path | Type | Notes |
|---|---|---|
| `filter.rulesets[]` | object[] | `{name, type, rule_count}` |
| `filter.rules[]` | object[] | `{ruleset, position, action, source, destination, service, protocol, logged, enabled, description}` |
| `filter.rules[].source` | ref | Reference to an address object or literal CIDR |
| `filter.objects[]` | object[] | `{name, type, members[]}` — members may reference other objects |
| `filter.objects[].expanded[]` | cidr[] | **Derived** — transitively flattened membership |
| `filter.applied[]` | object[] | `{ruleset, interface, direction}` |
| `filter.permits_any_any[]` | ref[] | Derived — rules permitting all sources to all destinations |
| `filter.unlogged_deny_present` | boolean | Derived |
| `filter.shadowed_rules[]` | ref[] | Derived — rules unreachable because an earlier rule matches first |
| `filter.default_action` | enum | `permit`, `deny`, `unknown` |

**`filter.objects[].expanded[]` is the fact that catches one of the most common
real-world defects:** a group named `Trusted-Admins` that transitively contains
`0.0.0.0/0` three nestings down. Nobody notices manually because expansion
requires following references.

---

### 4.9 `topology.*` — interfaces, zones, routing

Primarily consumed by the graph builder and by exposure classification.

| Path | Type | Notes |
|---|---|---|
| `topology.interfaces[]` | object[] | `{name, enabled, type, addresses[], zone, vlan, description, unused}` |
| `topology.interfaces[].unused` | boolean | Derived — enabled but unconfigured |
| `topology.zones[]` | object[] | `{name, trust_level, interfaces[]}` |
| `topology.vlans[]` | object[] | |
| `topology.routes[]` | object[] | `{destination, next_hop, interface, protocol, metric}` |
| `topology.default_route_present` | boolean | |
| `topology.routing_protocols[]` | object[] | `{protocol, authenticated, auth_type}` |
| `topology.vrfs[]` | object[] | |
| `topology.discovery_protocols[]` | object[] | `{protocol, enabled, interfaces[]}` — CDP, LLDP |

---

### 4.10 `services.*` — the extensible capability surface

**This domain is what allows the model to represent things nobody has thought of
yet.** When a platform exposes a capability that fits no existing domain — a
proprietary management protocol, a container runtime, a programmable data plane —
it is registered here with its security properties.

| Path | Type | Notes |
|---|---|---|
| `services.<name>.enabled` | boolean | |
| `services.<name>.port` | integer | |
| `services.<name>.properties` | object | The universal security property set (§6) |
| `services.<name>.classification` | enum | `known_category`, `novel_instance`, `unclassified` |
| `services.<name>.assessed_by[]` | ref[] | Which controls, if any, evaluate this capability |

A service with an empty `assessed_by[]` is **unaudited surface**, and triggers
both a finding and scope contamination of related control families.

---

## 5. Derived facts

Some facts are not extracted but **computed** from other facts. They are marked
as derived and record which facts they depend upon.

| Derived fact | Computed from | Why it exists |
|---|---|---|
| `device.exposure` | Graph position, zones, default route | Drives severity weighting |
| `auth.local_users[].reversible` | `storage_type` | Turns a platform detail into a portable assertion |
| `filter.objects[].expanded[]` | Transitive object membership | Catches nested over-broad groups |
| `crypto.weak_algorithms_present[]` | Configured algorithms ∩ weak list | Keeps the weak-algorithm list maintainable as data |
| `snmp.communities[].is_default` | Community name ∩ known-default list | |
| `mgmt.source_restriction.permits_any` | Restriction rules | Frequently-used convenience fact |
| `filter.shadowed_rules[]` | Rule ordering analysis | Finds dead policy |
| `topology.interfaces[].unused` | Interface state and configuration | Unused-but-enabled ports are an access vector |

Derived facts inherit the **weakest provenance** of their inputs. If any
contributing fact is `default_unknown`, the derived fact is `default_unknown`.
Uncertainty propagates rather than being laundered.

---

## 6. Universal security properties

Every capability — known or novel — can be characterised by a small, finite,
technology-independent property set. This is what allows controls to apply to
features that did not exist when the control was written.

| Property | Question | Control family it triggers |
|---|---|---|
| `listens` | Accepts network connections? | Source restriction; disable if unused |
| `authenticates` | Accepts credentials? | No defaults; no reversible storage |
| `executes` | Can run code? | Source verification; execution logging |
| `mutates` | Can change device configuration or behaviour? | Authentication required; audit record required |
| `transports` | Moves data across the network? | Encryption in transit |
| `persists` | Stores secrets or state? | Protection at rest |
| `observable` | Generates security-relevant logs? | Remote logging required |
| `default_on` | Enabled out of the box? | Explicit justification required |

**These properties were true of Telnet in 1985 and will be true of whatever ships
in 2032.** They are the durable answer to the problem statement's instruction
that the system operate *"regardless of vendor or market segment."*

### 6.1 Worked example — a genuinely novel capability

A white-box switch runs a container runtime on the switch itself. No compliance
framework anywhere has a control for this.

```yaml
services.container_runtime:
  enabled: true
  classification: unclassified
  properties:
    listens:     true     # exposes a control socket
    executes:    true     # runs arbitrary images
    mutates:     true     # containers can alter forwarding behaviour
    transports:  true     # pulls images from a remote registry
    default_on:  true
  assessed_by: []         # ← no control covers this
```

Property-derived controls immediately produce four legitimate findings —
image source verification, registry authentication, execution logging, and
default-on justification — for a capability with zero benchmark coverage on
Earth.

And because `assessed_by` is empty, the capability is reported as unaudited
surface and contaminates the scope of related passing controls.

---

## 7. Schema registry and extensibility

The namespace is not a fixed structure compiled into the product. It is a
**registry** — data, versioned, extensible at runtime.

```yaml
fact_definition:
  path:        mgmt.protocols.winbox.enabled
  type:        boolean
  category:    management_plane
  description: "Proprietary MikroTik management protocol"
  registered_by: r.kulkarni
  registered_at: 2026-09-14T10:22:00Z
  introduced_by_platform: mikrotik_routeros
  properties:  { listens: true, authenticates: true, mutates: true }
```

Three consequences:

1. Teaching a platform that introduces a new concept does not require a code
   change — satisfying *"without requiring backend code redeployment"*
2. Newly registered facts with no controls referencing them are automatically
   surfaced as unaudited surface
3. The registry itself is versioned, so a historical campaign can be reproduced
   against the schema as it existed then

---

## 8. Normalisation rules

Non-negotiable, because they are what make controls portable.

| Rule | Detail |
|---|---|
| **Time** | Always seconds. Platforms express minutes, seconds, or `mm ss` pairs |
| **Sizes** | Always bytes |
| **Booleans** | Always positive assertion. `mgmt.protocols.telnet.enabled = true` means Telnet is on, regardless of whether the platform expressed it as `transport input telnet` or `set admin-telnet enable` or `disabled=no` |
| **Algorithms** | Canonical lowercase identifiers from a maintained equivalence table |
| **Addresses** | CIDR notation. Wildcard masks converted |
| **Severity** | Control-defined; platform severities mapped, never inherited raw |
| **Versions** | Structured and comparable, not strings |
| **Enumerations** | Closed where the domain is closed (TLS versions); open with registry where it is not (management protocols) |

### 8.1 The polarity rule

The most dangerous normalisation, and the one that must never be silent.

```
Cisco     transport input ssh         → telnet.enabled = FALSE  (absence from list)
Cisco     transport input telnet ssh  → telnet.enabled = TRUE
Fortinet  set admin-telnet disable    → telnet.enabled = FALSE  (negated flag)
MikroTik  set telnet disabled=no      → telnet.enabled = TRUE   (double negative)
Juniper   delete system services telnet → telnet.enabled = FALSE
```

**Invert any one of these and a wide-open device is certified compliant.** This
is the highest-consequence error class in the entire system, which is why the
learning subsystem surfaces polarity as a separate, explicit confirmation
([FR-LRN-007](03-functional-requirements.md)) rather than inferring it silently.

---

## 9. Worked example — one device, end to end

Input, from the configuration in [01-domain-primer.md](01-domain-primer.md):

```
username admin privilege 15 password 7 0822455D0A16
line vty 0 4
 transport input telnet ssh
 exec-timeout 0 0
snmp-server community public RO
```

Resulting facts:

```yaml
- path: auth.local_users[0].name
  value: "admin"
  provenance: { source: explicit, lines: [6], extractor: cisco_ios.username@v4 }

- path: auth.local_users[0].privilege_level
  value: 15
  provenance: { source: explicit, lines: [6], extractor: cisco_ios.username@v4 }

- path: auth.local_users[0].storage_type
  value: "reversible"
  provenance: { source: explicit, lines: [6], extractor: cisco_ios.username@v4 }

- path: auth.local_users[0].reversible
  value: true
  provenance: { source: derived, depends_on: [auth.local_users[0].storage_type] }

- path: mgmt.protocols.telnet.enabled
  value: true
  provenance: { source: explicit, lines: [21], extractor: cisco_ios.vty.transport_input@v7 }

- path: mgmt.protocols.ssh.enabled
  value: true
  provenance: { source: explicit, lines: [21], extractor: cisco_ios.vty.transport_input@v7 }

- path: mgmt.session.idle_timeout_sec
  value: 0
  provenance: { source: explicit, lines: [22], extractor: cisco_ios.vty.exec_timeout@v3 }

- path: snmp.communities[0].name
  value: "public"
  provenance: { source: explicit, lines: [24], extractor: cisco_ios.snmp.community@v2 }

- path: snmp.communities[0].is_default
  value: true
  provenance: { source: derived, depends_on: [snmp.communities[0].name] }

- path: mgmt.source_restriction.configured
  value: false
  provenance: { source: default_known, platform: cisco_ios, version_range: "*" }

- path: crypto.ssh.ciphers
  value: null
  provenance: { source: default_unknown }      # ← forces UNKNOWN downstream
```

Note the last two. `mgmt.source_restriction.configured` resolves confidently
because a verified default exists. `crypto.ssh.ciphers` does not, so it produces
`default_unknown` — and every cipher-suite control returns UNKNOWN rather than
silently passing.

**That single distinction is the difference between an honest audit and a
dangerous one.**

---

## 10. Anti-patterns

Ways this schema can be got wrong, in order of how expensive they are to fix
later.

| Anti-pattern | Consequence |
|---|---|
| Vendor terminology in fact names | Controls stop being portable; the entire architecture collapses into a per-vendor tool |
| Values without provenance | Findings become unusable as audit evidence |
| Treating absence as `false` | Silently passes every device that omits a setting — the exact failure this product exists to prevent |
| Raw strings for algorithm lists | Control assertions degenerate into per-platform string matching |
| A closed, compiled schema | Cannot represent novel capabilities; violates the runtime-extensibility requirement |
| Conflating `not_applicable` with `default_unknown` | Corrupts the compliance denominator in both directions |
| Laundering uncertainty through derived facts | An uncertain input silently becomes a confident output |
| Silent polarity inference | The highest-consequence error class in the system |

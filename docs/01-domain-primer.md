# 01 · Domain Primer

> **Audience:** team members with a software, ML, or data background and no
> networking experience. This document builds the domain from first principles.
> Nothing here assumes prior networking knowledge.

---

## 1. What is a network device?

Three kinds of box, all of which are computers.

**A switch** connects machines within a building. It is the rack-mounted unit
with 24 or 48 ethernet ports. Every desk, printer, camera and wireless access
point plugs into one. Its job: get data from machine A to machine B on the same
floor.

**A router** connects *different* networks. The campus to the internet. The Delhi
office to the Mumbai office. Its job: decide which way to send a packet that is
not local.

**A firewall** sits at a boundary and decides what traffic may pass.
*"Guest wireless may reach the internet but not the finance servers."* It is a
policy enforcement point.

The essential point: **these are computers.** Each has a processor, memory,
storage and an operating system. Cisco's is called IOS. Juniper's is JunOS.
Fortinet's is FortiOS. Palo Alto's is PAN-OS. You connect to them over the
network, receive a command prompt, and type commands.

A mid-sized organisation runs 200–2,000 of them. A bank or a government
department runs tens of thousands.

---

## 2. What is a configuration file?

When commands are typed into one of these devices, the resulting state is held in
memory as a text document called the **running configuration**. It can be dumped
by typing `show running-config`.

**That text file is the device's entire behaviour.** Who may log in, what traffic
passes, what cryptography is used, where logs are sent — all of it.

### 2.1 A real example

A Cisco switch configuration, abridged. Read it before continuing; it is
dissected immediately below.

```
!
version 15.2
service password-encryption
hostname CORE-SW-01
!
enable secret 5 $1$mERr$hx5rVt7rPNoS4wqbXKX7m0
username admin privilege 15 password 7 0822455D0A16
!
aaa new-model
aaa authentication login default group tacacs+ local
!
ip domain-name corp.example.com
ip ssh version 2
!
interface GigabitEthernet0/1
 description Uplink to Router
 switchport mode trunk
 no shutdown
!
interface GigabitEthernet0/24
 description Guest WiFi AP
 switchport access vlan 40
 no shutdown
!
interface Vlan1
 ip address 10.0.0.5 255.255.255.0
!
line vty 0 4
 transport input telnet ssh
 exec-timeout 0 0
 login local
!
snmp-server community public RO
!
logging host 10.0.0.200
ntp server 10.0.0.201
!
end
```

That is roughly 30 lines. A production configuration is 2,000–15,000 lines. A
large firewall configuration can exceed 100,000.

### 2.2 What is wrong with it

Five serious security defects. None are obvious without platform knowledge.

**1 · `username admin privilege 15 password 7 0822455D0A16`**

`password 7` is Cisco's "type 7" encoding. It is not encryption — it is a
Vigenère-style XOR with a publicly known key, designed in the 1990s to prevent
shoulder-surfing. It is reversible in about two seconds; public web tools decode
it. `privilege 15` means full administrative control.

This line is therefore: **full administrative credentials, stored reversibly.**

**2 · `service password-encryption`**

A subtle trap. This line *sounds* like a security feature — it is the setting
that produces type 7 encoding. It therefore creates false confidence: an auditor
unfamiliar with the platform sees "password-encryption" and ticks a box. It is a
weak control that resembles a strong one.

**3 · `transport input telnet ssh`**

This sits inside the `line vty 0 4` block, which governs remote login sessions.
It permits both Telnet and SSH.

**Telnet transmits everything, including the password, as plaintext across the
network.** Anyone able to observe the traffic obtains the credentials. It has
been considered unacceptable since roughly 1995 and remains ubiquitous.

**4 · `exec-timeout 0 0`**

Session idle timeout of zero means *never expire*. An administrator logs in, is
distracted, walks away — the authenticated session persists indefinitely.

**5 · `snmp-server community public RO`**

SNMP is a management protocol for reading device state. The "community string" is
its password. `public` is the factory default and is universally known — the
equivalent of leaving the password as `password`. `RO` grants read-only access,
which frequently includes reading the configuration itself.

### 2.3 How these compose into a breach

This compositional property is central to the entire problem.

1. An attacker joins the guest wireless network — the segment attached to
   `GigabitEthernet0/24`. Trivial; it is guest wireless.
2. They scan and find a device at `10.0.0.5` answering SNMP with the community
   string `public`.
3. They read the device configuration over SNMP, obtaining
   `password 7 0822455D0A16`.
4. They decode the type 7 password. Two seconds.
5. They connect over **Telnet** — permitted by defect 3 — as `admin` with
   `privilege 15`.
6. They now fully control a core switch. From there: mirror all traffic to
   themselves, create a VLAN bypassing the firewall, disable logging to remain
   unseen, and pivot deeper into the internal network.

**No single line above is individually catastrophic.** Guest wireless is normal.
Read-only SNMP is normal. Telnet is bad but requires credentials. Type 7 is bad
but requires the configuration. It is the *chain* that is fatal.

This is why relationship analysis — not just line-level checking — matters.

---

## 3. The rulebooks

Because these mistakes are common and well understood, standards bodies publish
hardening guides. The problem statement names four, and they operate at very
different levels of abstraction.

### 3.1 CIS Benchmarks

Published by the Center for Internet Security. One document per platform;
*CIS Cisco IOS 15 Benchmark* runs to several hundred pages. It is a numbered list
of recommendations, each structured as:

> **1.2.4 — Set `transport input ssh` for `line vty` connections**
> **Rationale:** Telnet transmits credentials in cleartext
> **Audit:** run `show run | sec vty` and verify `transport input ssh`
> **Remediation:** `line vty 0 15` then `transport input ssh`
> **Default Value:** `transport input all`
> **Severity:** High

Note the shape: **a checkable assertion plus a fix plus a documented default.**
Essentially a test case with a suggested patch. There are 100–200 per platform.

Free with registration. **Redistribution of the document text is restricted** —
the platform implements the recommendations and cites the identifiers, but does
not reproduce CIS content.

### 3.2 DISA STIGs

*Security Technical Implementation Guides*, published by the US Defense
Information Systems Agency. Similar in spirit to CIS but more prescriptive, and
critically, **distributed as machine-readable XML** in the XCCDF format. Each
item carries a vulnerability identifier such as `V-216644`, a severity category
(CAT I / II / III), check text and fix text.

**Freely available**, which matters enormously — this is the best import source.

### 3.3 NIST SP 800-53

A different level of abstraction entirely. A catalogue of roughly 1,000 security
controls for US federal systems, organised into families:

- **AC** — Access Control (e.g. `AC-17`: Remote Access)
- **AU** — Audit and Accountability
- **IA** — Identification and Authentication
- **SC** — System and Communications Protection

These are **policy statements, not device settings**. `AC-17` requires that
remote access be authorised, monitored and cryptographically protected. It says
nothing about Cisco syntax.

Published as machine-readable OSCAL JSON, freely available.

### 3.4 ISO/IEC 27001

Higher still — an international standard for operating an information security
*management system*. Largely concerned with process and governance. Its Annex A
controls are one or two sentences each.

**A paid standard. Its text cannot be legally redistributed.** The platform can
reference control identifiers only.

### 3.5 The abstraction stack

```
ISO 27001      "Access to networks shall be controlled"      ← governance
NIST 800-53    AC-17: Remote Access                          ← policy
CIS / STIG     transport input ssh on line vty               ← device-specific
Configuration  transport input telnet ssh                    ← evidence
```

One piece of evidence at the bottom satisfies or violates requirements at every
level above it.

**This is why multi-framework support is largely a mapping exercise rather than
four separate engines** — you check the concrete thing once and report it upward
against four vocabularies.

---

## 4. Why this is hard

If there were one vendor, this would be a weekend project. The difficulty lies
entirely elsewhere. Five distinct problems.

### 4.1 Every platform speaks a different language

The **identical** security requirement — *"disable Telnet, use SSH only"* — across
six platforms:

**Cisco IOS** — indentation hierarchy:
```
line vty 0 15
 transport input ssh
```

**Juniper JunOS** (set format) — flat, each line a complete path:
```
delete system services telnet
set system services ssh protocol-version v2
```

**Juniper JunOS** (curly format) — *the same device*, different display mode:
```
system {
    services {
        ssh { protocol-version v2; }
    }
}
```

**Fortinet FortiOS** — block keywords:
```
config system global
    set admin-telnet disable
end
```

**Palo Alto PAN-OS** — XML:
```xml
<deviceconfig><system><service>
  <disable-telnet>yes</disable-telnet>
</service></system></deviceconfig>
```

**MikroTik RouterOS** — path headers with key/value pairs:
```
/ip service
set telnet disabled=yes
```

Six syntaxes and — more importantly — **six structural paradigms**: indentation,
flat paths, braces, block keywords, XML, key-value.

The semantics do not even align cleanly. Cisco expresses it as *"the permitted
protocol list is [ssh]"*; Fortinet as *"the telnet flag is disabled."* Positive
enumeration versus negative flag. The neutral model must absorb both.

### 4.2 Absence carries meaning

This is the problem that most surprises people from a data background.

If `service password-encryption` does not appear in a Cisco configuration, it is
**off**. If `ip ssh version 2` does not appear, some releases accept version 1.

**You cannot simply search for bad patterns.** You must know the default value
for every setting, on every platform, at every firmware version, and reason about
what is *not written*.

In data terms: the input is not a complete feature vector. It is a sparse
representation in which missing features carry platform-specific,
version-specific defaults that must be looked up. A naïve "search for violations"
approach silently passes every device that omits the setting entirely — which is
the *worst* case, not a safe one.

Worse still: for a platform the system has never seen, there is no defaults
table. Silence then has three possible meanings — feature at default, feature
unconfigured, or feature nonexistent — with identical evidence and completely
different security consequences.

### 4.3 The same words mean different things in different places

In the example configuration, `no shutdown` appears twice under two different
interfaces. In a real configuration it appears fifty times. So do `description`,
`login`, `permit`, `set`.

**A line has no meaning outside its position in the hierarchy.**

Consequence: line-level pattern matching is fundamentally insufficient. Structure
must be parsed before interpretation. This is why naïve regular expressions fail
on real configurations, and why naïve language-model prompting fails differently
— it reads the structure correctly sometimes and not others.

### 4.4 The effective configuration is not the configuration

The nastiest problem, and the one almost nobody anticipates.

In real enterprise deployments a device's actual behaviour is a **merge** of
several layers:

- **Palo Alto with Panorama:** shared → device-group → template stack → local
  override. The rule being audited may be inherited three layers away and absent
  from the device's own file entirely.
- **Juniper:** `groups` and `apply-groups` inheritance.
- **Cisco:** overlapping ranges. `line vty 0 4` and `line vty 0 15` both exist
  and overlap on lines 0–4, with non-obvious resolution rules.

The text is not the truth. The effective configuration must be *computed*. A tool
that skips this produces confidently wrong answers on exactly the large
enterprise networks that matter most.

### 4.5 The landscape does not hold still

New platforms appear continuously. Cloud providers have their own security-group
formats. White-box switches run open network operating systems. AI datacentre
fabrics use different hardware.

Any tool with hardcoded parsers becomes obsolete on a rolling basis.

---

## 5. What auditing looks like today

An auditor receives a list of 400 devices. For each:

1. Obtain the configuration — request it from the network team, or connect and
   run `show running-config`
2. Open the CIS Benchmark PDF for that exact platform and version
3. Work through ~150 recommendations
4. For each, search the configuration and determine pass or fail — including
   reasoning about platform defaults for anything absent
5. Record the result in a spreadsheet
6. Repeat, 400 times

Done properly: 30–90 minutes per device. **400 devices is three to six months of
full-time work** — during which the network changes, so the earliest results are
stale before the last are written.

Consequently it is not done properly.

---

## 6. Mapping the problem onto familiar concepts

For team members from a machine learning or data background:

| This domain | Familiar equivalent |
|---|---|
| Configuration → neutral model | Information extraction / structured prediction — named entity recognition plus relation extraction, over a formal language |
| Vendor syntactic diversity | Multilingual NLP — identical semantics, different surface forms. The neutral schema is an interlingua |
| Training interface | Active learning with human annotation, updating online |
| Unseen vendor | Zero-shot / few-shot domain transfer |
| "Cannot determine" verdict | Selective prediction / abstention — knowing when not to answer |
| Fleet outlier detection | Unsupervised anomaly detection |
| The compliance check itself | **Not machine learning** — symbolic reasoning over extracted facts |

That final row is the important one.

**This is a neurosymbolic system.** Neural components perform perception —
turning messy text into structured facts. A symbolic engine performs reasoning —
deciding pass or fail. The schema is the interface between them.

### 6.1 The constraint that inverts normal ML instincts

> **92% accuracy is not a good result here. It is a disqualifying one.**

In most applications a false positive is an annoyance and a false negative is a
miss. Here:

- A **false negative** means the system certified a vulnerable device as secure.
  If a breach follows, the tool contributed to it.
- A **false positive** means an administrator chases a phantom, finds nothing,
  and stops trusting the tool. Trust is lost permanently after roughly two such
  events. There is no *"the model is usually right"* in security tooling.

This is precisely why the architecture removes machine learning from the decision
path. The model helps *build* the rule; the rule makes the call. Adaptability
comes from the learning component, reliability from the symbolic one, and neither
compromises the other.

That trade-off is the genuinely interesting engineering problem in this product —
because the naïve ML solution is measurably *worse* than a simple deterministic
one, and obtaining the benefits of learning without its liabilities is the whole
design challenge.

---

## 7. The domain's one gift

A structural advantage worth understanding, because the learning system depends
on it.

**Networking vocabulary is standardised even where syntax is not.**

Every vendor on earth writes `telnet`, `ssh`, `snmp`, `ntp`, `syslog`, `radius`,
`tacacs`, `bgp`, `ospf`. They have no choice — these are interoperability
protocols defined in published RFCs. Vendors differentiate on syntax, never on
protocol names.

Therefore **the vocabulary shared across all these "languages" is precisely the
security-relevant vocabulary.** A system that has learned what `telnet` means on
six platforms can make a strong, well-founded guess about the seventh.

This is what makes cross-vendor transfer work at all, and it is the foundation of
the learning system described in [08-learning-system.md](08-learning-system.md).

---

## 8. Compressed mental model

1. Network devices are computers whose entire behaviour is one large text file.
2. That file is written in a vendor-specific language, with position-dependent
   meaning, where absence carries information, and where the visible text may not
   be the effective configuration.
3. Standards bodies publish rulebooks specifying what the file should contain.
   Some are concrete and device-specific; some are abstract policy. They require
   mapping between them.
4. Checking one file against one rulebook by hand takes about an hour.
   Organisations hold thousands of files. So it does not get done.
5. Existing tools work only for vendors somebody already programmed in, and
   adding a vendor requires an engineer and a release cycle.
6. **The ask:** a system that a network administrator can *teach* a new vendor in
   minutes without code — and that then audits deterministically enough to be
   trusted with a security verdict.

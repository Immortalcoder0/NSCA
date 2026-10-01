# Corpus — provenance and review notes

Partial seed for the TRD-00 §8.2 corpus requirement (≥5 platforms, ≥3
structural paradigms, 200 configurations, ≥60% real production). **This is
not that corpus** — it's 34 real-syntax sample files pulled and reviewed on
2026-09-01, a starting point. The 200-config/production-share target
remains unmet; sourcing/sanitizing the rest is still an open task (flagged
in [backend-01-assessment-engine.md](../../../../plans/backend-01-assessment-engine.md)
§8).

## File counts

| Folder | Count | Status |
|---|---|---|
| `cisco_ios/` | 6 | known (taught) |
| `juniper/` | 6 | known (taught) |
| `fortios/` | 5 | known (taught) |
| `panos/` | 4 | known (taught) — see paradigm-mismatch note below |
| `mikrotik/` | 5 | known (taught) |
| `_untaught/arista_eos/` | 5 | unknown (untaught) |
| `_untaught/huawei_vrp/` | 3 | unknown (untaught) |
| **Total** | **34** | |

## Sources

**`cisco_ios/`, `juniper/`, `fortios/`, `panos/`, `_untaught/arista_eos/`**
— [batfish/batfish](https://github.com/batfish/batfish), Apache-2.0,
commit `6124492e1fd3` (2026-09-01), from
`projects/batfish/src/test/resources/org/batfish/grammar/<vendor>/testconfigs/`
(and `.../vendor/arista/grammar/testconfigs/` for Arista). These are
Batfish's own grammar-parser test fixtures — several carry a
`RANCID-CONTENT-TYPE` header, indicating derivation from real
RANCID-backed device backups, sanitized (fake passwords/keys, RFC5737/
private addressing). Selected for domain diversity (mgmt/auth, logging,
SNMP, NTP, filtering, crypto) rather than just the largest files.

**`mikrotik/`** — batfish does not support MikroTik RouterOS either.
Pulled from [maxslug/mikrotik_maxslug](https://github.com/maxslug/mikrotik_maxslug)
(CC0-1.0 — public domain, no attribution required, 81 stars), a real home
network's `/export` output across 6 devices (1 router + 2 switches + 3
APs), sanitized by the author (fake MACs/keys still marked as templates in
comments). Picked `mikro1.rsc` (the main router — richest: `/ip service`,
`/ip ssh`, `/ip firewall filter`, `/user group` policy), `sw1.rsc`,
`sw2.rsc` (switches), `wap1.rsc`, `wap2.rsc` (APs; skipped `wap3.rsc` as a
near-duplicate of wap1/wap2 from the same template). This is the highest-
confidence source of the four pulled today — real network, real
complexity, CC0-clear.

**`_untaught/huawei_vrp/`** — batfish does not support Huawei VRP.
Pulled instead from
[osh0678/gns3-multivendor-network-test](https://github.com/osh0678/gns3-multivendor-network-test)
(no license file, 0 stars — a personal GNS3 lab repo, not a vetted
project). Verified as genuine, unmodified VRP CLI syntax (`system-view`,
`sysname`, `vlan batch`, `port link-type trunk`, etc.) generated from a
real GNS3 lab, not hand-typed. **Limitation, flagged not hidden**: these
three files are topology-only (VLANs/interfaces/routing) — no
auth/SNMP/ACL/logging content. Good for proving VRP's structural paradigm
and seeding fingerprint signatures; weak for exercising the security
baseline domains. Searched the same repo for aaa/snmp/acl content and
found none.

## Review notes / findings

- **PAN-OS files are set-format, not XML.** Our current `panos.yaml`
  rulepack is wired to the `xml` paradigm (lxml). These 4 files
  (`ipsec-tunnel.cfg`, `ospf.cfg`, `log-settings-syslog.cfg`,
  `ntp-server.cfg`) are real `set ...` command syntax — the same format
  Juniper uses, and one PAN-OS devices genuinely export via
  `show config running` in set-mode. They will **not** parse under the
  current PAN-OS rulepack/paradigm assignment as-is. Real finding, not
  fixed here — either add a `panos_set`-paradigm rulepack variant, or
  treat these as a documented negative/future-work case.
- Some files are intentionally thin (single-directive): `aaaNewmodel.cfg`,
  `ntp-server.cfg` (3 lines), `log-settings-syslog.cfg` (5 lines). Genuine
  vendor syntax, useful for extractor unit coverage, not representative of
  a full device posture on their own.
- `fortios_ignored.cfg` is Batfish's own "constructs the parser
  deliberately skips" test file (real syntax, unusual selection of
  features: accprofile/admin/gui-dashboard) — kept for `config system
  admin` RBAC content, which no other pulled FortiOS file has.
- No files were rejected outright; all 29 passed review (real syntax,
  non-empty, not an API error page, no obviously fabricated/templated
  content).

## Layout

```
corpus/
├── cisco_ios/    juniper/    fortios/    panos/     — taught platforms
└── _untaught/
    ├── arista_eos/   — indentation paradigm, real "! device: ... EOS-x.x" fingerprint markers
    └── huawei_vrp/   — block/indentation-hybrid paradigm, topology-only content
```

`_untaught/` platforms have no rulepack/fingerprint signatures in
`knowledge/` — intended for the grammar-inference / live-teaching demo
path (`08-learning-system.md`), not for `assess_device`, which will raise
`NotImplementedError` on them today.

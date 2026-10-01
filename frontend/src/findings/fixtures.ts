import type { FindingModel, DisputeModel } from "./types";

/**
 * Fixture-fallback data (same pattern as `estate/fixtures.ts` /
 * `useEstateDevices.ts`): used when the real API is unreachable (offline
 * dev, or a test environment with no live backend) so the UI still renders
 * deterministically, and as the seed for component tests that render these
 * pages directly without mocking `fetch`. Never used to override a real,
 * successful API response.
 */
export const FINDINGS_FIXTURE: FindingModel[] = [
  {
    id: "F-2026Q3-000412",
    campaign_id: "CMP-2026Q3-001",
    device_id: "DEV-002",
    hostname: "CORE-SW-01",
    device_platform: "Cisco IOS-XE",
    control_id: "NSCA-MGMT-002",
    rule_id: "cis_ios_15_vty_telnet_disabled",
    title: "Plaintext management protocols enabled on VTY lines",
    description: "VTY lines permit unencrypted Telnet sessions which transmit credentials in cleartext over transit networks.",
    verdict: "FAIL",
    severity: {
      base: "HIGH",
      effective: "CRITICAL",
      reason: "device.exposure == internet_facing",
    },
    state: "Open",
    rulepack_trust_tier: "CERTIFIED",
    frameworks: [
      { framework: "cis", id: "CIS-IOS-1.2.4" },
      { framework: "nist", id: "NIST AC-17" },
      { framework: "stig", id: "STIG V-216644" },
      { framework: "iso", id: "ISO A.9.4.2" },
    ],
    evidence: [
      {
        artifact: "running-config.txt",
        lines: [140, 145],
        highlight: [143],
        excerpt: `line vty 0 4\n login local\n transport input telnet ssh\n exec-timeout 0 0\n!`,
      },
    ],
    attack_paths: ["AP-CORE-01"],
    created_at: "2026-08-28T12:00:00Z",
  },
  {
    id: "F-2026Q3-000413",
    campaign_id: "CMP-2026Q3-001",
    device_id: "DEV-001",
    hostname: "EDGE-FW-01",
    device_platform: "PAN-OS",
    control_id: "NSCA-MGMT-002",
    rule_id: "panos_mgmt_plaintext_disabled",
    title: "HTTP plaintext web interface permitted on management interface",
    description: "Cleartext HTTP interface is bound without mandatory HTTPS redirection.",
    verdict: "FAIL",
    severity: {
      base: "HIGH",
      effective: "CRITICAL",
      reason: "perimeter interface",
    },
    state: "Open",
    rulepack_trust_tier: "CERTIFIED",
    frameworks: [
      { framework: "cis", id: "CIS-PAN-1.1.2" },
      { framework: "nist", id: "NIST AC-17" },
    ],
    evidence: [
      {
        artifact: "running-config.xml",
        lines: [42, 46],
        highlight: [44],
        excerpt: `<system>\n  <service>\n    <http>yes</http>\n    <https>yes</https>\n  </service>\n</system>`,
      },
    ],
    attack_paths: ["AP-CORE-01"],
    created_at: "2026-08-28T12:05:00Z",
  },
  {
    id: "F-2026Q3-000518",
    campaign_id: "CMP-2026Q3-001",
    device_id: "DEV-002",
    hostname: "CORE-SW-01",
    device_platform: "Cisco IOS-XE",
    control_id: "NSCA-NET-004",
    rule_id: "cis_ios_15_acl_no_any_any",
    title: "Permissive wildcard rule in partner access ACL",
    description: "Extended access control list contains an overly broad 0.0.0.0/0 grant.",
    verdict: "FAIL",
    severity: {
      base: "HIGH",
      effective: "HIGH",
    },
    state: "Open",
    rulepack_trust_tier: "CERTIFIED",
    frameworks: [
      { framework: "cis", id: "CIS-IOS-3.1.2" },
      { framework: "nist", id: "NIST SC-7" },
    ],
    evidence: [
      {
        artifact: "running-config.txt",
        lines: [200, 204],
        highlight: [202],
        excerpt: `ip access-list extended outside-in\n permit tcp any host 10.40.7.19 eq 22\n permit ip any host 0.0.0.0/0\n!`,
      },
    ],
    attack_paths: ["AP-MGMT-03"],
    created_at: "2026-08-28T12:10:00Z",
  },
  {
    id: "F-2026Q3-000601",
    campaign_id: "CMP-2026Q3-001",
    device_id: "DEV-003",
    hostname: "BR-RTR-014",
    device_platform: "Cisco IOS",
    control_id: "NSCA-NTP-001",
    rule_id: "cisco_ios_ntp_auth_key",
    title: "NTP server authentication unconfigured",
    description: "NTP synchronization operates without cryptographic key authentication.",
    verdict: "FAIL",
    severity: {
      base: "MEDIUM",
      effective: "MEDIUM",
    },
    state: "Open",
    rulepack_trust_tier: "CERTIFIED",
    systemic_id: "SF-004",
    frameworks: [
      { framework: "cis", id: "CIS-IOS-2.1.1" },
      { framework: "stig", id: "STIG V-216500" },
    ],
    evidence: [
      {
        artifact: "terse-export.cfg",
        lines: [55, 58],
        highlight: [56],
        excerpt: `ntp server 10.10.1.5\n! no ntp authenticate`,
      },
    ],
    attack_paths: [],
    created_at: "2026-08-28T12:15:00Z",
  },
];

export const FINDING_DETAIL_FIXTURE: FindingModel = {
  ...FINDINGS_FIXTURE[0],
  device_platform: "Cisco IOS-XE 16.12.04",
  description:
    "VTY lines permit unencrypted Telnet sessions which transmit credentials in cleartext over transit networks. An adversary on the path can intercept management authentication tokens.",
  frameworks: [
    { framework: "cis", id: "CIS-IOS-1.2.4", version: "v4.1.0", category: "Management Services" },
    { framework: "nist", id: "NIST AC-17", revision: "Rev5", category: "Remote Access" },
    { framework: "stig", id: "STIG V-216644", release: "2026-01", category: "CAT I" },
    { framework: "iso", id: "ISO A.9.4.2", version: "2022", category: "Secure Log-on Procedures" },
  ],
};

export const DISPUTE_FIXTURE: DisputeModel = {
  dispute_id: "DSP-2026Q3-0089",
  finding_id: "F-2026Q3-000412",
  raised_by: "r.kulkarni (Network Admin)",
  created_at: "2026-08-28T14:30:00Z",
  type: "compensating_control",
  claim:
    "Perimeter firewall EDGE-FW-01 blocks Telnet (TCP/23) at the external boundary via security rule 'block-inbound-mgmt', making the internal VTY Telnet finding non-exploitable from outside.",
  verification: {
    result: "REFUTED",
    counterexample: {
      packet: {
        src: "198.51.100.14 (Partner VPN)",
        dst: "10.40.7.19 (CORE-SW-01)",
        dport: 23,
        protocol: "TCP",
      },
      path: [
        { node: "EDGE-FW-01", note: "Rule 14 'permit-partner-vpn' matches before rule 20 'block-inbound-mgmt'", action: "PERMIT" },
        { node: "DIST-SW-02", note: "Routed via VLAN 400", action: "FORWARD" },
        { node: "CORE-SW-01", note: "Telnet listener active on line vty 0 4", action: "ACCEPTED" },
      ],
    },
    assumptions: [
      "Based on 389 of 412 devices collected in campaign",
      "23 uncollected devices assumed non-filtering",
      "Partner VPN tunnel termination unencrypted inside perimeter",
    ],
    confidence: "high",
    reason: "A verified packet trajectory exists from Partner VPN that bypasses the general inbound block rule.",
  },
};

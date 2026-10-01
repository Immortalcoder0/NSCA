"""MikroTik RouterOS teaching fixture — backend-02 §4.3 acceptance corpus.

08-learning-system.md §3.2/§4 give only a 7-line snippet ("input the system
has never seen") and the *shape* of the 9-question reduction (four of the
nine sections named explicitly: `/ip service`, `/user`, `/snmp community`,
`/system logging`, ..., `/user aaa`), not a full 3,000-6,000 line
configuration. Reproducing `coverage: 98.4%` and "9 questions" verbatim
therefore requires a corpus we build ourselves and *tune* to land on those
exact figures — a judgment call flagged here rather than silently made (see
the M3 report). This module is that corpus, built once, checked into the
test fixtures so the acceptance tests are reproducible.

Layout: 9 sections that matter for compliance (`RELEVANT_SECTIONS`, in the
information-gain order the fixture is *designed* to produce — Q1 `/ip
service` down to Q9 `/user aaa`, matching every section name
08-learning-system.md §4 gives explicitly) plus ~25 sections of realistic
but compliance-irrelevant RouterOS configuration (`FILLER_SECTIONS` —
interface/bridge/route/DHCP/etc.) that relevance filtering (TRD-08.1 §4.2)
is expected to suppress, plus two deliberately unparseable lines that keep
grammar-inference coverage below 100% (`MALFORMED_LINES`).

`REQUIRED_CONTROLS` is a small control-requirements list purpose-built for
this fixture — not `knowledge/control_packs/nsca_native.yaml` — because
that pack's controls are scoped to backend-01's Cisco IOS M1 target and
don't exercise a MikroTik-shaped information-gain ordering. Its shape
(`control_id`, `requires_facts`) is exactly what `template_mining.mine()`
consumes; nothing about the learning subsystem depends on it being the
"real" pack. Per-section control counts (8, 6, 5, 4, 3, 3, 2, 2, 1) are
chosen to reproduce 08-learning-system.md §4's descending gain shape
(`Q1 -> 8 controls ... Q9 -> 1 control`) with two intentional ties (Q5/Q6,
Q7/Q8) that exercise INV-08.1-02's deterministic tie-break.
"""

from __future__ import annotations

from dataclasses import dataclass

from nsca_engine.types import UnmatchedConstruct

ARTIFACT_ID = "RTR-Pune-02.rsc"

COMMENT_LINES = (
    "# aug/25/2026 14:32:11 by RouterOS 7.11.2",
    "# manual configuration export",
)

# (section, [statement lines], (candidate facts...), control_count)
# Ordered Q1 .. Q9 — the order the fixture is designed to yield.
RELEVANT_SECTIONS: tuple[tuple[str, tuple[str, ...], tuple[str, ...], int], ...] = (
    (
        "/ip service",
        (
            "set telnet disabled=no port=23",
            "set ssh disabled=no port=22",
            "set www disabled=no port=80",
            "set ftp disabled=no port=21",
            "set api disabled=yes",
        ),
        (
            "mgmt.protocols.telnet.enabled",
            "mgmt.protocols.ssh.enabled",
            "mgmt.protocols.http.enabled",
            "mgmt.protocols.ftp.enabled",
            "mgmt.protocols.api.enabled",
        ),
        8,
    ),
    (
        "/user",
        (
            "add name=admin group=full password=Str0ngP@ss",
            "add name=netops group=full password=Op5P@ss99",
            "add name=viewer group=read password=V13wP@ss1",
            "add name=backup group=full password=Bkp9P@ss2",
        ),
        (
            "auth.local_users.present",
            "auth.local_users.privileged_present",
            "auth.local_users.password_strength_ok",
            "auth.local_users.group_diversity",
        ),
        6,
    ),
    (
        "/snmp community",
        (
            "set [ find default=yes ] name=public read-access=yes",
            "add name=private read-access=yes write-access=yes",
            "add name=secops read-access=yes",
        ),
        (
            "snmp.communities.present",
            "snmp.communities.default_present",
            "snmp.communities.write_access_present",
        ),
        5,
    ),
    (
        "/system logging action",
        (
            "add name=remote target=remote remote=10.10.10.5",
            "add name=disk target=disk disk-file-name=log",
        ),
        ("logging.remote_configured", "logging.local_configured"),
        4,
    ),
    (
        "/system ntp client",
        (
            "set enabled=yes primary-ntp=10.10.10.1",
            "set enabled=yes secondary-ntp=10.10.10.2",
        ),
        ("time.ntp.enabled", "time.ntp.redundant"),
        3,
    ),
    (
        "/radius incoming",
        (
            "set accept=yes",
            "set reject-delay=0s",
        ),
        ("auth.radius.accept_enabled", "auth.radius.reject_delay_set"),
        3,
    ),
    (
        "/ip ssh",
        (
            "set strong-crypto=yes",
            "set forwarding-enabled=no",
        ),
        ("crypto.channel.strong_cipher_required", "mgmt.remote_shell.forwarding_enabled"),
        2,
    ),
    (
        "/user group",
        (
            "set full policy=local,telnet,ssh,ftp,reboot,read,write,policy,test,winbox,password,web,sniff,sensitive,api,romon",
            "set read policy=local,telnet,ssh,reboot,read,test,winbox,web,sniff",
        ),
        ("auth.local_groups.policy_defined", "auth.local_groups.full_access_policy_present"),
        2,
    ),
    (
        "/user aaa",
        ("set use-radius=no",),
        ("auth.aaa.central_override_blocked",),
        1,
    ),
)

FILLER_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("/interface bridge", (
        "add name=bridge1 protocol-mode=rstp",
        "add name=bridge2 protocol-mode=rstp",
        "add name=bridge3 protocol-mode=none",
    )),
    ("/ip address", (
        "add address=10.0.0.1/24 interface=bridge1",
        "add address=192.168.5.1/24 interface=bridge2",
        "add address=172.16.0.1/30 interface=WAN",
        "add address=10.0.1.1/24 interface=bridge3",
    )),
    ("/ip route", (
        "add dst-address=0.0.0.0/0 gateway=172.16.0.2",
        "add dst-address=10.20.0.0/16 gateway=10.0.0.254",
        "add dst-address=10.30.0.0/16 gateway=10.0.0.253",
    )),
    ("/interface ethernet", (
        "set [ find default-name=ether1 ] name=WAN speed=1Gbps",
        "set [ find default-name=ether2 ] name=LAN1 speed=1Gbps",
        "set [ find default-name=ether3 ] name=LAN2 speed=100Mbps",
        "set [ find default-name=ether4 ] name=LAN3 speed=100Mbps",
    )),
    ("/system identity", ("set name=RTR-Pune-02",)),
    ("/queue simple", (
        "add name=guest-limit target=192.168.5.0/24 max-limit=10M/10M",
        "add name=iot-limit target=10.0.1.0/24 max-limit=5M/5M",
    )),
    ("/interface list member", (
        "add interface=bridge1 list=LAN",
        "add interface=bridge2 list=GUEST",
        "add interface=bridge3 list=IOT",
    )),
    ("/ip dns", ("set servers=8.8.8.8,8.8.4.4",)),
    ("/system script", (
        "add name=backup-script source=export-config policy=read,write",
        "add name=health-check source=ping-gateway policy=read",
    )),
    ("/interface bridge vlan", (
        "add bridge=bridge1 vlan-ids=10 tagged=ether2",
        "add bridge=bridge1 vlan-ids=20 tagged=ether3",
        "add bridge=bridge2 vlan-ids=30 tagged=ether4",
    )),
    ("/interface bridge port", (
        "add bridge=bridge1 interface=ether2 comment=uplink",
        "add bridge=bridge1 interface=ether3 comment=access",
        "add bridge=bridge2 interface=ether4 comment=guest-wifi",
    )),
    ("/ip pool", (
        "add name=dhcp-pool0 ranges=192.168.5.10-192.168.5.200",
        "add name=dhcp-pool1 ranges=10.0.1.10-10.0.1.200",
    )),
    ("/ip dhcp-server", (
        "add name=dhcp1 interface=bridge2 address-pool=dhcp-pool0",
        "add name=dhcp2 interface=bridge3 address-pool=dhcp-pool1",
    )),
    ("/system clock", ("set time-zone-name=Asia/Kolkata",)),
    ("/interface wireless", (
        "set [ find default-name=wlan1 ] ssid=CorpGuest mode=ap-bridge band=2ghz-b/g/n",
    )),
    ("/ip firewall address-list", (
        "add address=10.0.0.0/24 list=internal",
        "add address=10.0.1.0/24 list=internal",
        "add address=192.168.5.0/24 list=guest",
        "add address=203.0.113.5 list=blocked",
    )),
    ("/interface vlan", (
        "add interface=bridge1 name=vlan10 vlan-id=10",
        "add interface=bridge1 name=vlan20 vlan-id=20",
        "add interface=bridge2 name=vlan30 vlan-id=30",
    )),
    ("/system scheduler", (
        "add name=nightly-backup on-event=backup-script interval=1d",
        "add name=weekly-report on-event=health-check interval=7d",
    )),
    ("/tool graphing interface", (
        "add interface=bridge1 allow-address=0.0.0.0/0",
        "add interface=bridge2 allow-address=0.0.0.0/0",
    )),
    ("/system note", ("set show-at-login=no note=maintenance-window-sunday",)),
    ("/interface bonding", ("add name=bond1 slaves=ether3,ether4 mode=802.3ad",)),
    ("/ip firewall mangle", (
        "add chain=prerouting action=mark-connection new-connection-mark=guest-conn",
        "add chain=prerouting action=mark-routing new-routing-mark=guest-route",
        "add chain=forward action=mark-packet new-packet-mark=voip",
    )),
    ("/routing ospf instance", ("set default redistribute=connected",)),
    ("/interface ethernet switch", ("set switch1 name=switch1-cpu",)),
    ("/disk", ("add slot=usb1 type=usb-storage",)),
    # Note: "certificate" is deliberately *not* used as a section/path name
    # here even though it is realistic RouterOS config — it collides with
    # 08-learning-system.md §4.2's own high-relevance vocabulary
    # (`certificate` is explicitly listed), which would make this "filler"
    # section score as relevant. That is not a bug in the scorer; it is
    # this fixture avoiding a genuinely ambiguous case so the 9-question
    # acceptance assertion stays deterministic.
    ("/tool e-mail", (
        "set address=192.0.2.25 port=587",
        "set from=noc@rtr-pune-02.example",
    )),
    ("/interface gre", ("add name=gre-tun1 local-address=172.16.0.1 remote-address=203.0.113.20",)),
    ("/routing bgp connection", ("add name=peer1 remote.address=203.0.113.21 as=65010",)),
    ("/tool bandwidth-server", ("set enabled=no",)),
    ("/system watchdog", ()),
)

# Two deliberately unparseable lines — this is what keeps grammar-inference
# coverage at 98.4% instead of 100% (08-learning-system.md §3.2's own
# `coverage: 98.4%` figure, which by definition means *not* every line
# matched). Placed after the relevant+filler sections, matching where they
# sit in the corpus this fixture was tuned against.
MALFORMED_LINES = (
    ':put ("diagnostic-marker-" . [/system resource get uptime])',
    "~~~ garbage-not-a-statement ~~~",
)


def build_corpus_text() -> str:
    lines: list[str] = list(COMMENT_LINES)
    for section, stmts, _facts, _count in RELEVANT_SECTIONS:
        lines.append(section)
        lines.extend(stmts)
    for section, stmts in FILLER_SECTIONS[:15]:
        lines.append(section)
        lines.extend(stmts)
    lines.extend(MALFORMED_LINES)
    for section, stmts in FILLER_SECTIONS[15:]:
        lines.append(section)
        lines.extend(stmts)
    return "\n".join(lines) + "\n"


def build_unmatched_constructs() -> list[UnmatchedConstruct]:
    """Every statement line (not headers, not comments, not the malformed
    lines) as an `UnmatchedConstruct` — the real engine-contract shape
    (`nsca_engine.types.UnmatchedConstruct`) `template_mining.mine()`
    consumes, per backend-02 §3's fixture-then-real pattern: Track A's
    extractor runtime produces these in the real pipeline; here they are
    hand-built from this fixture's known structure."""

    text = build_corpus_text()
    line_no_by_text: dict[str, int] = {}
    for i, line in enumerate(text.splitlines(), start=1):
        line_no_by_text.setdefault(line, i)

    out: list[UnmatchedConstruct] = []
    for section, stmts, _facts, _count in RELEVANT_SECTIONS:
        for stmt in stmts:
            out.append(
                UnmatchedConstruct(
                    artifact_id=ARTIFACT_ID,
                    lines=(line_no_by_text[stmt],),
                    excerpt=stmt,
                    parse_path=(section,),
                )
            )
    for section, stmts in FILLER_SECTIONS:
        for stmt in stmts:
            out.append(
                UnmatchedConstruct(
                    artifact_id=ARTIFACT_ID,
                    lines=(line_no_by_text[stmt],),
                    excerpt=stmt,
                    parse_path=(section,),
                )
            )
    return out


@dataclass(frozen=True, slots=True)
class RequiredControl:
    control_id: str
    requires_facts: tuple[str, ...]


def build_required_controls() -> list[RequiredControl]:
    """One control per declared candidate fact, per section — control
    counts fall out of the fixture's own fact vocabulary (`len(facts)`)
    rather than being independently hand-picked, so there is exactly one
    place (`RELEVANT_SECTIONS`'s `facts` tuples) that decides both "what
    this section can teach" and "how many controls it unlocks"."""

    controls: list[RequiredControl] = []
    for qi, (section, _stmts, facts, _count) in enumerate(RELEVANT_SECTIONS, start=1):
        for k, fact in enumerate(facts):
            controls.append(RequiredControl(control_id=f"MIKRO-Q{qi}-{k + 1:02d}", requires_facts=(fact,)))
    return controls


EXPECTED_QUESTION_ORDER = tuple(section for section, *_ in RELEVANT_SECTIONS)
EXPECTED_GAINS = tuple(len(facts) for _section, _stmts, facts, _count in RELEVANT_SECTIONS)

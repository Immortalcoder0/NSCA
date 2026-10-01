"""Deliberately constructed fixture set (backend-01 §6, M4): >=30
near-identical Cisco IOS branch-router configs sharing one identical
defective management ACL/telnet block, used to prove
`risk/anomaly.detect_systemic` actually fires (TRD-06.3 §4, V-06.3-005) since
the real corpus doesn't have anything like this yet (same reasoning as the
M2/M3 corpus-gap notes elsewhere in this codebase).

Generated programmatically rather than as 40 near-duplicate physical files —
deterministic given `n`, so byte-identical across runs/processes (D1/D6), and
easy to see exactly what varies per device (hostname/IP octet only) versus
what's the shared defect (the whole management block, byte-for-byte
identical across every affected device — the systemic clustering
normalisation should collapse even the differing IP octets).
"""

from __future__ import annotations

TOTAL_BRANCH_ROUTERS = 40
DEFECTIVE_COUNT = 31  # TRD-06.3 §4.2's own worked example: 31 of 40


def _device_id(i: int) -> str:
    return f"BR-RTR-{i:03d}"


def branch_router_config(i: int, *, defective: bool) -> str:
    """One branch router's running-config. ``defective`` devices carry the
    shared build-template defect (telnet enabled, no source restriction on
    the management ACL — same underlying misconfiguration on every affected
    device, byte-identical after evidence normalisation). Non-defective
    devices are otherwise structurally identical but were "built from a
    corrected template" (ssh-only transport)."""

    hostname = _device_id(i)
    octet = 10 + i  # 11..50, keeps every device on a distinct /24
    transport = "telnet ssh" if defective else "ssh"
    return (
        "!\n"
        "version 15.2\n"
        "service password-encryption\n"
        f"hostname {hostname}\n"
        "!\n"
        "username admin privilege 15 password 5 $1$mERr$hx5rVt7rPNoS4wqbXKX7m0\n"
        "!\n"
        "aaa new-model\n"
        "aaa authentication login default group tacacs+ local\n"
        "!\n"
        "ip domain-name corp.example.com\n"
        "ip ssh version 2\n"
        "no ip http server\n"
        "!\n"
        f"interface GigabitEthernet0/0\n"
        f" ip address 192.168.{octet}.1 255.255.255.0\n"
        "!\n"
        "line vty 0 4\n"
        " login local\n"
        f" transport input {transport}\n"
        " exec-timeout 5 0\n"
        "!\n"
        "end\n"
    )


def branch_router_fleet(
    total: int = TOTAL_BRANCH_ROUTERS, defective: int = DEFECTIVE_COUNT,
) -> tuple[tuple[str, str], ...]:
    """Returns ``((device_id, config_text), ...)`` for the full fleet, sorted
    by device id (D6) — the first ``defective`` devices (by index) carry the
    shared defect."""

    out = []
    for i in range(1, total + 1):
        out.append((_device_id(i), branch_router_config(i, defective=i <= defective)))
    out.sort(key=lambda t: t[0])
    return tuple(out)

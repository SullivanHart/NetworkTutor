import ipaddress
import re
from dataclasses import dataclass
from typing import Callable

from packages.curriculum.network_sim import NetworkTopology
from packages.curriculum.lessons.lesson_01.lesson import build_topology

@dataclass
class LessonStep:
    number: int
    title: str
    content: str
    task: str
    completion_check: Callable
    hint: str

class LessonState:
    lesson_title = "Network Diagnostic Commands"
    lesson_number = 3

    def __init__(self):
        self.topology: NetworkTopology = build_topology()
        # In Lesson 3 the network is fully functional; add the route that
        # Lesson 1 students discover is missing so that ping succeeds.
        r1 = self.topology.devices.get("r1")
        if r1 is not None:
            r1.add_route("172.16.0.0/24", "10.0.0.2", "eth1", metric=1, proto="static")
        self.current_step: int = 1
        self.command_history: list[str] = []
        self.commands_run: set[str] = set()
        self.last_output: list[str] = []
        self.focused_device: str = "host_a"
        self.last_ping_success: dict[str, bool] = {}
        self.connections_shown: bool = False

    def record_command(self, cmd: str):
        self.command_history.append(cmd.strip())
        self.commands_run.add(cmd.strip().lower())

    def has_run(self, cmd: str) -> bool:
        return cmd.strip().lower() in self.commands_run

    def has_run_any(self, *cmds: str) -> bool:
        return any(self.has_run(c) for c in cmds)

    def get_steps(self) -> list:
        return build_steps()

    def get_step(self, n: int):
        steps = self.get_steps()
        idx = n - 1
        if 0 <= idx < len(steps):
            return steps[idx]
        return None

    def render_state(self) -> list[str]:
        dev_name = self.focused_device or "host_a"
        device = self.topology.devices.get(dev_name)
        if device is None:
            return [f"Host: {dev_name.upper()}  (not found)"]

        # Determine display IP from first interface
        ip_display = ""
        if device.interfaces:
            ip_display = f"  ({device.interfaces[0].ip})"

        lines = [
            f"Host: {dev_name.upper()}{ip_display}",
            "",
            f"  {'Interface':<14} {'Address':<18} State",
            "  " + "─" * 38,
        ]
        for iface in device.interfaces:
            lines.append(f"  {iface.name:<14} {iface.cidr:<18} UP")
        if dev_name in ("host_a", "host_b"):
            lines.append(f"  {'lo':<14} {'127.0.0.1/8':<18} UP")
        return lines

    def handle_command(self, cmd_str: str) -> list[str]:
        cmd_lower = re.sub(r"\s+", " ", cmd_str.strip().lower())

        if cmd_lower in ("ip addr", "ip a", "ifconfig"):
            return self._cmd_ip_addr()
        if cmd_lower in ("ip route", "ip r"):
            return self._cmd_ip_route()
        if cmd_lower.startswith("ping "):
            return self._cmd_ping(cmd_lower)
        if cmd_lower in ("ss", "ss -t", "netstat"):
            return self._cmd_ss()
        if cmd_lower.startswith("ip addr show "):
            dev = cmd_lower.split("ip addr show ", 1)[1].strip()
            return self._cmd_ip_addr_show(dev)
        if cmd_lower in ("help", "?"):
            return _help()

        return [f"[red]Unknown command:[/red] {cmd_str}  - type 'help' for lesson commands."]

    def _cmd_ip_addr(self) -> list[str]:
        device = self.topology.devices.get(self.focused_device)
        if device is None:
            return [f"[red]Device not found:[/red] {self.focused_device}"]
        lines = [f"ip addr show  (device: {self.focused_device.upper()})", ""]
        for iface in device.interfaces:
            lines.append(f"  {iface.name}: <BROADCAST,MULTICAST,UP,LOWER_UP>")
            lines.append(f"      inet {iface.cidr} scope global {iface.name}")
        if self.focused_device in ("host_a", "host_b"):
            lines.append("  lo: <LOOPBACK,UP,LOWER_UP>")
            lines.append("      inet 127.0.0.1/8 scope host lo")
        return lines

    def _cmd_ip_route(self) -> list[str]:
        device = self.topology.devices.get(self.focused_device)
        if device is None:
            return [f"[red]Device not found:[/red] {self.focused_device}"]
        lines = [f"ip route  (device: {self.focused_device.upper()})", ""]
        if not device.routes:
            lines.append("  [dim](no routes)[/dim]")
        else:
            for route in sorted(device.routes, key=lambda r: (-r.prefix_len, r.network)):
                gw = f"via {route.gateway}" if route.gateway else ""
                dev_part = f"dev {route.interface}"
                proto = f"proto {route.proto}"
                metric = f"metric {route.metric}"
                if route.network == "0.0.0.0/0":
                    line = f"  default {gw} {dev_part} {proto} {metric}".rstrip()
                else:
                    line = f"  {route.network} {gw} {dev_part} {proto} {metric}".rstrip()
                style = "dim" if route.proto == "connected" else ""
                lines.append(f"[{style}]{line}[/{style}]" if style else line)
        return lines

    def _cmd_ping(self, cmd_lower: str) -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 2:
            return ["[red]Usage:[/red] ping <ip>"]
        dest_ip = parts[1]
        try:
            ipaddress.ip_address(dest_ip)
        except ValueError:
            return [f"[red]Invalid IP address:[/red] {dest_ip}"]
        hops = self.topology.simulate_ping(self.focused_device, dest_ip)
        overall_success = all(h.success for h in hops) and len(hops) > 0
        self.last_ping_success[dest_ip] = overall_success
        src_device = self.topology.devices.get(self.focused_device)
        src_ip = src_device.interfaces[0].ip if src_device and src_device.interfaces else "?"
        lines = [f"Simulating ping: {src_ip} -> {dest_ip}", ""]
        for i, hop in enumerate(hops, 1):
            dev = hop.device.upper().replace("_", " ")
            icon = "[green]✓[/green]" if hop.success else "[red]✗[/red]"
            row = f"  Hop {i}  [{dev:<8}]  {hop.ip:<18}  {hop.note}"
            lines.append(f"{row}  {icon}")
        lines.append("")
        if overall_success:
            lines.append("[green]SUCCESS[/green]  - round trip simulated.")
        else:
            failed = next((h for h in hops if not h.success), None)
            note = failed.note if failed else "unknown"
            lines.append(f"[red]UNREACHABLE[/red]  - {note}")
        return lines

    def _cmd_ss(self) -> list[str]:
        self.connections_shown = True
        return [
            "Active Internet connections (ss -t)",
            "",
            f"  {'Netid':<6}  {'State':<8}  {'Local Address:Port':<25}  Peer Address:Port",
            "  " + "─" * 62,
            f"  {'tcp':<6}  {'ESTAB':<8}  {'192.168.1.10:49152':<25}  172.16.0.10:80",
            f"  {'tcp':<6}  {'ESTAB':<8}  {'192.168.1.10:49153':<25}  172.16.0.10:443",
            f"  {'tcp':<6}  {'LISTEN':<8}  {'0.0.0.0:22':<25}  0.0.0.0:*",
            "",
            "ESTAB  = established connection (data flowing)",
            "LISTEN = waiting for incoming connections",
        ]

    def _cmd_ip_addr_show(self, dev: str) -> list[str]:
        _mapping = {
            "host_a": "host_a", "hosta": "host_a",
            "host_b": "host_b", "hostb": "host_b",
            "r1": "r1", "r2": "r2",
        }
        dev_name = _mapping.get(dev.lower(), dev.lower())
        device = self.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev}"]
        self.focused_device = dev_name
        return self._cmd_ip_addr()

def _help() -> list[str]:
    return [
        "Lesson 3 commands",
        "─" * 40,
        "",
        "  ip addr  /  ip a  /  ifconfig    show network interfaces",
        "  ip addr show <dev>               focus on a specific device",
        "  ip route  /  ip r                show routing table",
        "  ping <ip>                        simulate ping from focused device",
        "  ss  /  ss -t  /  netstat         show active TCP connections",
        "",
        "  hint    hint for the current step",
        "  next    advance when the current step is complete",
        "  quit    exit",
    ]

def build_steps() -> list[LessonStep]:
    steps: list[LessonStep] = []

    steps.append(LessonStep(
        number=1,
        title="Introduction -- Linux Network Commands",
        content=(
            "These are the commands you will actually use when working with\n"
            "real Linux systems. Every network engineer uses them daily.\n\n"
            "  ip addr    show network interfaces and IP addresses\n"
            "  ip route   show the routing table\n"
            "  ping       test reachability\n"
            "  ss         show active TCP connections\n\n"
            "You are on Host A (192.168.1.10) looking at the same four-device\n"
            "topology from Lesson 1. Type ip addr to see your interfaces."
        ),
        task="ip addr",
        completion_check=lambda state: (
            state.has_run_any("ip addr", "ip a", "ifconfig"),
            "Type: ip addr",
        ),
        hint='type "ip addr"',
    ))

    steps.append(LessonStep(
        number=2,
        title="Viewing Interface Addresses (ip addr)",
        content=(
            "The ip addr command shows every network interface on the host\n"
            "and its assigned IP address.\n\n"
            "Each interface has:\n\n"
            "  name     eth0, lo, etc.\n"
            "  address  IP address with subnet mask in CIDR notation (/24)\n"
            "  state    UP means the interface is active\n\n"
            "lo is the loopback interface -- always 127.0.0.1, used for\n"
            "local communication within the same host.\n\n"
            "Run ip addr again to see the full output."
        ),
        task="ip addr",
        completion_check=lambda state: (
            state.has_run_any("ip addr", "ip a", "ifconfig"),
            "Type: ip addr",
        ),
        hint='type "ip addr"',
    ))

    steps.append(LessonStep(
        number=3,
        title="Viewing the Routing Table (ip route)",
        content=(
            "ip route shows the routing table, connecting back to what you\n"
            "learned in Lesson 1.\n\n"
            "Each line is a route. The default route (0.0.0.0/0 shown as\n"
            "'default') is how the host reaches everything it does not have\n"
            "a specific route for. Without a default route, the host can only\n"
            "reach devices on its local subnets.\n\n"
            "Host A's default route points to R1 (192.168.1.1), which will\n"
            "then forward packets onwards toward the destination."
        ),
        task="ip route",
        completion_check=lambda state: (
            state.has_run_any("ip route", "ip r"),
            "Type: ip route",
        ),
        hint='type "ip route"',
    ))

    steps.append(LessonStep(
        number=4,
        title="Testing Connectivity (ping)",
        content=(
            "ping sends ICMP echo requests and waits for replies. It tells\n"
            "you if a host is reachable and approximately how long the round\n"
            "trip takes.\n\n"
            "Here, ping walks hop-by-hop through the topology exactly as real\n"
            "IP routing works, and shows you each forwarding decision.\n\n"
            "Try to reach Host B at 172.16.0.10."
        ),
        task="ping 172.16.0.10",
        completion_check=lambda state: (
            state.has_run("ping 172.16.0.10") and
            state.last_ping_success.get("172.16.0.10") is True,
            "Type: ping 172.16.0.10  (it should succeed -- topology is intact)",
        ),
        hint='type "ping 172.16.0.10"',
    ))

    steps.append(LessonStep(
        number=5,
        title="Viewing Active Connections (ss)",
        content=(
            "ss (socket statistics) shows active network connections -- what\n"
            "ports your system has open and what remote addresses it is\n"
            "connected to. It replaced netstat on modern Linux systems.\n\n"
            "Each line shows:\n\n"
            "  state           ESTAB (connected) or LISTEN (waiting)\n"
            "  local address   your IP and port\n"
            "  peer address    remote IP and port\n\n"
            "Port 80 = HTTP, port 443 = HTTPS, port 22 = SSH."
        ),
        task="ss",
        completion_check=lambda state: (
            state.has_run_any("ss", "ss -t", "netstat"),
            "Type: ss",
        ),
        hint='type "ss"',
    ))

    steps.append(LessonStep(
        number=6,
        title="Lesson Complete",
        content=(
            "These commands map directly to the layers from Lesson 2:\n"
            "ip addr is Physical Network, ip route is Network (IP),\n"
            "ping exercises the full stack, ss shows Transport-layer state.\n\n"
            "Lesson 4  Visualizing packet transmission\n"
            "Lesson 5  TCP congestion control"
        ),
        task="next",
        completion_check=lambda state: (True, ""),
        hint="next",
    ))

    return steps

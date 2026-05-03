import ipaddress
import re
from dataclasses import dataclass, field
from typing import Callable, Optional
from packages.curriculum.network_sim import (
    Interface,
    NetworkDevice,
    NetworkTopology,
    Route,
)

@dataclass
class LessonStep:
    number: int
    title: str
    content: str
    task: str
    completion_check: Callable
    hint: str

def _normalize_device(name: str) -> str:
    mapping = {
        "r1": "r1", "router1": "r1", "router r1": "r1",
        "r2": "r2", "router2": "r2", "router r2": "r2",
        "host_a": "host_a", "hosta": "host_a", "host a": "host_a", "a": "host_a",
        "host_b": "host_b", "hostb": "host_b", "host b": "host_b", "b": "host_b",
    }
    return mapping.get(name.lower().strip(), name.lower().strip())

class LessonState:
    lesson_title = "Routing Tables and Longest Prefix Match"
    lesson_number = 1

    def __init__(self, topology: NetworkTopology):
        self.topology = topology
        self.current_step: int = 1
        self.command_history: list[str] = []
        self.commands_run: set[str] = set()
        self.last_output: list[str] = []
        self.focused_device: str = "r1"
        self.last_ping_success: dict[str, bool] = {}

    def record_command(self, cmd: str):
        self.command_history.append(cmd.strip())
        self.commands_run.add(cmd.strip().lower())

    def has_run(self, cmd: str) -> bool:
        return cmd.strip().lower() in self.commands_run

    def get_steps(self) -> list:
        return build_steps()

    def get_step(self, n: int):
        steps = self.get_steps()
        idx = n - 1
        if 0 <= idx < len(steps):
            return steps[idx]
        return None

    def render_state(self) -> list[str]:
        dev_name = self.focused_device or "r1"
        device = self.topology.devices.get(dev_name)
        if device is None:
            return [f"Routing table: {dev_name}  (not found)"]
        n = len(device.routes)
        lines = [
            f"Routing table: {dev_name.upper()}  ({n} route{'s' if n != 1 else ''})",
            "",
            f"  {'Destination':<22}{'Gateway':<22}{'Interface':<12}{'Protocol':<12}Metric",
            "  " + "─" * 68,
        ]
        if not device.routes:
            lines.append("  [dim](empty)[/dim]")
        else:
            for route in sorted(device.routes, key=lambda r: (-r.prefix_len, r.network)):
                gw = route.gateway if route.gateway else "directly connected"
                style = "dim" if route.proto == "connected" else ""
                row = f"  {route.network:<22}{gw:<22}{route.interface:<12}{route.proto:<12}{route.metric}"
                lines.append(f"[{style}]{row}[/{style}]" if style else row)
        return lines

    def handle_command(self, cmd_str: str) -> list[str]:
        cmd_lower = re.sub(r"\s+", " ", cmd_str.strip().lower())

        if cmd_lower == "show diagram":
            return self._cmd_show_diagram()
        if cmd_lower.startswith("show routes"):
            return self._cmd_show_routes(cmd_lower)
        if cmd_lower.startswith("show interfaces"):
            return self._cmd_show_interfaces(cmd_lower)
        if cmd_lower.startswith("show lpm"):
            return self._cmd_show_lpm(cmd_lower)
        if cmd_lower.startswith("ping "):
            return self._cmd_ping(cmd_lower)
        if cmd_lower.startswith("traceroute "):
            return self._cmd_ping(cmd_lower.replace("traceroute ", "ping ", 1))
        if cmd_lower.startswith("route add "):
            return self._cmd_route_add(cmd_str)
        if cmd_lower.startswith("route del "):
            return self._cmd_route_del(cmd_lower)

        return [f"[red]Unknown command:[/red] {cmd_str}  - type 'help' for a list of commands."]

    def _cmd_show_diagram(self) -> list[str]:
        lines = ["Network Topology Diagram", ""]
        for line in ASCII_DIAGRAM.splitlines():
            lines.append(line)
        lines += [
            "",
            "  host_a   Host A     192.168.1.10/24   (Office A)",
            "  r1       Router R1  eth0: 192.168.1.1/24  eth1: 10.0.0.1/30",
            "  r2       Router R2  eth0: 10.0.0.2/30    eth1: 172.16.0.1/24",
            "  host_b   Host B     172.16.0.10/24   (Office B)",
        ]
        return lines

    def _cmd_show_routes(self, cmd_lower: str) -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 3:
            return ["[red]Usage:[/red] show routes <device>   e.g. show routes r1"]
        dev_name = _normalize_device(parts[2])
        device = self.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}  (valid: r1, r2, host_a, host_b)"]
        self.focused_device = dev_name
        lines = [f"Routing table for {dev_name.upper()} - see panel above.", ""]
        lines.append(f"  {'Destination':<22}{'Gateway':<22}{'Interface':<12}{'Protocol':<12}Metric")
        lines.append("  " + "─" * 68)
        if not device.routes:
            lines.append("  [dim](no routes)[/dim]")
        else:
            for route in sorted(device.routes, key=lambda r: (-r.prefix_len, r.network)):
                gw = route.gateway if route.gateway else "directly connected"
                style = "dim" if route.proto == "connected" else ""
                row = f"  {route.network:<22}{gw:<22}{route.interface:<12}{route.proto:<12}{route.metric}"
                lines.append(f"[{style}]{row}[/{style}]" if style else row)
        lines.append("")
        lines.append(f"[dim]{len(device.routes)} route(s)[/dim]")
        return lines

    def _cmd_show_interfaces(self, cmd_lower: str) -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 3:
            return ["[red]Usage:[/red] show interfaces <device>"]
        dev_name = _normalize_device(parts[2])
        device = self.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}"]
        lines = [f"Interfaces - {dev_name.upper()}", ""]
        lines.append(f"  {'Interface':<14}{'IP / prefix':<20}{'Network':<20}Peer")
        lines.append("  " + "─" * 62)
        for iface in device.interfaces:
            peer = iface.peer if iface.peer else "-"
            lines.append(f"  {iface.name:<14}{iface.cidr:<20}{iface.network:<20}{peer}")
        return lines

    def _cmd_show_lpm(self, cmd_lower: str) -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 3:
            return ["[red]Usage:[/red] show lpm <ip>   e.g. show lpm 172.16.0.5"]
        dest_ip = parts[2]
        try:
            ipaddress.ip_address(dest_ip)
        except ValueError:
            return [f"[red]Invalid IP address:[/red] {dest_ip}"]
        dev_name = self.focused_device or "r1"
        device = self.topology.devices.get(dev_name)
        if device is None:
            device = self.topology.devices.get("r1")
            dev_name = "r1"
        matching = device.get_all_matching_routes(dest_ip)
        winner = device.lookup_route(dest_ip)
        lines = [
            f"Longest Prefix Match - {dest_ip} on {dev_name.upper()}",
            "",
            "RFC 1812 §5.2.4.3 - forwarding algorithm:",
            "  1. Collect all routes whose network contains the destination IP.",
            "  2. Select the one with the longest prefix (largest /N).",
            "  3. Break ties by metric (lower wins).",
            "",
            f"  {'Route':<24}{'Prefix':>8}  {'Metric':>6}  {'Match?':>8}  Selected",
            "  " + "─" * 60,
        ]
        for route in sorted(device.routes, key=lambda r: (-r.prefix_len, r.network)):
            does_match = route.matches(dest_ip)
            is_winner = winner is not None and route.network == winner.network
            match_str = "yes" if does_match else "no"
            sel_str = "<-- winner" if is_winner else ""
            row = f"  {route.network:<24}/{route.prefix_len:>6}  {route.metric:>6}  {match_str:>8}  {sel_str}"
            if is_winner:
                lines.append(f"[bold]{row}[/bold]")
            elif not does_match:
                lines.append(f"[dim]{row}[/dim]")
            else:
                lines.append(row)
        lines.append("")
        if winner:
            gw = winner.gateway if winner.gateway else "directly connected"
            lines.append(
                f"Result: /{winner.prefix_len} wins"
                + (f" ({len(matching)} routes matched, most specific selected)" if len(matching) > 1 else "")
            )
            lines.append(f"  -> forward via gateway {gw}  out {winner.interface}")
        else:
            lines.append(f"[red]Result: no route to {dest_ip} - packet would be dropped.[/red]")
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
        hops = self.topology.simulate_ping("host_a", dest_ip)
        overall_success = all(h.success for h in hops) and len(hops) > 0
        self.last_ping_success[dest_ip] = overall_success
        lines = [f"Simulating ping: 192.168.1.10 -> {dest_ip}", ""]
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

    def _cmd_route_add(self, cmd_str: str) -> list[str]:
        pattern = re.compile(
            r"route\s+add\s+(?P<network>\S+)\s+via\s+(?P<gateway>\S+)"
            r"\s+dev\s+(?P<interface>\S+)\s+on\s+(?P<device>\S+)",
            re.IGNORECASE,
        )
        m = pattern.search(cmd_str)
        if not m:
            return [
                "[red]Parse error.[/red]  Syntax:",
                "  route add <network/prefix> via <gateway> dev <interface> on <device>",
                "  Example: route add 172.16.0.0/24 via 10.0.0.2 dev eth1 on r1",
            ]
        network, gateway = m.group("network"), m.group("gateway")
        interface = m.group("interface")
        dev_name = _normalize_device(m.group("device"))
        try:
            norm_network = str(ipaddress.ip_network(network, strict=False))
        except ValueError:
            return [f"[red]Invalid network:[/red] {network}"]
        try:
            ipaddress.ip_address(gateway)
        except ValueError:
            return [f"[red]Invalid gateway IP:[/red] {gateway}"]
        device = self.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}  (valid: r1, r2, host_a, host_b)"]
        device.add_route(norm_network, gateway, interface, metric=1, proto="static")
        self.focused_device = dev_name
        return [
            f"[green]Route added to {dev_name.upper()}:[/green]  {norm_network}  via {gateway}  dev {interface}",
            f"[dim]Routing table for {dev_name.upper()} now has {len(device.routes)} route(s).[/dim]",
        ]

    def _cmd_route_del(self, cmd_lower: str) -> list[str]:
        pattern = re.compile(
            r"route\s+del\s+(?P<network>\S+)\s+on\s+(?P<device>\S+)",
            re.IGNORECASE,
        )
        m = pattern.search(cmd_lower)
        if not m:
            return [
                "[red]Parse error.[/red]  Syntax:",
                "  route del <network/prefix> on <device>",
                "  Example: route del 172.16.0.0/24 on r1",
            ]
        network = m.group("network")
        dev_name = _normalize_device(m.group("device"))
        try:
            ipaddress.ip_network(network, strict=False)
        except ValueError:
            return [f"[red]Invalid network:[/red] {network}"]
        device = self.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}"]
        removed = device.del_route(network)
        if removed:
            self.focused_device = dev_name
            return [
                f"[green]Route removed from {dev_name.upper()}:[/green]  {network}",
                f"[dim]Routing table for {dev_name.upper()} now has {len(device.routes)} route(s).[/dim]",
            ]
        return [f"Route not found: {network} on {dev_name.upper()}"]

ASCII_DIAGRAM = """\
Office A (192.168.1.0/24)                   Office B (172.16.0.0/24)

+--------+          +----------+            +----------+          +--------+
| Host A |__________| Router   |____________| Router   |__________| Host B |
|        | eth0     |   R1     | eth1  eth0 |   R2     | eth1     |        |
| .1.10  | .1.1/24  | .1.1/24  |  10.0.0/30 | 10.0.0.2 | .0.1/24  | .0.10  |
+--------+          +----------+            +----------+          +--------+
^ you
192.168.1.10        192.168.1.1             10.0.0.2              172.16.0.10
                    eth1: 10.0.0.1/30       eth1: 172.16.0.1/24

WAN Link: 10.0.0.0/30  (R1 eth1=10.0.0.1  <-->  R2 eth0=10.0.0.2)
"""

def build_topology() -> NetworkTopology:
    topo = NetworkTopology()

    host_a = NetworkDevice(
        name="host_a",
        device_type="host",
        interfaces=[Interface("eth0", "192.168.1.10/24")],
        routes=[Route("0.0.0.0/0", "192.168.1.1", "eth0", 1, "static")],
    )

    # R1 intentionally missing the route to 172.16.0.0/24 -- this is the bug
    r1 = NetworkDevice(
        name="r1",
        device_type="router",
        interfaces=[
            Interface("eth0", "192.168.1.1/24"),
            Interface("eth1", "10.0.0.1/30"),
        ],
        routes=[
            Route("192.168.1.0/24", None, "eth0", 0, "connected"),
            Route("10.0.0.0/30",    None, "eth1", 0, "connected"),
        ],
    )

    r2 = NetworkDevice(
        name="r2",
        device_type="router",
        interfaces=[
            Interface("eth0", "10.0.0.2/30"),
            Interface("eth1", "172.16.0.1/24"),
        ],
        routes=[
            Route("10.0.0.0/30",  None,       "eth0", 0, "connected"),
            Route("172.16.0.0/24", None,      "eth1", 0, "connected"),
            Route("0.0.0.0/0",    "10.0.0.1", "eth0", 1, "static"),
        ],
    )

    host_b = NetworkDevice(
        name="host_b",
        device_type="host",
        interfaces=[Interface("eth0", "172.16.0.10/24")],
        routes=[Route("0.0.0.0/0", "172.16.0.1", "eth0", 1, "static")],
    )

    topo.add_device(host_a)
    topo.add_device(r1)
    topo.add_device(r2)
    topo.add_device(host_b)

    topo.add_link("host_a", "eth0", "r1",    "eth0")
    topo.add_link("r1",     "eth1", "r2",    "eth0")
    topo.add_link("r2",     "eth1", "host_b","eth0")

    return topo

def _r1_has_route_to_office_b(state: LessonState) -> tuple[bool, str]:
    r1 = state.topology.devices.get("r1")
    if r1 is None:
        return False, "R1 not found in topology."
    route = r1.lookup_route("172.16.0.10")
    if route and route.network != "0.0.0.0/0":
        import ipaddress
        if ipaddress.ip_network(route.network, strict=False).prefixlen > 0:
            return True, "Route to Office B is present on R1."
    return False, "R1 still has no route to 172.16.0.0/24."

def build_steps() -> list[LessonStep]:
    steps: list[LessonStep] = []

    steps.append(LessonStep(
        number=1,
        title="Introduction -- The Network Scenario",
        content=(
            "You are a network engineer called in to troubleshoot a connectivity\n"
            "problem. Two offices are connected through two routers, but Host A\n"
            "cannot reach Host B.\n\n"
            "  Office A (192.168.1.0/24)           Office B (172.16.0.0/24)\n\n"
            "  Host A -- Router R1 -- WAN (10.0.0.0/30) -- Router R2 -- Host B\n"
            "  .1.10     .1.1                               10.0.0.2    .0.10\n\n"
            "Your job: diagnose the fault and fix the routing table so packets\n"
            "flow end-to-end. Type commands and watch the routing table update live."
        ),
        task="show diagram",
        completion_check=lambda state: (
            state.has_run("show diagram"),
            "Type: show diagram",
        ),
        hint="type \'show diagram\'",
    ))

    steps.append(LessonStep(
        number=2,
        title="Examine the Routing Table",
        content=(
            "A routing table is stored on every router and host. It is a list\n"
            "of rules: Destination -> Where to forward packets.\n\n"
            "Each entry has five fields:\n\n"
            "  Destination   the target network  (e.g. 192.168.1.0/24)\n"
            "  Gateway       next-hop IP, or 'directly connected' if on the same link\n"
            "  Interface     the outgoing NIC  (eth0, eth1 ...)\n"
            "  Protocol      how the route was learned: connected (auto), static (manual)\n"
            "  Metric        cost; lower wins when two routes tie\n\n"
            "When a packet arrives, the router looks up the destination and forwards\n"
            "it out the matching interface.\n\n"
            "Look at R1's table. Two routes are present. What's missing?"
        ),
        task="show routes r1",
        completion_check=lambda state: (
            state.has_run("show routes r1"),
            "Type: show routes r1",
        ),
        hint="type 'show routes r1'",
    ))

    steps.append(LessonStep(
        number=3,
        title="Diagnose the Problem -- Simulate a Ping",
        content=(
            "Host A (192.168.1.10) is trying to reach Host B (172.16.0.10),\n"
            "but something in the network is dropping the packet.\n\n"
            "The 'ping' command here simulates packet forwarding hop-by-hop.\n"
            "It walks each device's routing table in order, exactly as real IP\n"
            "routing works, and shows you where the packet is dropped.\n\n"
            "Which device drops the packet, and why?"
        ),
        task="ping 172.16.0.10",
        completion_check=lambda state: (
            state.has_run("ping 172.16.0.10") and
            state.last_ping_success.get("172.16.0.10") is False,
            "Type: ping 172.16.0.10  (it should fail -- nothing is fixed yet)",
        ),
        hint="type 'ping 172.16.0.10'",
    ))

    steps.append(LessonStep(
        number=4,
        title="Fix the Routing Table -- Add a Static Route",
        content=(
            "R1 has no route to 172.16.0.0/24 (Office B). When it receives\n"
            "a packet for 172.16.0.10, it finds no matching entry and drops it.\n\n"
            "Fix: add a static route telling R1 where to send those packets.\n\n"
            "  For traffic to 172.16.0.0/24, forward to R2 (10.0.0.2) via eth1.\n\n"
            "On Linux this would be:\n\n"
            "  ip route add 172.16.0.0/24 via 10.0.0.2 dev eth1\n\n"
            "Watch the routing table update as soon as you run the command."
        ),
        task="route add 172.16.0.0/24 via 10.0.0.2 dev eth1 on r1",
        completion_check=_r1_has_route_to_office_b,
        hint="type 'route add 172.16.0.0/24 via 10.0.0.2 dev eth1 on r1'",
    ))

    steps.append(LessonStep(
        number=5,
        title="Verify the Fix -- Ping Again",
        content=(
            "R1 now has a route to 172.16.0.0/24. Expected path:\n\n"
            "  Host A -> R1 -> R2 -> Host B\n\n"
            "  Hop 1  Host A: default route -> forward to R1 (192.168.1.1)\n"
            "  Hop 2  R1: matches 172.16.0.0/24 -> forward to R2 (10.0.0.2)\n"
            "  Hop 3  R2: 172.16.0.0/24 directly connected -> deliver\n"
            "  Hop 4  Host B receives the packet\n\n"
            "Each router makes an independent forwarding decision based only\n"
            "on its own routing table. This is how IP routing works at every\n"
            "hop on the Internet."
        ),
        task="ping 172.16.0.10",
        completion_check=lambda state: (
            state.has_run("ping 172.16.0.10") and
            state.last_ping_success.get("172.16.0.10") is True,
            "The ping must succeed. Have you added the route in Step 4?",
        ),
        hint="type 'ping 172.16.0.10'",
    ))

    steps.append(LessonStep(
        number=6,
        title="Lesson Complete",
        content=(
            "Routing tables map destinations to next hops. Every router makes\n"
            "an independent forwarding decision based only on its own table --\n"
            "there is no central authority.\n\n"
            "Lesson 2  The TCP/IP model\n"
            "Lesson 3  Network diagnostic commands\n"
            "Lesson 4  Visualizing packet transmission\n"
            "Lesson 5  TCP congestion control"
        ),
        task="next",
        completion_check=lambda state: (True, ""),
        hint="next",
    ))

    return steps

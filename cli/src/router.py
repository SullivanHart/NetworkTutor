"""
Command dispatcher for the Network Tutor.

CommandRouter.dispatch(cmd_str, state) -> list[str]

All output is returned as a list of rich markup strings so app.py can
print them. Markup is used only where it carries meaning:
  [green] / [red] for success / failure
  [dim]   for secondary info
  [bold]  for emphasis on key values
"""
from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.curriculum.lessons.lesson_01.lesson import LessonState


def _normalize_device(name: str) -> str:
    mapping = {
        "r1": "r1", "router1": "r1", "router r1": "r1",
        "r2": "r2", "router2": "r2", "router r2": "r2",
        "host_a": "host_a", "hosta": "host_a", "host a": "host_a", "a": "host_a",
        "host_b": "host_b", "hostb": "host_b", "host b": "host_b", "b": "host_b",
    }
    return mapping.get(name.lower().strip(), name.lower().strip())


class CommandRouter:

    def dispatch(self, cmd_str: str, state: "LessonState") -> list[str]:
        cmd_str = cmd_str.strip()
        if not cmd_str:
            return []
        cmd_lower = re.sub(r"\s+", " ", cmd_str.lower())

        if cmd_lower == "show diagram":
            return self._cmd_show_diagram(state)
        if cmd_lower.startswith("show routes"):
            return self._cmd_show_routes(cmd_lower, state)
        if cmd_lower.startswith("show interfaces"):
            return self._cmd_show_interfaces(cmd_lower, state)
        if cmd_lower.startswith("show lpm"):
            return self._cmd_show_lpm(cmd_lower, state)
        if cmd_lower.startswith("ping "):
            return self._cmd_ping(cmd_lower, state)
        if cmd_lower.startswith("traceroute "):
            return self._cmd_ping(cmd_lower.replace("traceroute ", "ping ", 1), state)
        if cmd_lower.startswith("route add "):
            return self._cmd_route_add(cmd_str, state)
        if cmd_lower.startswith("route del "):
            return self._cmd_route_del(cmd_lower, state)
        if cmd_lower == "hint":
            return self._cmd_hint(state)
        if cmd_lower in ("help", "?"):
            return self._cmd_help()
        if cmd_lower == "next":
            return self._cmd_next(state)
        if cmd_lower in ("quit", "exit", "q"):
            return []

        return [f"[red]Unknown command:[/red] {cmd_str}  - type 'help' for a list of commands."]

    # ------------------------------------------------------------------
    # show diagram
    # ------------------------------------------------------------------

    def _cmd_show_diagram(self, state: "LessonState") -> list[str]:
        from packages.curriculum.lessons.lesson_01.lesson import ASCII_DIAGRAM
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

    # ------------------------------------------------------------------
    # show routes <device>
    # ------------------------------------------------------------------

    def _cmd_show_routes(self, cmd_lower: str, state: "LessonState") -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 3:
            return ["[red]Usage:[/red] show routes <device>   e.g. show routes r1"]
        dev_name = _normalize_device(parts[2])
        device = state.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}  (valid: r1, r2, host_a, host_b)"]
        state.focused_device = dev_name
        # The routing table is shown in the persistent panel above the output
        # area; return a simple acknowledgement with the device name so the
        # panel focuses to the right device.
        lines = [f"Routing table for {dev_name.upper()} - see panel above."]
        lines.append("")
        lines.append(
            f"  {'Destination':<22}{'Gateway':<22}{'Interface':<12}{'Protocol':<12}Metric"
        )
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

    # ------------------------------------------------------------------
    # show interfaces <device>
    # ------------------------------------------------------------------

    def _cmd_show_interfaces(self, cmd_lower: str, state: "LessonState") -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 3:
            return ["[red]Usage:[/red] show interfaces <device>"]
        dev_name = _normalize_device(parts[2])
        device = state.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}"]
        lines = [f"Interfaces - {dev_name.upper()}", ""]
        lines.append(f"  {'Interface':<14}{'IP / prefix':<20}{'Network':<20}Peer")
        lines.append("  " + "─" * 62)
        for iface in device.interfaces:
            peer = iface.peer if iface.peer else "-"
            lines.append(f"  {iface.name:<14}{iface.cidr:<20}{iface.network:<20}{peer}")
        return lines

    # ------------------------------------------------------------------
    # show lpm <ip>
    # ------------------------------------------------------------------

    def _cmd_show_lpm(self, cmd_lower: str, state: "LessonState") -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 3:
            return ["[red]Usage:[/red] show lpm <ip>   e.g. show lpm 172.16.0.5"]
        dest_ip = parts[2]
        try:
            ipaddress.ip_address(dest_ip)
        except ValueError:
            return [f"[red]Invalid IP address:[/red] {dest_ip}"]

        dev_name = state.focused_device or "r1"
        device = state.topology.devices.get(dev_name)
        if device is None:
            device = state.topology.devices.get("r1")
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

    # ------------------------------------------------------------------
    # ping <ip>
    # ------------------------------------------------------------------

    def _cmd_ping(self, cmd_lower: str, state: "LessonState") -> list[str]:
        parts = cmd_lower.split()
        if len(parts) < 2:
            return ["[red]Usage:[/red] ping <ip>"]
        dest_ip = parts[1]
        try:
            ipaddress.ip_address(dest_ip)
        except ValueError:
            return [f"[red]Invalid IP address:[/red] {dest_ip}"]

        hops = state.topology.simulate_ping("host_a", dest_ip)
        overall_success = all(h.success for h in hops) and len(hops) > 0
        state.last_ping_success[dest_ip] = overall_success

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

    # ------------------------------------------------------------------
    # route add
    # ------------------------------------------------------------------

    def _cmd_route_add(self, cmd_str: str, state: "LessonState") -> list[str]:
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

        device = state.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}  (valid: r1, r2, host_a, host_b)"]

        device.add_route(norm_network, gateway, interface, metric=1, proto="static")
        state.focused_device = dev_name

        return [
            f"[green]Route added to {dev_name.upper()}:[/green]  {norm_network}  via {gateway}  dev {interface}",
            f"[dim]Routing table for {dev_name.upper()} now has {len(device.routes)} route(s).[/dim]",
        ]

    # ------------------------------------------------------------------
    # route del
    # ------------------------------------------------------------------

    def _cmd_route_del(self, cmd_lower: str, state: "LessonState") -> list[str]:
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

        device = state.topology.devices.get(dev_name)
        if device is None:
            return [f"[red]Device not found:[/red] {dev_name}"]

        removed = device.del_route(network)
        if removed:
            state.focused_device = dev_name
            return [
                f"[green]Route removed from {dev_name.upper()}:[/green]  {network}",
                f"[dim]Routing table for {dev_name.upper()} now has {len(device.routes)} route(s).[/dim]",
            ]
        return [f"Route not found: {network} on {dev_name.upper()}"]

    # ------------------------------------------------------------------
    # hint
    # ------------------------------------------------------------------

    def _cmd_hint(self, state: "LessonState") -> list[str]:
        from packages.curriculum.lessons.lesson_01.lesson import build_steps
        steps = build_steps()
        idx = state.current_step - 1
        if 0 <= idx < len(steps):
            return ["Hint:", f"  [dim]{steps[idx].hint}[/dim]"]
        return ["[dim]No hint available.[/dim]"]

    # ------------------------------------------------------------------
    # next
    # ------------------------------------------------------------------

    def _cmd_next(self, state: "LessonState") -> list[str]:
        from packages.curriculum.lessons.lesson_01.lesson import build_steps
        steps = build_steps()
        idx = state.current_step - 1
        if idx >= len(steps):
            return ["[dim]Already on the last step.[/dim]"]
        step = steps[idx]
        complete, reason = step.completion_check(state)
        if not complete:
            return [
                f"Step {state.current_step} is not yet complete.",
                f"  {reason}",
                "  [dim]Type 'hint' for guidance.[/dim]",
            ]
        if state.current_step >= len(steps):
            return ["[green]All steps complete.[/green]  Type 'quit' to exit."]
        state.current_step += 1
        return [
            f"[green]Advanced to Step {state.current_step}.[/green]",
            f"[dim]{steps[state.current_step - 1].title}[/dim]",
        ]

    # ------------------------------------------------------------------
    # help
    # ------------------------------------------------------------------

    def _cmd_help(self) -> list[str]:
        return [
            "Available commands",
            "─" * 50,
            "",
            "  show diagram                          network topology diagram",
            "  show routes <dev>                     routing table  (r1, r2, host_a, host_b)",
            "  show interfaces <dev>                 interface IP addresses",
            "  show lpm <ip>                         longest prefix match walkthrough",
            "",
            "  ping <ip>                             simulate ping from Host A",
            "  traceroute <ip>                       same as ping",
            "",
            "  route add <net> via <gw> dev <iface> on <dev>",
            "  route del <net> on <dev>",
            "  Examples:",
            "    route add 172.16.0.0/24 via 10.0.0.2 dev eth1 on r1",
            "    route add 172.16.0.5/32 via 10.0.0.2 dev eth1 on r1",
            "    route del 172.16.0.0/24 on r1",
            "",
            "  hint    hint for the current step",
            "  next    advance when the current step is complete",
            "  help    this text",
            "  quit    exit",
        ]

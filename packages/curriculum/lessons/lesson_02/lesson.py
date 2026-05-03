import re
from dataclasses import dataclass
from typing import Callable

@dataclass
class LessonStep:
    number: int
    title: str
    content: str
    task: str
    completion_check: Callable
    hint: str

class LessonState:
    lesson_title = "The TCP/IP Model"
    lesson_number = 2

    def __init__(self):
        self.current_step: int = 1
        self.command_history: list[str] = []
        self.commands_run: set[str] = set()
        self.last_output: list[str] = []
        self.focused_layer: str = "none"

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
        layers = [
            ("Application",      "HTTP GET /index.html  Host: 172.16.0.10",          "app"),
            ("Transport (TCP)",  "TCP  src:49152  dst:80  seq:1000  flags:SYN",       "transport"),
            ("Network (IP)",     "IP   src:192.168.1.10  dst:172.16.0.10  TTL:64",    "network"),
            ("Physical Network", "ETH  src:aa:bb:cc:dd:ee:ff  dst:ff:ee:dd:cc:bb:aa", "physical"),
        ]
        lines = [
            "TCP/IP Model",
            "",
            f"  {'Layer':<20} Protocol / Data",
            "  " + "─" * 58,
        ]
        for layer_name, protocol, key in layers:
            row = f"  {layer_name:<20} {protocol}"
            if self.focused_layer == key:
                lines.append(f"[bold]{row}[/bold]")
            elif self.focused_layer == "all":
                lines.append(row)
            else:
                lines.append(f"[dim]{row}[/dim]")
        return lines

    def handle_command(self, cmd_str: str) -> list[str]:
        cmd_lower = re.sub(r"\s+", " ", cmd_str.strip().lower())

        if cmd_lower == "show model":
            self.focused_layer = "all"
            return _show_model()
        if cmd_lower == "show layer app":
            self.focused_layer = "app"
            return _show_layer_app()
        if cmd_lower == "show layer transport":
            self.focused_layer = "transport"
            return _show_layer_transport()
        if cmd_lower == "show layer network":
            self.focused_layer = "network"
            return _show_layer_network()
        if cmd_lower == "show layer physical":
            self.focused_layer = "physical"
            return _show_layer_physical()
        if cmd_lower == "show packet":
            return _show_packet()
        if cmd_lower in ("help", "?"):
            return _help()

        return [f"[red]Unknown command:[/red] {cmd_str}  - type 'help' for lesson commands."]

def _show_model() -> list[str]:
    return [
        "TCP/IP Model - All Layers",
        "",
        f"  {'Layer':<20} Protocol / Data",
        "  " + "─" * 58,
        f"  {'Application':<20} HTTP GET /index.html  Host: 172.16.0.10",
        f"  {'Transport (TCP)':<20} TCP  src:49152  dst:80  seq:1000  flags:SYN",
        f"  {'Network (IP)':<20} IP   src:192.168.1.10  dst:172.16.0.10  TTL:64",
        f"  {'Physical Network':<20} ETH  src:aa:bb:cc:dd:ee:ff  dst:ff:ee:dd:cc:bb:aa",
        "",
        "Each layer wraps the one above it as data travels down the stack.",
        "Use 'show layer <app|transport|network|physical>' to focus on a layer.",
    ]

def _show_layer_app() -> list[str]:
    return [
        "Application Layer",
        "",
        "  User-facing protocols: HTTP, DNS, SSH, SMTP.",
        "",
        "  Defines what the data means. An HTTP request is application-layer",
        "  data. This layer does not know or care how the data gets to the",
        "  destination -- that is the job of the layers below.",
        "",
        "    HTTP GET /index.html  Host: 172.16.0.10",
        "",
        "  The browser on Host A is requesting a web page from Host B.",
    ]

def _show_layer_transport() -> list[str]:
    return [
        "Transport Layer  (TCP)",
        "",
        "  TCP adds source/destination port numbers, sequence numbers,",
        "  and acknowledgements.",
        "",
        "  Port numbers identify which application receives the data:",
        "    80   = HTTP",
        "    443  = HTTPS",
        "    22   = SSH",
        "",
        "  Sequence numbers let TCP reassemble out-of-order packets and",
        "  detect loss. The SYN flag initiates a new connection.",
        "",
        "    TCP  src:49152  dst:80  seq:1000  flags:SYN",
    ]

def _show_layer_network() -> list[str]:
    return [
        "Network Layer  (IP)",
        "",
        "  IP adds source and destination IP addresses, a TTL field",
        "  (decremented at each hop to prevent loops), and a protocol field",
        "  identifying the transport layer (6 = TCP, 17 = UDP).",
        "",
        "  Routers operate at this layer -- they read the IP header, look up",
        "  the destination in their routing table (Lesson 1), and forward",
        "  the packet out the correct interface.",
        "",
        "    IP  src:192.168.1.10  dst:172.16.0.10  TTL:64",
        "",
        "  TTL starts at 64 and is decremented by each router. If it reaches",
        "  zero, the packet is discarded and an ICMP error is sent back.",
    ]

def _show_layer_physical() -> list[str]:
    return [
        "Physical Network Layer  (Ethernet)",
        "",
        "  Ethernet adds source and destination MAC addresses.",
        "",
        "  MAC addresses are local -- they identify devices on the same",
        "  physical link only. When a packet crosses a router, the router",
        "  strips the old Ethernet frame and creates a new one with its own",
        "  MAC address as the source.",
        "",
        "    ETH  src:aa:bb:cc:dd:ee:ff  dst:ff:ee:dd:cc:bb:aa",
        "",
        "  Host A's MAC is the source. The destination MAC is R1's interface --",
        "  the next hop on the local link, not Host B.",
    ]

def _show_packet() -> list[str]:
    return [
        "Full encapsulated packet (nested boxes):",
        "",
        "  +----------------------------------------------------------+",
        "  |  Physical Network  (Ethernet Frame)                     |",
        "  |  src: aa:bb:cc:dd:ee:ff  dst: ff:ee:dd:cc:bb:aa         |",
        "  |  +----------------------------------------------------+  |",
        "  |  |  Network  (IP Packet)                              |  |",
        "  |  |  src: 192.168.1.10  dst: 172.16.0.10  TTL: 64     |  |",
        "  |  |  +----------------------------------------------+  |  |",
        "  |  |  |  Transport  (TCP Segment)                    |  |  |",
        "  |  |  |  src: 49152  dst: 80  seq: 1000  SYN        |  |  |",
        "  |  |  |  +----------------------------------------+  |  |  |",
        "  |  |  |  |  Application  (HTTP Data)              |  |  |  |",
        "  |  |  |  |  GET /index.html  Host: 172.16.0.10   |  |  |  |",
        "  |  |  |  +----------------------------------------+  |  |  |",
        "  |  |  +----------------------------------------------+  |  |",
        "  |  +----------------------------------------------------+  |",
        "  +----------------------------------------------------------+",
        "",
        "Each layer wraps the data from the layer above.",
        "On receipt, each layer strips its own header and passes the payload up.",
    ]

def _help() -> list[str]:
    return [
        "Lesson 2 commands",
        "─" * 40,
        "",
        "  show model              all four TCP/IP layers",
        "  show layer app          application layer detail",
        "  show layer transport    transport (TCP) layer detail",
        "  show layer network      network (IP) layer detail",
        "  show layer physical     physical network layer detail",
        "  show packet             full encapsulated packet diagram",
        "",
        "  hint    hint for the current step",
        "  next    advance when the current step is complete",
        "  quit    exit",
    ]

def build_steps() -> list[LessonStep]:
    steps: list[LessonStep] = []

    steps.append(LessonStep(
        number=1,
        title="Introduction -- The TCP/IP Model",
        content=(
            "The TCP/IP model organizes network communication into four layers.\n"
            "Each layer has a specific job and hands data to the layer below\n"
            "(when sending) or above (when receiving).\n\n"
            "  Application      -- HTTP, DNS, SSH, SMTP\n"
            "  Transport (TCP)  -- ports, sequence numbers, reliability\n"
            "  Network (IP)     -- addressing, routing\n"
            "  Physical Network -- Ethernet, Wi-Fi  (physical delivery)\n\n"
            "For a detailed treatment of the TCP/IP protocol stack, see\n"
            "Rubin, 'Introduction: Networking in a Nutshell,' IEEE, 2025 [1]."
        ),
        task="show model",
        completion_check=lambda state: (
            state.has_run("show model"),
            "Type: show model",
        ),
        hint='type "show model"',
    ))

    steps.append(LessonStep(
        number=2,
        title="Application Layer",
        content=(
            "The application layer is where user-facing protocols live:\n"
            "HTTP, DNS, SSH, SMTP.\n\n"
            "It defines what the data means -- an HTTP request is application-layer\n"
            "data. This layer does not know or care how the data gets there;\n"
            "that is the lower layers' job.\n\n"
            "Common application-layer protocols:\n\n"
            "  HTTP / HTTPS   web pages\n"
            "  DNS            name-to-IP resolution\n"
            "  SSH            remote shell\n"
            "  SMTP           email delivery"
        ),
        task="show layer app",
        completion_check=lambda state: (
            state.has_run("show layer app"),
            "Type: show layer app",
        ),
        hint='type "show layer app"',
    ))

    steps.append(LessonStep(
        number=3,
        title="Transport Layer  (TCP)",
        content=(
            "TCP adds source/destination port numbers, sequence numbers,\n"
            "and acknowledgements.\n\n"
            "Port numbers identify which application on a host receives the data:\n\n"
            "  80    HTTP\n"
            "  443   HTTPS\n"
            "  22    SSH\n\n"
            "Sequence numbers allow TCP to reassemble out-of-order packets\n"
            "and detect loss. This makes TCP a reliable transport: every byte\n"
            "is accounted for and retransmitted if lost."
        ),
        task="show layer transport",
        completion_check=lambda state: (
            state.has_run("show layer transport"),
            "Type: show layer transport",
        ),
        hint='type "show layer transport"',
    ))

    steps.append(LessonStep(
        number=4,
        title="Network Layer  (IP)",
        content=(
            "IP adds source and destination IP addresses, a TTL field\n"
            "(decremented at each hop to prevent loops), and a protocol field\n"
            "identifying the transport layer (6 = TCP, 17 = UDP).\n\n"
            "Routers operate at this layer -- they read the IP header, look up\n"
            "the destination in their routing table (Lesson 1), and forward\n"
            "the packet out the correct interface.\n\n"
            "IP addressing is global and hierarchical, which is what makes\n"
            "routing across the Internet possible."
        ),
        task="show layer network",
        completion_check=lambda state: (
            state.has_run("show layer network"),
            "Type: show layer network",
        ),
        hint='type "show layer network"',
    ))

    steps.append(LessonStep(
        number=5,
        title="Physical Network Layer  (Ethernet)",
        content=(
            "Ethernet adds source and destination MAC addresses.\n\n"
            "MAC addresses are local -- they identify devices on the same\n"
            "physical link only. When a packet crosses a router, the router\n"
            "strips the old Ethernet frame and creates a new one with its own\n"
            "MAC address as the source.\n\n"
            "The IP addresses stay the same end-to-end;\n"
            "the MAC addresses change at every router hop."
        ),
        task="show layer physical",
        completion_check=lambda state: (
            state.has_run("show layer physical"),
            "Type: show layer physical",
        ),
        hint='type "show layer physical"',
    ))

    steps.append(LessonStep(
        number=6,
        title="Lesson Complete",
        content=(
            "Each layer only knows about the layer directly above and below it.\n"
            "The application doesn't see MAC addresses; Ethernet doesn't see ports.\n"
            "Encapsulation keeps each layer independent.\n\n"
            "Lesson 3  Network diagnostic commands\n"
            "Lesson 4  Visualizing packet transmission\n"
            "Lesson 5  TCP congestion control"
        ),
        task="next",
        completion_check=lambda state: (True, ""),
        hint="next",
    ))

    return steps

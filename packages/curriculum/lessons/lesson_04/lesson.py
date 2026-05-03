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

# MAC addresses for the simulated network
MACS = {
    "host_a":  "aa:aa:aa:aa:aa:aa",
    "r1_eth0": "bb:bb:bb:bb:bb:01",   # R1 LAN-side (faces Host A)
    "r1_eth1": "bb:bb:bb:bb:bb:02",   # R1 WAN-side (faces R2)
    "r2_eth0": "cc:cc:cc:cc:cc:01",   # R2 WAN-side (faces R1)
    "r2_eth1": "cc:cc:cc:cc:cc:02",   # R2 LAN-side (faces Host B)
    "host_b":  "dd:dd:dd:dd:dd:dd",
}

# State of the packet at each hop (after that device processes it)
# position 0 = Host A (packet created, not yet sent)
# position 1 = R1     (R1 has processed and is about to forward)
# position 2 = R2     (R2 has processed and is about to deliver)
# position 3 = Host B (delivered)
_HOP_DATA = {
    0: {
        "name":    "Host A",
        "ttl":     64,
        "eth_src": MACS["host_a"],
        "eth_dst": MACS["r1_eth0"],
        "action":  (
            "Packet created at Host A.\n"
            "  Default route: 0.0.0.0/0 via 192.168.1.1 (R1)\n"
            "  IP header set: src=192.168.1.10  dst=172.16.0.10  TTL=64\n"
            "  Ethernet frame: src=Host_A  dst=R1_eth0  (local link only)"
        ),
    },
    1: {
        "name":    "Router R1",
        "ttl":     63,
        "eth_src": MACS["r1_eth1"],
        "eth_dst": MACS["r2_eth0"],
        "action":  (
            "R1 received the frame, stripped the Ethernet header, read the IP header.\n"
            "  Routing lookup: 172.16.0.10 matched 172.16.0.0/24, next hop = 10.0.0.2\n"
            "  TTL decremented: 64 -> 63\n"
            "  New Ethernet frame: src=R1_eth1  dst=R2_eth0  (WAN link)"
        ),
    },
    2: {
        "name":    "Router R2",
        "ttl":     62,
        "eth_src": MACS["r2_eth1"],
        "eth_dst": MACS["host_b"],
        "action":  (
            "R2 received the frame, stripped the Ethernet header, read the IP header.\n"
            "  Routing lookup: 172.16.0.10 matched 172.16.0.0/24, directly connected\n"
            "  TTL decremented: 63 -> 62\n"
            "  New Ethernet frame: src=R2_eth1  dst=Host_B  (LAN link)"
        ),
    },
    3: {
        "name":    "Host B",
        "ttl":     62,
        "eth_src": MACS["r2_eth1"],
        "eth_dst": MACS["host_b"],
        "action":  (
            "Host B received the Ethernet frame.\n"
            "  Stripped Ethernet header, passed IP packet to the OS network stack.\n"
            "  Stripped IP header, passed payload to the application.\n"
            "  Packet delivered."
        ),
    },
}

# Diagram line and marker column for each position
_DIAGRAM = """\
+--------+          +----------+            +----------+          +--------+
| Host A |__________| Router   |____________| Router   |__________| Host B |
|        | eth0     |   R1     | eth1  eth0 |   R2     | eth1     |        |
| .1.10  | .1.1/24  | .1.1/24  |  10.0.0/30 | 10.0.0.2 | .0.1/24  | .0.10  |
+--------+          +----------+            +----------+          +--------+"""

# Column (0-indexed) for the ^ marker under each device
_MARKER_COL = {0: 4, 1: 25, 2: 49, 3: 70}
_DEVICE_LABEL = {0: "you", 1: "R1", 2: "R2", 3: "Host B"}

class LessonState:
    lesson_title = "Visualizing Packet Transmission"
    lesson_number = 4

    def __init__(self):
        self.current_step: int = 1
        self.command_history: list[str] = []
        self.commands_run: set[str] = set()
        self.last_output: list[str] = []
        self.position: int = 0        # current packet hop (0-3)
        self.packet_sent: bool = False # True once the user has run 'step' at least once

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
        lines = list(_DIAGRAM.splitlines())

        # Position marker row
        col = _MARKER_COL[self.position]
        lines.append(" " * col + "^")
        lines.append(" " * col + _DEVICE_LABEL[self.position])
        lines.append("")

        if not self.packet_sent:
            lines.append("  Packet not yet sent.  Type 'step' to send from Host A.")
        else:
            hop = _HOP_DATA[self.position]
            lines.append(f"  IP src:    192.168.1.10        (unchanged throughout)")
            lines.append(f"  IP dst:    172.16.0.10         (unchanged throughout)")
            lines.append(f"  TTL:       {hop['ttl']}")
            lines.append(f"  ETH src:   {hop['eth_src']}")
            lines.append(f"  ETH dst:   {hop['eth_dst']}")

        return lines

    def handle_command(self, cmd_str: str) -> list[str]:
        cmd_lower = re.sub(r"\s+", " ", cmd_str.strip().lower())

        if cmd_lower in ("step", "send", "forward"):
            return self._cmd_step()
        if cmd_lower == "inspect":
            return self._cmd_inspect()
        if cmd_lower in ("show diagram", "diagram"):
            return self._cmd_show_diagram()
        if cmd_lower in ("help", "?"):
            return _help()

        return [f"[red]Unknown command:[/red] {cmd_str}  - type 'help' for lesson commands."]

    def _cmd_step(self) -> list[str]:
        if self.position >= 3:
            return ["The packet has already been delivered.  Type 'inspect' to review."]

        self.packet_sent = True
        self.position += 1
        hop = _HOP_DATA[self.position]

        lines = [
            f"Packet advanced to {hop['name']}.",
            "",
        ]
        lines += hop["action"].splitlines()
        return lines

    def _cmd_inspect(self) -> list[str]:
        if not self.packet_sent:
            return ["No packet in flight yet.  Type 'step' to send it."]

        hop = _HOP_DATA[self.position]
        lines = [
            f"Packet headers at {hop['name']}",
            "─" * 50,
            "",
            f"  IP header:",
            f"    src:       192.168.1.10",
            f"    dst:       172.16.0.10",
            f"    TTL:       {hop['ttl']}",
            f"    protocol:  6 (TCP)",
            "",
            f"  Ethernet frame:",
            f"    src:       {hop['eth_src']}",
            f"    dst:       {hop['eth_dst']}",
            "",
        ]
        lines += hop["action"].splitlines()
        return lines

    def _cmd_show_diagram(self) -> list[str]:
        return self.render_state()

def _help() -> list[str]:
    return [
        "Lesson 4 commands",
        "─" * 40,
        "",
        "  step      advance the packet one hop",
        "  inspect   show detailed packet headers at the current hop",
        "  diagram   show the network diagram with packet position",
        "",
        "  hint    hint for the current step",
        "  next    advance when the current step is complete",
        "  quit    exit",
    ]

def build_steps() -> list[LessonStep]:
    steps: list[LessonStep] = []

    steps.append(LessonStep(
        number=1,
        title="Introduction -- A Packet's Journey",
        content=(
            "A packet traveling from Host A to Host B crosses two routers.\n"
            "At each hop, something changes and something stays the same.\n\n"
            "Watch:\n\n"
            "  IP addresses (src/dst)   stay the same the entire trip.\n"
            "  Ethernet MAC addresses   change at every single hop.\n"
            "  TTL                      decrements by 1 at each router.\n\n"
            "This is the core difference between the Network layer (IP, end-to-end)\n"
            "and the Physical Network layer (Ethernet, link-local). IP identifies\n"
            "the endpoints; Ethernet identifies the next device on the current link.\n\n"
            "The network below is the same one from Lesson 1."
        ),
        task="step",
        completion_check=lambda state: (
            state.packet_sent,
            "Type: step",
        ),
        hint="step",
    ))

    steps.append(LessonStep(
        number=2,
        title="At Router R1",
        content=(
            "The packet has arrived at R1.\n\n"
            "R1 operates at the Network layer. When it receives an Ethernet frame:\n\n"
            "  1. Strip the Ethernet header (Physical Network — only relevant for this link).\n"
            "  2. Read the IP destination: 172.16.0.10.\n"
            "  3. Look up 172.16.0.10 in the routing table.\n"
            "     Matches 172.16.0.0/24, next hop = R2 (10.0.0.2).\n"
            "  4. Decrement TTL.  If TTL reaches 0, drop and send ICMP Time Exceeded.\n"
            "  5. Build a new Ethernet frame for the R1-to-R2 link, addressed to R2's MAC.\n\n"
            "The IP header (src, dst) is untouched.\n"
            "The Ethernet frame is completely new."
        ),
        task="inspect  then  step",
        completion_check=lambda state: (
            state.has_run("inspect") and state.position >= 2,
            "Run 'inspect' to see the packet headers, then 'step' to forward to R2.",
        ),
        hint="inspect  then  step",
    ))

    steps.append(LessonStep(
        number=3,
        title="At Router R2",
        content=(
            "The packet is now at R2. R2 performs the same process:\n\n"
            "  1. Strip Ethernet header.\n"
            "  2. Look up 172.16.0.10.  Matched 172.16.0.0/24 -- directly connected.\n"
            "  3. Decrement TTL.\n"
            "  4. Build a new Ethernet frame addressed directly to Host B's MAC.\n\n"
            "Because 172.16.0.0/24 is directly connected on R2's eth1, R2 can\n"
            "address the frame straight to Host B without another routing hop.\n\n"
            "This is the last router.  One more step delivers the packet."
        ),
        task="step",
        completion_check=lambda state: (
            state.position >= 3,
            "Type: step",
        ),
        hint="step",
    ))

    steps.append(LessonStep(
        number=4,
        title="Delivered -- What Changed, What Didn't",
        content=(
            "The packet has reached Host B.\n\n"
            "Across the full journey:\n\n"
            "  Hop   Device   TTL   ETH src         ETH dst\n"
            "  ───────────────────────────────────────────────────────────────\n"
            "  0     Host A   64    aa:aa:aa:aa:aa   bb:bb:bb:bb:bb:01 (R1)\n"
            "  1     R1       63    bb:bb:bb:bb:02   cc:cc:cc:cc:cc:01 (R2)\n"
            "  2     R2       62    cc:cc:cc:cc:02   dd:dd:dd:dd:dd:dd (Host B)\n\n"
            "IP src (192.168.1.10) and IP dst (172.16.0.10) never changed.\n\n"
            "The TTL field exists precisely to prevent routing loops -- if a\n"
            "misconfigured network sent a packet in a circle, TTL would hit 0\n"
            "and the packet would be dropped rather than looping forever."
        ),
        task="inspect",
        completion_check=lambda state: (
            state.has_run("inspect") and state.position == 3,
            "Type: inspect",
        ),
        hint="inspect",
    ))

    steps.append(LessonStep(
        number=5,
        title="Lesson Complete",
        content=(
            "IP is end-to-end; Ethernet is hop-to-hop. That distinction\n"
            "shows up in every packet trace you'll ever read.\n\n"
            "Lesson 5  TCP congestion control"
        ),
        task="next",
        completion_check=lambda state: (True, ""),
        hint="next",
    ))

    return steps

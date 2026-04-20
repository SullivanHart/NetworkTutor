from dataclasses import dataclass, field
from typing import Callable, Optional
from packages.curriculum.lessons.lesson_01.network_sim import (
    Interface,
    NetworkDevice,
    NetworkTopology,
    Route,
)


# ---------------------------------------------------------------------------
# Lesson step dataclass
# ---------------------------------------------------------------------------

@dataclass
class LessonStep:
    number: int
    title: str
    content: str          # plain text shown in the step panel
    task: str             # command(s) the user must run
    completion_check: Callable  # (state: LessonState) -> (bool, str)
    hint: str             # shown when user types 'hint'


# ---------------------------------------------------------------------------
# Lesson state
# ---------------------------------------------------------------------------

class LessonState:
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


# ---------------------------------------------------------------------------
# Build the initial topology
# ---------------------------------------------------------------------------

ASCII_DIAGRAM = """\
Office A (192.168.1.0/24)                   Office B (172.16.0.0/24)

+--------+          +----------+            +----------+          +--------+
| Host A |__________| Router   |____________| Router   |__________| Host B |
|        | eth0     |   R1     | eth1  eth0 |   R2     | eth1     |        |
| .1.10  | .1.1/24  | .1.1/24  |  10.0.0/30 | 10.0.0.2 | .0.1/24  | .0.10  |
+--------+          +----------+            +----------+          +--------+
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


# ---------------------------------------------------------------------------
# Completion check helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Build lesson steps
# ---------------------------------------------------------------------------

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
        hint="type \"show diagram\"",
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
        hint="type \"show routes r1\"",
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
        hint="type \"ping 172.16.0.10\"",
    ))

    steps.append(LessonStep(
        number=4,
        title="Fix the Routing Table -- Add a Static Route",
        content=(
            "R1 has no route to 172.16.0.0/24 (Office B). When it receives\n"
            "a packet for 172.16.0.10, it finds no matching entry and drops it.\n\n"
            "Fix: add a static route telling R1 where to send those packets.\n\n"
            "  For traffic to 172.16.0.0/24, forward to R2 (10.0.0.2) via eth1.\n\n"
            "Equivalent commands on real systems:\n\n"
            "  Linux:      ip route add 172.16.0.0/24 via 10.0.0.2 dev eth1\n"
            "  Cisco IOS:  ip route 172.16.0.0 255.255.255.0 10.0.0.2\n\n"
            "Watch the routing table update as soon as you run the command."
        ),
        task="route add 172.16.0.0/24 via 10.0.0.2 dev eth1 on r1",
        completion_check=_r1_has_route_to_office_b,
        hint="type \"route add 172.16.0.0/24 via 10.0.0.2 dev eth1 on r1\"",
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
        hint="type \"ping 172.16.0.10\"",
    ))

    steps.append(LessonStep(
        number=6,
        title="Lesson Complete",
        content=(
            "You have completed Lesson 1.\n\n"
            "What you learned:\n\n"
            "  - What a routing table is and how each field is used\n"
            "  - How to read a routing table and spot a missing route\n"
            "  - How to add a static route\n"
            "  - How packets are forwarded hop-by-hop across routers\n\n"
            "Coming up:\n\n"
            "  Lesson 2  The TCP/IP model and protocol layers\n"
            "  Lesson 3  Network diagnostic commands  (ping, ip a, netstat, ss)\n"
            "  Lesson 4  TCP congestion control\n"
        ),
        task="quit",
        completion_check=lambda state: (True, ""),
        hint="quit",
    ))

    return steps

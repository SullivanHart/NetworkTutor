import re
from dataclasses import dataclass, field
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
    lesson_title = "TCP Congestion Control"
    lesson_number = 5

    def __init__(self):
        self.current_step: int = 1
        self.command_history: list[str] = []
        self.commands_run: set[str] = set()
        self.last_output: list[str] = []
        self.cwnd: float = 1.0
        self.ssthresh: float = 64.0
        self.rtt: int = 0
        self.phase: str = "slow_start"
        self.history: list[tuple[int, float]] = [(0, 1.0)]
        self._timeout_run: bool = False
        self._triple_dup_run: bool = False

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
        phase_display = "Slow Start" if self.phase == "slow_start" else "Congestion Avoidance"
        sent_bytes = int(self.cwnd * 1460 * self.rtt) if self.rtt > 0 else 0
        sent_display = f"~{sent_bytes // 1024} KB" if sent_bytes >= 1024 else f"{sent_bytes} B"

        lines = [
            "TCP Congestion Control Simulation",
            "",
            f"  cwnd:      {self.cwnd:.0f} MSS       "
            f"ssthresh:  {self.ssthresh:.0f} MSS      "
            f"phase: {phase_display}",
            f"  RTT:       {self.rtt:<12} sent:      {sent_display}",
            "",
        ]
        lines += _build_graph(self.history)
        return lines

    def _advance_rtt(self):
        self.rtt += 1
        if self.phase == "slow_start":
            self.cwnd = min(self.cwnd * 2, self.ssthresh * 2)
            if self.cwnd >= self.ssthresh:
                self.phase = "cong_avoid"
        else:
            self.cwnd += 1.0
        self.history.append((self.rtt, self.cwnd))

    def _do_timeout(self):
        self.ssthresh = max(self.cwnd / 2, 2.0)
        self.cwnd = 1.0
        self.phase = "slow_start"
        self._timeout_run = True
        self.rtt += 1
        self.history.append((self.rtt, self.cwnd))

    def _do_triple_dup(self):
        self.ssthresh = max(self.cwnd / 2, 2.0)
        self.cwnd = self.ssthresh
        self.phase = "cong_avoid"
        self._triple_dup_run = True
        self.rtt += 1
        self.history.append((self.rtt, self.cwnd))

    def handle_command(self, cmd_str: str) -> list[str]:
        cmd_lower = re.sub(r"\s+", " ", cmd_str.strip().lower())

        if cmd_lower == "rtt":
            return self._cmd_rtt()
        if cmd_lower == "timeout":
            return self._cmd_timeout()
        if cmd_lower == "triple-dup":
            return self._cmd_triple_dup()
        if cmd_lower == "reset":
            return self._cmd_reset()
        if cmd_lower == "show cwnd":
            return self._cmd_show_cwnd()
        if cmd_lower == "show graph":
            return self._cmd_show_graph()
        if cmd_lower in ("help", "?"):
            return _help()

        return [f"[red]Unknown command:[/red] {cmd_str}  - type 'help' for lesson commands."]

    def _cmd_rtt(self) -> list[str]:
        old_cwnd = self.cwnd
        old_phase = self.phase
        self._advance_rtt()
        phase_display = "Slow Start" if self.phase == "slow_start" else "Congestion Avoidance"
        lines = [
            f"RTT {self.rtt}:",
            f"  phase:    {phase_display}",
            f"  cwnd:     {old_cwnd:.0f} MSS  ->  {self.cwnd:.0f} MSS",
        ]
        if old_phase == "slow_start" and self.phase == "cong_avoid":
            lines.append(
                f"  [green]Transitioned to Congestion Avoidance[/green]"
                f"  (cwnd reached ssthresh={self.ssthresh:.0f})"
            )
        elif self.phase == "slow_start":
            lines.append(f"  [dim]Slow Start: doubled cwnd  (ssthresh={self.ssthresh:.0f})[/dim]")
        else:
            lines.append(f"  [dim]Congestion Avoidance: +1 MSS per RTT[/dim]")
        return lines

    def _cmd_timeout(self) -> list[str]:
        old_cwnd = self.cwnd
        self._do_timeout()
        return [
            f"Timeout event at RTT {self.rtt}:",
            f"  ssthresh:  {old_cwnd:.0f} / 2  =  {self.ssthresh:.0f} MSS",
            f"  cwnd:      reset to 1 MSS  (was {old_cwnd:.0f})",
            f"  phase:     Slow Start",
            "",
            "[red]Timeout is treated as severe congestion.[/red]",
            "cwnd is reset to 1 and Slow Start begins again.",
        ]

    def _cmd_triple_dup(self) -> list[str]:
        old_cwnd = self.cwnd
        self._do_triple_dup()
        return [
            f"3 duplicate ACKs (Fast Retransmit) at RTT {self.rtt}:",
            f"  ssthresh:  {old_cwnd:.0f} / 2  =  {self.ssthresh:.0f} MSS",
            f"  cwnd:      set to ssthresh  =  {self.cwnd:.0f} MSS  (was {old_cwnd:.0f})",
            f"  phase:     Congestion Avoidance  (no Slow Start restart)",
            "",
            "[yellow]Fast Retransmit is less severe than timeout.[/yellow]",
            "Later packets got through, so the connection is still alive.",
            "TCP Reno halves cwnd but skips Slow Start.",
        ]

    def _cmd_reset(self) -> list[str]:
        self.cwnd = 1.0
        self.ssthresh = 64.0
        self.rtt = 0
        self.phase = "slow_start"
        self.history = [(0, 1.0)]
        self._timeout_run = False
        self._triple_dup_run = False
        return ["Simulation reset to initial state.", "  cwnd=1  ssthresh=64  phase=Slow Start"]

    def _cmd_show_cwnd(self) -> list[str]:
        phase_display = "Slow Start" if self.phase == "slow_start" else "Congestion Avoidance"
        return [
            f"cwnd:      {self.cwnd:.0f} MSS",
            f"ssthresh:  {self.ssthresh:.0f} MSS",
            f"phase:     {phase_display}",
            f"RTT:       {self.rtt}",
        ]

    def _cmd_show_graph(self) -> list[str]:
        lines = ["cwnd history:"]
        lines += _build_graph(self.history)
        return lines

def _build_graph(history: list[tuple[int, float]]) -> list[str]:
    if not history:
        return ["  [dim](no history)[/dim]"]

    max_cwnd = max(v for _, v in history)
    if max_cwnd <= 0:
        max_cwnd = 1.0

    # Choose a set of y-axis tick values
    graph_height = 6
    tick_step = max(1, round(max_cwnd / graph_height))

    ticks = []
    t = tick_step
    while t <= max_cwnd + tick_step:
        ticks.append(t)
        t += tick_step
    ticks = sorted(set(ticks), reverse=True)

    # Build a dict: rtt -> cwnd for quick lookup
    rtt_to_cwnd: dict[int, float] = {}
    for rtt_val, cwnd_val in history:
        rtt_to_cwnd[rtt_val] = cwnd_val

    max_rtt = max(r for r, _ in history)
    rtt_range = list(range(0, max_rtt + 1))

    y_label_width = len(str(int(ticks[0]))) + 1

    lines = ["  cwnd history (MSS)", "  " + "─" * (y_label_width + 2 + len(rtt_range) * 2)]
    for tick in ticks:
        row_chars = []
        for rtt_val in rtt_range:
            cwnd_val = rtt_to_cwnd.get(rtt_val)
            if cwnd_val is not None and round(cwnd_val) == round(tick):
                row_chars.append("* ")
            else:
                row_chars.append("  ")
        label = str(int(tick)).rjust(y_label_width)
        lines.append(f"  {label} |{''.join(row_chars)}")

    # X-axis
    x_axis = "  " + " " * y_label_width + " └" + "──" * len(rtt_range)
    lines.append(x_axis)

    # X-axis labels (RTT numbers)
    x_label_parts = []
    for rtt_val in rtt_range:
        x_label_parts.append(str(rtt_val).ljust(2))
    x_labels = "  " + " " * (y_label_width + 2) + "".join(x_label_parts)
    lines.append(x_labels)
    lines.append("  " + " " * (y_label_width + 2) + "RTT")

    return lines

def _help() -> list[str]:
    return [
        "Lesson 5 commands",
        "─" * 40,
        "",
        "  rtt           simulate one round-trip time, update cwnd",
        "  timeout       simulate timeout event (severe congestion)",
        "  triple-dup    simulate 3 dup ACKs / fast retransmit (TCP Reno)",
        "  reset         reset simulation to initial state",
        "  show cwnd     print current cwnd, ssthresh, phase",
        "  show graph    print cwnd history graph",
        "",
        "  hint    hint for the current step",
        "  next    advance when the current step is complete",
        "  quit    exit",
    ]

def build_steps() -> list[LessonStep]:
    steps: list[LessonStep] = []

    steps.append(LessonStep(
        number=1,
        title="Introduction -- TCP Congestion Control",
        content=(
            "When multiple flows share a network link, they can overwhelm it,\n"
            "causing congestion. TCP detects congestion through packet loss and\n"
            "reduces its send rate to back off.\n\n"
            "The congestion window (cwnd) limits how much data TCP can have in\n"
            "flight at once. A larger cwnd means more data sent per RTT; a\n"
            "smaller cwnd means a slower, more conservative sender.\n\n"
            "TCP congestion control is covered in RFC 5681 and in Rubin [1].\n\n"
            "Run 'rtt' to simulate one round-trip time and watch cwnd grow."
        ),
        task="rtt",
        completion_check=lambda state: (
            state.rtt >= 1,
            "Type: rtt",
        ),
        hint='type "rtt"',
    ))

    steps.append(LessonStep(
        number=2,
        title="Slow Start",
        content=(
            "TCP starts conservatively. cwnd begins at 1 MSS (Maximum Segment\n"
            "Size, typically 1460 bytes). Each RTT without loss, cwnd doubles.\n\n"
            "This grows the send rate exponentially until it hits the slow start\n"
            "threshold (ssthresh). The name 'Slow Start' is misleading -- it\n"
            "actually grows very fast, but starts from a low base.\n\n"
            "  RTT 0: cwnd = 1 MSS\n"
            "  RTT 1: cwnd = 2 MSS\n"
            "  RTT 2: cwnd = 4 MSS\n"
            "  RTT 3: cwnd = 8 MSS\n\n"
            "Keep running 'rtt' until you have run it at least 6 times total."
        ),
        task="rtt  (run until RTT >= 6)",
        completion_check=lambda state: (
            state.rtt >= 6,
            f"Current RTT = {state.rtt}. Run 'rtt' until RTT >= 6.",
        ),
        hint='type "rtt" repeatedly until RTT reaches 6',
    ))

    steps.append(LessonStep(
        number=3,
        title="Congestion Avoidance",
        content=(
            "Once cwnd reaches ssthresh, TCP slows its growth to additive\n"
            "increase: +1 MSS per RTT instead of doubling.\n\n"
            "This is gentler than doubling. The idea is to probe for available\n"
            "bandwidth without causing a collapse. Combined with the halving\n"
            "that happens on loss, this forms the AIMD (Additive Increase /\n"
            "Multiplicative Decrease) algorithm.\n\n"
            "Run 'rtt' 4 more times and observe the slower linear growth.\n"
            "Watch the cwnd history graph in the state panel."
        ),
        task="rtt  (run until RTT >= 10)",
        completion_check=lambda state: (
            state.rtt >= 10,
            f"Current RTT = {state.rtt}. Run 'rtt' until RTT >= 10.",
        ),
        hint='type "rtt" repeatedly until RTT reaches 10',
    ))

    steps.append(LessonStep(
        number=4,
        title="Timeout Event",
        content=(
            "A timeout means a packet was lost and the ACK never arrived within\n"
            "the retransmit timeout period. TCP treats this as severe congestion.\n\n"
            "On timeout:\n\n"
            "  ssthresh = max(cwnd / 2, 2)\n"
            "  cwnd     = 1 MSS\n"
            "  phase    = Slow Start\n\n"
            "This is a harsh reaction because a timeout suggests the network\n"
            "may be seriously congested or a router's buffer has overflowed.\n"
            "Starting over with cwnd=1 gives the network time to recover."
        ),
        task="timeout",
        completion_check=lambda state: (
            state._timeout_run,
            "Type: timeout",
        ),
        hint='type "timeout"',
    ))

    steps.append(LessonStep(
        number=5,
        title="Fast Retransmit (TCP Reno)",
        content=(
            "If TCP receives 3 duplicate ACKs for the same packet, it knows\n"
            "that packet was lost but the connection is still alive (later\n"
            "packets got through). This is called fast retransmit.\n\n"
            "TCP Reno treats this less severely than a timeout:\n\n"
            "  ssthresh = max(cwnd / 2, 2)\n"
            "  cwnd     = ssthresh\n"
            "  phase    = Congestion Avoidance  (no Slow Start restart)\n\n"
            "Run a few 'rtt' commands to rebuild cwnd, then run 'triple-dup'\n"
            "to simulate 3 duplicate ACKs."
        ),
        task="triple-dup",
        completion_check=lambda state: (
            state._triple_dup_run,
            "Type: triple-dup  (run some 'rtt' commands first to rebuild cwnd)",
        ),
        hint='type "triple-dup"',
    ))

    steps.append(LessonStep(
        number=6,
        title="Lesson Complete",
        content=(
            "TCP Reno was standardized in RFC 5681. Modern stacks use\n"
            "CUBIC or BBR, but the Slow Start / Congestion Avoidance\n"
            "state machine is still the foundation."
        ),
        task="",
        completion_check=lambda state: (True, ""),
        hint="",
    ))

    return steps

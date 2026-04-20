"""
app.py - Main render/input loop for the Network Tutor.

VimTutor mechanic:
  render() -> input -> dispatch -> check completion -> render() -> ...

The screen is cleared and fully redrawn after every command so the
routing table always reflects the live network state.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from rich.console import Console

from cli.src.theme import TUTOR_THEME
from cli.src.router import CommandRouter

if TYPE_CHECKING:
    from packages.curriculum.lessons.lesson_01.lesson import LessonState

console = Console(theme=TUTOR_THEME, highlight=False)
_router = CommandRouter()

LESSON_TITLE = "Routing Tables and Longest Prefix Match"

def _clear():
    os.system("cls" if os.name == "nt" else "clear")

def _rule(width: int = 72) -> str:
    return "─" * width

# ---------------------------------------------------------------------------
# NetTutorApp
# ---------------------------------------------------------------------------

class NetTutorApp:
    def __init__(self, lesson_state: "LessonState"):
        self.state = lesson_state
        self._steps = None
        self._quit = False

    # ------------------------------------------------------------------
    # Step helpers
    # ------------------------------------------------------------------

    def _get_steps(self):
        if self._steps is None:
            from packages.curriculum.lessons.lesson_01.lesson import build_steps
            self._steps = build_steps()
        return self._steps

    def _current_step(self):
        steps = self._get_steps()
        idx = self.state.current_step - 1
        if 0 <= idx < len(steps):
            return steps[idx]
        return None

    # ------------------------------------------------------------------
    # Render sections
    # ------------------------------------------------------------------

    def _print_header(self):
        steps = self._get_steps()
        n = len(steps)
        step_info = f"Step {self.state.current_step}/{n}"
        header = f"Network Tutor  |  Lesson 1: {LESSON_TITLE}  |  {step_info}"
        console.print(header)
        console.print(_rule())

    def _print_step(self):
        step = self._current_step()
        if step is None:
            return
        console.print()
        console.print(f"[bold]Step {step.number}: {step.title}[/bold]")
        console.print(_rule(len(f"Step {step.number}: {step.title}")))
        console.print()
        console.print(step.content)
        console.print()
        complete, _ = step.completion_check(self.state)
        console.print(f"  Task: {step.task}")
        if complete:
            console.print()
            console.print("  [green]Step complete.[/green]  Type 'next' to advance.")

    def _print_routing_table(self):
        console.print()
        console.print(_rule())
        dev_name = self.state.focused_device or "r1"
        device = self.state.topology.devices.get(dev_name)
        if device is None:
            console.print(f"Routing table: {dev_name}  (not found)")
            return
        n = len(device.routes)
        console.print(f"Routing table: {dev_name.upper()}  ({n} route{'s' if n != 1 else ''})")
        console.print()
        col = f"  {'Destination':<22}{'Gateway':<22}{'Interface':<12}{'Protocol':<12}{'Metric'}"
        console.print(f"[dim]{col}[/dim]")
        console.print(f"  [dim]{_rule(68)}[/dim]")
        if not device.routes:
            console.print("  [dim](empty)[/dim]")
        else:
            sorted_routes = sorted(device.routes, key=lambda r: (-r.prefix_len, r.network))
            for route in sorted_routes:
                gw = route.gateway if route.gateway else "directly connected"
                # dim connected routes; leave static routes plain so the student-added
                # route stands out from the pre-existing ones
                style = "dim" if route.proto == "connected" else ""
                row = f"  {route.network:<22}{gw:<22}{route.interface:<12}{route.proto:<12}{route.metric}"
                if style:
                    console.print(f"[{style}]{row}[/{style}]")
                else:
                    console.print(row)

    def _print_output(self):
        console.print()
        console.print(_rule())
        lines = self.state.last_output
        if not lines:
            console.print("[dim](no output yet)[/dim]")
        else:
            for line in lines:
                console.print(line)

    def _print_command_bar(self):
        console.print()
        console.print(_rule())
        console.print(
            "[dim]  show routes <dev>   show diagram   ping <ip>   "
            "route add <net> via <gw> dev <iface> on <dev>[/dim]"
        )
        console.print(
            "[dim]  route del <net> on <dev>   show lpm <ip>   "
            "show interfaces <dev>   hint   next   help   quit[/dim]"
        )

    # ------------------------------------------------------------------
    # Full screen render
    # ------------------------------------------------------------------

    def render(self):
        _clear()
        self._print_header()
        self._print_step()
        self._print_routing_table()
        self._print_output()
        self._print_command_bar()

    # ------------------------------------------------------------------
    # Step completion notification
    # ------------------------------------------------------------------

    def _check_completion(self, old_step: int) -> list[str]:
        steps = self._get_steps()
        idx = self.state.current_step - 1
        if idx >= len(steps):
            return []
        step = steps[idx]
        complete, _ = step.completion_check(self.state)
        if complete and self.state.current_step == old_step:
            return ["", "[green]Step complete.[/green]  Type 'next' to advance."]
        return []

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        self.render()
        while not self._quit:
            try:
                console.print()
                cmd_str = console.input("nettutor> ")
            except (EOFError, KeyboardInterrupt):
                console.print("\nGoodbye.")
                break

            if not cmd_str.strip():
                self.render()
                continue

            if cmd_str.strip().lower() in ("quit", "exit", "q"):
                console.print("\nGoodbye.\n")
                break

            old_step = self.state.current_step
            self.state.record_command(cmd_str)

            output_lines = _router.dispatch(cmd_str, self.state)
            output_lines += self._check_completion(old_step)
            self.state.last_output = output_lines

            self.render()

from __future__ import annotations

import os

from rich.console import Console

from cli.src.theme import TUTOR_THEME
from cli.src.router import CommandRouter

console = Console(theme=TUTOR_THEME, highlight=False)
_router = CommandRouter()

def _clear():
    os.system("cls" if os.name == "nt" else "clear")

def _rule(width: int = 72) -> str:
    return "─" * width

class NetTutorApp:
    def __init__(self, lesson_state):
        self.state = lesson_state
        self.lesson_complete = False

    def _print_header(self):
        steps = self.state.get_steps()
        n = len(steps)
        step_info = f"Step {min(self.state.current_step, n)}/{n}"
        lesson_num = self.state.lesson_number
        lesson_title = self.state.lesson_title
        header = f"Network Tutor  |  Lesson {lesson_num}: {lesson_title}  |  {step_info}"
        console.print(header)
        console.print(_rule())

    def _print_step(self):
        step = self.state.get_step(self.state.current_step)
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
            steps = self.state.get_steps()
            if self.state.current_step >= len(steps):
                from packages.curriculum.lesson_registry import get_lesson
                next_n = self.state.lesson_number + 1
                if get_lesson(next_n):
                    console.print(f"  [green]Lesson complete.[/green]  Type 'next' to continue to Lesson {next_n}.")
                else:
                    console.print("  [green]All lessons complete.[/green]  Type 'quit' to exit.")
            else:
                console.print("  [green]Step complete.[/green]  Type 'next' to advance.")

    def _print_state_panel(self):
        console.print()
        console.print(_rule())
        lines = self.state.render_state()
        for line in lines:
            console.print(line)

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
        console.print("[dim]  hint   next   help   quit[/dim]")

    def render(self):
        _clear()
        self._print_header()
        self._print_step()
        self._print_state_panel()
        self._print_output()
        self._print_command_bar()

    def _check_completion(self, old_step: int) -> list[str]:
        steps = self.state.get_steps()
        idx = self.state.current_step - 1
        if idx >= len(steps):
            return []
        # Last step: completion shown in step panel, not output panel
        if self.state.current_step >= len(steps):
            return []
        step = steps[idx]
        complete, _ = step.completion_check(self.state)
        if complete and self.state.current_step == old_step:
            return ["", "[green]Step complete.[/green]  Type 'next' to advance."]
        return []

    def run(self):
        self.render()
        while True:
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
                console.print()
                break

            old_step = self.state.current_step
            self.state.record_command(cmd_str)

            # 'next' on the last complete step advances to the next lesson
            steps = self.state.get_steps()
            if (cmd_str.strip().lower() == "next"
                    and self.state.current_step >= len(steps)
                    and steps[-1].completion_check(self.state)[0]):
                self.lesson_complete = True
                break

            output_lines = _router.dispatch(cmd_str, self.state)
            output_lines += self._check_completion(old_step)
            self.state.last_output = output_lines

            self.render()

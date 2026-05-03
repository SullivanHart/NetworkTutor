from __future__ import annotations

import re

class CommandRouter:

    def dispatch(self, cmd_str: str, state) -> list[str]:
        cmd_str = cmd_str.strip()
        if not cmd_str:
            return []
        cmd_lower = re.sub(r"\s+", " ", cmd_str.lower())

        if cmd_lower == "hint":
            return self._cmd_hint(state)
        if cmd_lower in ("help", "?"):
            return self._cmd_help()
        if cmd_lower == "next":
            return self._cmd_next(state)
        if cmd_lower in ("quit", "exit", "q"):
            return []

        return state.handle_command(cmd_str)

    def _cmd_hint(self, state) -> list[str]:
        step = state.get_step(state.current_step)
        if step is not None:
            return ["Hint:", f"  [dim]{step.hint}[/dim]"]
        return ["[dim]No hint available.[/dim]"]

    def _cmd_next(self, state) -> list[str]:
        steps = state.get_steps()
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
            return []
        state.current_step += 1
        next_step = state.get_step(state.current_step)
        title = next_step.title if next_step else ""
        return [
            f"[green]Advanced to Step {state.current_step}.[/green]",
            f"[dim]{title}[/dim]",
        ]

    def _cmd_help(self) -> list[str]:
        return [
            "Available commands",
            "─" * 50,
            "",
            "  hint    hint for the current step",
            "  next    advance when the current step is complete",
            "  help    this text",
            "  quit    exit",
            "",
            "Type 'help' in the current lesson for lesson-specific commands.",
        ]

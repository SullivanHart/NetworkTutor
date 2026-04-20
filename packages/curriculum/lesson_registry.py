import importlib
from typing import Optional

LESSONS: dict[int, dict] = {
    1: {
        "title": "Routing Tables and Longest Prefix Match",
        "module": "packages.curriculum.lessons.lesson_01.lesson",
        "description": (
            "Learn how routers forward packets using routing tables "
            "and the Longest Prefix Match (LPM) algorithm (RFC 1812)."
        ),
    },
}


def get_lesson(number: int) -> Optional[dict]:
    """
    Return the lesson metadata dict for a given lesson number,
    or None if not found.
    """
    return LESSONS.get(number)


def load_lesson_module(number: int):
    """
    Dynamically import and return the lesson module for a given lesson number.
    Raises KeyError if the lesson number is unknown.
    Raises ImportError if the module cannot be loaded.
    """
    entry = LESSONS.get(number)
    if entry is None:
        raise KeyError(f"Lesson {number} not found in registry.")
    module_path = entry["module"]
    return importlib.import_module(module_path)


def list_lessons() -> list[dict]:
    """Return a sorted list of all lesson metadata dicts (with 'number' key added)."""
    result = []
    for num, meta in sorted(LESSONS.items()):
        entry = dict(meta)
        entry["number"] = num
        result.append(entry)
    return result

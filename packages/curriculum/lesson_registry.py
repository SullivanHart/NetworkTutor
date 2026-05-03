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
    2: {
        "title": "The TCP/IP Model",
        "module": "packages.curriculum.lessons.lesson_02.lesson",
        "description": (
            "Explore the four layers of the TCP/IP model and see how "
            "data is encapsulated as it travels from application to wire."
        ),
    },
    3: {
        "title": "Network Diagnostic Commands",
        "module": "packages.curriculum.lessons.lesson_03.lesson",
        "description": (
            "Practice the Linux commands used to inspect network "
            "configuration and diagnose connectivity: ip addr, ip route, ping, ss."
        ),
    },
    4: {
        "title": "Visualizing Packet Transmission",
        "module": "packages.curriculum.lessons.lesson_04.lesson",
        "description": (
            "Step a packet hop-by-hop from Host A to Host B and observe "
            "how IP addresses stay fixed while Ethernet MACs and TTL change."
        ),
    },
    5: {
        "title": "TCP Congestion Control",
        "module": "packages.curriculum.lessons.lesson_05.lesson",
        "description": (
            "Simulate TCP's congestion window and observe Slow Start, "
            "Congestion Avoidance, timeout, and fast retransmit (TCP Reno)."
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

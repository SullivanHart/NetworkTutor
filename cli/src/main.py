import os
import sys

# Add the project root (two levels up from cli/src/) to sys.path so that
# both the cli and packages directories are importable.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

def _load_lesson_state(lesson_number: int):
    if lesson_number == 1:
        from packages.curriculum.lessons.lesson_01.lesson import build_topology, LessonState
        return LessonState(build_topology())
    if lesson_number == 2:
        from packages.curriculum.lessons.lesson_02.lesson import LessonState
        return LessonState()
    if lesson_number == 3:
        from packages.curriculum.lessons.lesson_03.lesson import LessonState
        return LessonState()
    if lesson_number == 4:
        from packages.curriculum.lessons.lesson_04.lesson import LessonState
        return LessonState()
    if lesson_number == 5:
        from packages.curriculum.lessons.lesson_05.lesson import LessonState
        return LessonState()
    raise KeyError(f"Lesson {lesson_number} not found.")

def main():
    lesson_number = 1

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("-h", "--help"):
            print("Usage: nettutor [lesson_number]")
            print("  lesson_number  Lesson to start (default: 1)")
            print("\nAvailable lessons:")
            try:
                from packages.curriculum.lesson_registry import list_lessons
                for entry in list_lessons():
                    print(f"  {entry['number']}: {entry['title']}")
                    print(f"     {entry['description']}")
            except Exception:
                print("  1: Routing Tables and Longest Prefix Match")
            sys.exit(0)
        try:
            lesson_number = int(arg)
        except ValueError:
            print(f"error: lesson number must be an integer, got {arg!r}", file=sys.stderr)
            sys.exit(1)

    try:
        from packages.curriculum.lesson_registry import get_lesson
        if get_lesson(lesson_number) is None:
            print(f"error: lesson {lesson_number} not found", file=sys.stderr)
            sys.exit(1)

        lesson_state = _load_lesson_state(lesson_number)

    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("install dependencies with: pip install rich", file=sys.stderr)
        sys.exit(1)

    from cli.src.app import NetTutorApp
    from packages.curriculum.lesson_registry import get_lesson

    while True:
        app = NetTutorApp(lesson_state)
        app.run()

        next_n = lesson_number + 1
        if not app.lesson_complete or get_lesson(next_n) is None:
            break

        lesson_number = next_n
        lesson_state = _load_lesson_state(lesson_number)

if __name__ == "__main__":
    main()

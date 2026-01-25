#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Get the Django project directory (where manage.py is located)
project_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_dir)

# Remove all instances of the parent directory from sys.path to prevent NewFUHI.booking imports
sys.path = [p for p in sys.path if os.path.abspath(p) != parent_dir]

# Ensure the Django project directory is at the front of sys.path
if project_dir in sys.path:
    sys.path.remove(project_dir)
sys.path.insert(0, project_dir)

# Remove duplicates while preserving order
seen = set()
sys.path = [p for p in sys.path if not (p in seen or seen.add(p))]


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
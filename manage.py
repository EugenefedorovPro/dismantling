#!/usr/bin/env python
"""Command-line utility for Django administration."""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dismantling.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()


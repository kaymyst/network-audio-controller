#!/usr/bin/env python3

import signal
import sys
import logging


def handler(signum, frame):
    sys.exit(main())


def _process_verbose_flag():
    # If user passed -v or --verbose, enable DEBUG logging early and
    # remove the flag so the CLI framework doesn't treat it as unknown.
    args = sys.argv[1:]
    verbose_flags = ["-v", "--verbose"]

    if any(flag in args for flag in verbose_flags):
        logging.basicConfig(level=logging.DEBUG)
        # Ensure the root logger and any existing handlers are DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
        for h in logging.getLogger().handlers:
            try:
                h.setLevel(logging.DEBUG)
            except Exception:
                pass

        # Also make the top-level package logger more chatty
        logging.getLogger("netaudio").setLevel(logging.DEBUG)

        # remove all occurrences so cleo doesn't error on unknown option
        sys.argv = [sys.argv[0]] + [a for a in args if a not in verbose_flags]


if __name__ == "__main__":
    _process_verbose_flag()

    from netaudio.console.application import main

    signal.signal(signal.SIGINT, handler)

    sys.exit(main())

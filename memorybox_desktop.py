from __future__ import annotations
import argparse
from memorybox.desktop import run_desktop


def main(argv=None):
    p = argparse.ArgumentParser(prog="MemoryBox")
    p.add_argument("paths", nargs="*", help="Memory Box packages to open")
    p.add_argument("--minimized", action="store_true", help="Start hidden in the system tray")
    args = p.parse_args(argv)
    return run_desktop(args.paths, minimized=args.minimized)


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import os
import sys

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")


def main():
    parser = argparse.ArgumentParser(description="DemandLens offline data and evaluation pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Download UCI data or prepare an existing workbook")
    prep.add_argument("--input", help="Path to the original UCI Online Retail workbook")
    sub.add_parser("evaluate", help="Run validation, frozen testing, and final forecasts")
    sub.add_parser("publish-demo", help="Build the local deployment bundle (does not upload)")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            from .data import prepare
            prepare(args.input)
        elif args.command == "evaluate":
            from .evaluation import evaluate
            from threadpoolctl import threadpool_limits
            with threadpool_limits(limits=2):
                evaluate()
        else:
            from .storage import publish_demo
            publish_demo()
    except (ValueError, FileNotFoundError, ImportError) as exc:
        print(f"DemandLens: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

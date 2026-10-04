from __future__ import annotations

import argparse
import getpass
import json
import logging
import os
import sys

from .backend import Backend, session_directory, error_metadata
from .errors import diagnostics, suppress_private_logs
from .connection import selected_region, login_and_save, LoginFailure


def main() -> None:
    suppress_private_logs()
    parser = argparse.ArgumentParser(description="Garminops development runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("login", "status", "serve", "probe"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--region", choices=("com", "cn"), default=None)
        if name == "probe":
            cmd.add_argument("operation")
            cmd.add_argument("--arguments", default="{}")
    args = parser.parse_args()
    region_override = args.region
    args.region = args.region or selected_region()
    # Do not emit upstream raw error bodies or credential-bearing debug logs.
    logging.getLogger("garminconnect").setLevel(logging.CRITICAL)
    if args.command == "serve":
        from .server import run
        run(region_override)
        return
    if args.command == "status":
        print(json.dumps(Backend(args.region).status(), indent=2))
        return
    if args.command == "login":
        if not sys.stdin.isatty():
            parser.error("Login requires your local interactive terminal; do not send credentials through chat.")
        os.umask(0o077)
        directory = session_directory(args.region)
        print(f"Garmin {args.region}; refresh tokens will be stored only in {directory}")
        email = input("Garmin email: ").strip()
        password = getpass.getpass("Garmin password (hidden): ")
        try:
            account = login_and_save(args.region, email, password,
                lambda: getpass.getpass("Garmin MFA code (hidden): "))
            print("Login and fresh-client resume succeeded; selected connection: " + json.dumps(account))
        except Exception as exc:
            diagnostic = json.dumps(exc.diagnostic if isinstance(exc, LoginFailure) else diagnostics(exc, stage="login", operation="login"))
            print(f"Login failed: {diagnostic}. No account-data write was requested.", file=sys.stderr)
            raise SystemExit(1) from None
        finally:
            password = None
        return
    try:
        result = Backend(args.region).read(args.operation, json.loads(args.arguments))
        print(json.dumps({"data": result}, ensure_ascii=False))
    except Exception as exc:
        metadata = error_metadata(exc)
        print(json.dumps({**metadata, **diagnostics(exc, stage=getattr(exc, "garminops_stage", "operation"), operation=args.operation, status=metadata.get("http_status"))}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

"""Explicit migration command. Database bootstrap remains outside this module."""
import argparse
import os
import sys

import psycopg

from .schema import ConfigError
from .store import migrate


def main():
    parser = argparse.ArgumentParser(description="HarpiSense configuration registry")
    parser.add_argument("command", choices=["migrate"])
    parser.parse_args()
    dsn = os.environ.get("HARPISENSE_CONFIG_MIGRATION_DSN")
    if not dsn:
        print("MIGRATION_DSN_REQUIRED", file=sys.stderr)
        return 2
    try:
        migrate(lambda: psycopg.connect(dsn))
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except psycopg.Error:
        # Connection errors can contain usernames, hosts or credential-bearing DSNs.
        print("CONFIG_MIGRATION_FAILED", file=sys.stderr)
        return 1
    print("CONFIG_SCHEMA_1_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

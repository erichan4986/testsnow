#!/usr/bin/env python3
"""Deprecated compatibility shim for Xueqiu detail extraction.

This script is no longer maintained. Use scripts/extract_detail.py instead.
"""

import argparse


MESSAGE = """\
[DEPRECATED] extract_detail_via_cdp.py is no longer supported.

Please use the canonical extraction command instead:

    cd scripts
    python extract_detail.py --stock 黑芝麻智能 --date YYYYMMDD --cdp-port 9222
    python extract_detail.py --all --date YYYYMMDD --cdp-port 9222

The new command reads featured posts from data/raw/ and extracts detail pages
via Chrome CDP with proper delays and Vault output.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Deprecated: use extract_detail.py for Xueqiu detail extraction.",
        epilog=MESSAGE,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args(argv)
    print(MESSAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

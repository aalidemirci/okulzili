from __future__ import annotations

import argparse
from pathlib import Path

from okul_zili.pilot_log import analyze_files, format_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Okul Zili pilot günlüklerinde çift zil ve sessiz başarısızlık arar."
    )
    parser.add_argument("logs", nargs="+", type=Path, help="JSONL günlük dosyaları")
    parser.add_argument("--en-az-gun", type=int, default=5)
    args = parser.parse_args()
    report = analyze_files(args.logs)
    print(format_report(report, args.en_az_gun))
    return 0 if len(report.teaching_days) >= args.en_az_gun and report.passes_safety_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())

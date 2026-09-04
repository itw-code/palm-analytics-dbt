#!/usr/bin/env python3
"""Discord alert for scheduled-run failure + synthetic-fallback / freshness warnings.

Reads the same artifacts the CI workflow already produces:
  - target/run_results.json      (dbt build PASS/WARN/ERROR counts)
  - target/freshness.json        (per-source freshness status + staleness)
  - ingestion_manifest.json      (synthetic fallback provenance)

Safe mode: DRY-RUN IS THE DEFAULT. Without --live the script only prints the
redacted payload it *would* send and exits 0. Pass --live to POST.

Secrets: webhook comes ONLY from the DISCORD_WEBHOOK_URL env var (repo secret
in CI). It is never hardcoded and never printed — logs show only
``webhook_configured=yes/no``. Missing webhook + --live = warning + exit 0
(alerting must never fail the build).

Severity:
  ERROR  job-status failure, or dbt error>0, or freshness error/fail
  WARN   synthetic_sources>0, or freshness warn, or key artifact missing
  OK     everything green (nothing posted unless --always)

Usage (CI):
  python scripts/discord_alert.py --event "$EVENT" --job-status "$STATUS" \\
      --run-url "$RUN_URL" --live
Local test (safe, no network):
  python scripts/discord_alert.py --dry-run
  python scripts/discord_alert.py --job-status failure --dry-run
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request

MANIFEST = pathlib.Path("ingestion_manifest.json")
RUN_RESULTS = pathlib.Path("target/run_results.json")
FRESHNESS = pathlib.Path("target/freshness.json")

COLORS = {"ERROR": 0xED4245, "WARN": 0xFEE75C, "OK": 0x57F287}
EMOJI = {"ERROR": "🔴", "WARN": "🟡", "OK": "🟢"}


def load_json(p):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def dbt_counts(run_results):
    counts = {"pass": 0, "warn": 0, "error": 0, "total": 0}
    if not isinstance(run_results, dict):
        return counts, False
    results = run_results.get("results", [])
    for r in results:
        s = (r.get("status") or "").lower()
        if s in ("pass", "success"):
            counts["pass"] += 1
        elif s == "warn":
            counts["warn"] += 1
        elif s in ("error", "fail", "failure"):
            counts["error"] += 1
        counts["total"] += 1
    return counts, True


def freshness_detail(freshness):
    """Return (overall, [(name, status, days_stale, max_loaded_at)])."""
    if not isinstance(freshness, dict):
        return "unknown", []
    rows = []
    for r in freshness.get("results", []):
        name = (r.get("unique_id") or "?").split(".")[-1]
        status = r.get("status") or "unknown"
        ago_s = r.get("max_loaded_at_time_ago_in_s")
        days = round(ago_s / 86400, 1) if isinstance(ago_s, (int, float)) else None
        rows.append((name, status, days, r.get("max_loaded_at")))
    statuses = [s for _, s, _, _ in rows]
    if "error" in statuses or "fail" in statuses:
        return "error", rows
    if "warn" in statuses:
        return "warn", rows
    if rows and all(s == "pass" for s in statuses):
        return "ok", rows
    return "unknown", rows


def synthetic_sources(manifest):
    """Return (count, [names]) of sources that used synthetic fallback."""
    names = []
    if not isinstance(manifest, dict):
        return 0, names
    for src, val in (manifest.get("sources") or {}).items():
        if not isinstance(val, dict):
            continue
        if "mode" in val:
            if val.get("mode") == "synthetic":
                names.append(src)
        elif any(isinstance(v, dict) and v.get("mode") == "synthetic"
                 for v in val.values()):
            names.append(src)
    count = manifest.get("synthetic_sources", len(names)) or 0
    return int(count), names


def build_payload(args, counts, have_rr, fresh_status, fresh_rows,
                   synth_count, synth_names, manifest):
    if args.job_status == "failure" or counts["error"] > 0 or fresh_status == "error":
        sev = "ERROR"
    elif (synth_count > 0 or fresh_status == "warn" or fresh_status == "unknown"
          or not have_rr):
        sev = "WARN"
    else:
        sev = "OK"

    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = f"{EMOJI[sev]} palm-analytics {args.event} run: {sev}"
    if sev == "ERROR" and args.job_status == "failure":
        title += " (scheduled job failed)"
    elif sev == "WARN" and synth_count > 0:
        title += f" ({synth_count} synthetic fallback)"

    if fresh_rows:
        fresh_lines = []
        for n, s, d, _ in fresh_rows:
            if d is None:
                fresh_lines.append(f"`{n}`: {s}")
            elif d < 0:
                fresh_lines.append(f"`{n}`: {s} (max +{-d}d in future)")
            else:
                fresh_lines.append(f"`{n}`: {s} ({d}d stale)")
    elif fresh_status == "unknown":
        fresh_lines = ["freshness.json missing or unreadable"]
    else:
        fresh_lines = ["no sources reported"]

    synth_line = ", ".join(f"`{n}`" for n in synth_names) or "none"
    if synth_count > len(synth_names):
        synth_line += f" ({synth_count} total incl. sub-sources)"

    lake = (manifest or {}).get("lake", {}) if isinstance(manifest, dict) else {}
    fields = [
        {"name": "dbt", "value": (
            f"{counts['pass']}/{counts['total']} PASS "
            f"({counts['error']} error, {counts['warn']} warn)"
            if have_rr else "run_results.json missing"), "inline": True},
        {"name": "Freshness", "value": "\n".join(fresh_lines)[:1000], "inline": True},
        {"name": "Synthetic fallback",
         "value": f"{synth_count} source(s): {synth_line}"[:1000], "inline": False},
        {"name": "Lake snapshot",
         "value": str(lake.get("snapshot_id", "?")), "inline": True},
        {"name": "Run",
         "value": args.run_url or f"event={args.event} (no URL)", "inline": False},
    ]
    return {"content": title, "embeds": [{
        "title": title,
        "color": COLORS[sev],
        "fields": fields,
        "footer": {"text": f"palm-analytics-dbt • {now}"},
    }]}, sev


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", "manual"))
    ap.add_argument("--job-status", default="success",
                    help="'failure' signals a scheduled-job failure (ERROR)")
    ap.add_argument("--run-url", default=os.environ.get("GITHUB_RUN_URL", ""))
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--run-results", default=str(RUN_RESULTS))
    ap.add_argument("--freshness", default=str(FRESHNESS))
    ap.add_argument("--live", action="store_true",
                    help="actually POST to Discord; default is dry-run")
    ap.add_argument("--dry-run", action="store_true",
                    help="explicit dry-run (same as default without --live)")
    ap.add_argument("--always", action="store_true",
                    help="also post on OK (default: only WARN/ERROR)")
    ap.add_argument("--min-severity", default="WARN", choices=["WARN", "ERROR"],
                    help="minimum severity that triggers a post")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args()

    manifest = load_json(args.manifest)
    run_results = load_json(args.run_results)
    freshness = load_json(args.freshness)

    counts, have_rr = dbt_counts(run_results)
    fresh_status, fresh_rows = freshness_detail(freshness)
    synth_count, synth_names = synthetic_sources(manifest)

    payload, sev = build_payload(args, counts, have_rr, fresh_status,
                                 fresh_rows, synth_count, synth_names, manifest)

    order = {"OK": 0, "WARN": 1, "ERROR": 2}
    if order[sev] < order[args.min_severity] and not (sev == "OK" and args.always):
        print(f"[discord] severity={sev} below --min-severity={args.min_severity}: skip")
        return 0
    if sev == "OK" and not args.always:
        print("[discord] severity=OK: all green, nothing to post (use --always to force)")
        return 0

    live = args.live and not args.dry_run
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    print(f"[discord] severity={sev} dry_run={not live} "
          f"webhook_configured={'yes' if webhook else 'no'}")
    print(f"[discord] payload that {'was sent' if live else 'would be sent'}:")
    print(json.dumps(payload, indent=2)[:3000])

    if not live:
        return 0
    if not webhook:
        print("[discord] ::warning:: --live but DISCORD_WEBHOOK_URL is unset; skipping post",
              file=sys.stderr)
        return 0
    try:
        req = urllib.request.Request(
            webhook,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            print(f"[discord] posted (http {resp.status})")
    except Exception as e:
        # Alerting must never fail the build; surface as a warning.
        print(f"[discord] ::warning:: POST failed ({e.__class__.__name__}); payload logged above",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

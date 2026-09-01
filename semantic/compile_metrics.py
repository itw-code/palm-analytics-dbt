"""Compile the semantic-layer metric registry into a governed dbt model.

Reads target/manifest.json (dbt-core parses the MetricFlow-compatible spec in
models/marts/_marts__semantic.yml) and generates:

    models/semantic_layer/sl_metrics_daily.sql

Long-format output: (metric_name, metric_time, region_key, metric_value).

Compiler strategy: metrics resolve recursively down to base-measure column
fragments (derived exprs are inlined through their components, longest-name-
first word substitution), so every metric CTE reads directly from its model's
base aggregation CTE - no forward references, no ambiguous joins. Metrics that
cannot resolve to a single semantic model (e.g. true cross-model derived, or
types needing a full MetricFlow engine) are SKIPPED with a visible notice in
the generated file - never silently dropped.

Run order:  dbt deps -> ingestion -> dbt parse -> compile -> dbt build
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MANIFEST = Path("target/manifest.json")
OUTPUT = Path("models/semantic_layer/sl_metrics_daily.sql")

AGG_SQL = {
    "sum": "sum({expr})",
    "average": "avg({expr})",
    "min": "min({expr})",
    "max": "max({expr})",
    "count": "count({expr})",
    "count_distinct": "count(distinct {expr})",
}

HEADER = """-- !! GENERATED FILE - DO NOT EDIT !!
-- Produced by semantic/compile_metrics.py from the metric registry in
-- models/marts/_marts__semantic.yml. Edit the YAML and re-run the compiler:
--   dbt parse --profiles-dir . && python semantic/compile_metrics.py
-- Grain: (metric_name, metric_time, region_key). region_key is NULL for
-- semantic models without a categorical region dimension.
"""


def model_ref(semantic_model: dict) -> str:
    return "{{ ref('" + semantic_model["node_relation"]["alias"] + "') }}"


def base_grain(sm: dict) -> tuple[str, str | None]:
    """(time dimension column, categorical region dimension column or None)"""
    time_col, region_col = None, None
    for d in sm["dimensions"]:
        if d["type"] == "time":
            time_col = d.get("expr") or d["name"]
        if d["type"] == "categorical" and d["name"] == "region_key":
            region_col = d["name"]
    if time_col is None:
        raise SystemExit(f"[compile] semantic model {sm['name']} has no time dimension")
    return time_col, region_col


def main() -> int:
    if not MANIFEST.exists():
        print("[compile] target/manifest.json missing - run `dbt parse --profiles-dir .` first", file=sys.stderr)
        return 1

    man = json.load(open(MANIFEST, encoding="utf-8"))
    sem_models = {v["name"]: v for v in man.get("semantic_models", {}).values()}
    metrics = {v["name"]: v for v in man.get("metrics", {}).values()}
    if not sem_models or not metrics:
        print("[compile] no semantic_models/metrics in manifest - check _marts__semantic.yml", file=sys.stderr)
        return 1

    def measure_of(name: str) -> tuple[str, str] | None:
        """(semantic_model_name, measure_column) for a simple/cumulative metric"""
        tp = metrics[name]["type_params"]
        mref = tp.get("measure")
        if not mref:
            return None
        mname = mref["name"] if isinstance(mref, dict) else mref
        for sm in sem_models.values():
            if any(mm["name"] == mname for mm in sm["measures"]):
                return (sm["name"], mname)
        return None

    resolved: dict[str, tuple[str | None, str | None]] = {}

    def resolve(name: str, depth: int = 0) -> tuple[str | None, str | None]:
        """metric -> (semantic_model_name, sql fragment over base CTE columns)"""
        if name in resolved:
            return resolved[name]
        if depth > 10 or name not in metrics:
            resolved[name] = (None, None)
            return resolved[name]
        t, tp = metrics[name]["type"], metrics[name]["type_params"]
        if t in ("simple", "cumulative"):
            out = measure_of(name)
        elif t in ("derived", "ratio"):
            expr = tp.get("expr") or ""
            comps = [mm["name"] for mm in tp.get("metrics", [])]
            sub, sms, ok = {}, set(), bool(comps)
            for c in comps:
                cs, cf = resolve(c, depth + 1)
                if cs is None:
                    ok = False
                    break
                sub[c] = cf
                sms.add(cs)
            if not ok or len(sms) != 1:
                out = (None, None)  # cross-model or unresolvable components
            else:
                frag = expr
                for c in sorted(sub, key=len, reverse=True):  # longest-first, no prefix clobbering
                    frag = re.sub(r"\b" + re.escape(c) + r"\b", sub[c], frag)
                out = (next(iter(sms)), frag)
        else:
            out = (None, None)
        resolved[name] = out
        return out

    ctes: list[str] = []
    base_cte = {}

    # 1) base aggregation CTE per semantic model
    for sm_name, sm in sorted(sem_models.items()):
        time_col, region_col = base_grain(sm)
        base_cte[sm_name] = f"base__{sm_name}"
        parts = [f"        {time_col} as metric_time",
                 f"        {region_col}" if region_col else "        cast(null as varchar) as region_key"]
        for m in sm["measures"]:
            agg = AGG_SQL.get(m["agg"])
            if agg is None:
                raise SystemExit(f"[compile] unsupported agg '{m['agg']}' on measure {m['name']}")
            parts.append(f"        {agg.format(expr=m.get('expr') or m['name'])} as {m['name']}")
        group = "metric_time" + (", " + region_col if region_col else "")
        ctes.append("base__{n} as (\n    select\n{cols}\n    from {ref}\n    group by {grp}\n)".format(
            n=sm_name, cols=",\n".join(parts), ref=model_ref(sm), grp=group))

    # 2) one CTE per resolvable metric; simple/cumulative first, derived last
    skipped: list[str] = []
    unions: list[str] = []
    order = ([n for n in sorted(metrics) if metrics[n]["type"] in ("simple", "cumulative")]
             + [n for n in sorted(metrics) if metrics[n]["type"] not in ("simple", "cumulative")])
    for name in order:
        t = metrics[name]["type"]
        sm_name, frag = resolve(name)
        if sm_name is None:
            skipped.append(f"{name} (type '{t}' not resolvable by the OSS compiler)")
            continue
        if t == "cumulative":
            tp = metrics[name]["type_params"]
            ctp = tp.get("cumulative_type_params") or {}
            window = ctp.get("window") or tp.get("window") or "7 days"
            n_days = int("".join(ch for ch in str(window) if ch.isdigit()) or 7)
            ctes.append(
                f"m__{name} as (\n"
                f"    select metric_time, region_key,\n"
                f"           sum({frag}) over (partition by region_key order by metric_time\n"
                f"               range between interval '{n_days - 1}' day preceding and current row)::double as metric_value\n"
                f"    from {base_cte[sm_name]}\n)")
        else:
            ctes.append(f"m__{name} as (\n"
                        f"    select metric_time, region_key, ({frag})::double as metric_value\n"
                        f"    from {base_cte[sm_name]}\n)")
        unions.append(name)

    if not unions:
        print("[compile] no compilable metrics found", file=sys.stderr)
        return 1

    body = "with " + ",\n".join(ctes) + "\n\n"
    body += "\nunion all\n".join(
        f"select '{n}' as metric_name, metric_time, region_key, metric_value from m__{n}"
        for n in sorted(unions)
    )
    if skipped:
        body += "\n\n-- SKIPPED metrics (need full MetricFlow / dbt Cloud or cross-model support):\n"
        body += "".join(f"--   * {s}\n" for s in skipped)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(HEADER + "\n" + body + "\n", encoding="utf-8")
    print(f"[compile] wrote {OUTPUT} ({len(unions)} metrics, {len(skipped)} skipped)")
    for s in skipped:
        print(f"[compile]   skipped: {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

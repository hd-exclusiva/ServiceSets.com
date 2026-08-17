#!/usr/bin/env python3

"""
analyze_results.py
==================

Analyseert de resultaten van tester.py en maakt:

    test_results/
        analysis/
            dashboard.html
            all_results.csv
            product_summary.csv
            package_summary.csv
            failures.csv
            counterexamples.csv
            report.txt

Gebruik:

    python analyze_results.py

Of:

    python analyze_results.py --input test_results
    python analyze_results.py --open

De analyzer probeert automatisch te werken met:

    summary.json
    failures.json
    counterexamples.json
    warnings.json
    all_results.json

all_results.json is het meest waardevol omdat daarin iedere
product x verpakking-test staat.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import platform
import subprocess
import sys
import webbrowser
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================================
# CONFIG
# ============================================================================

DEFAULT_INPUT = Path("test_results")
DEFAULT_OUTPUT = Path("test_results") / "analysis"


# ============================================================================
# IO
# ============================================================================

def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"⚠ Kon {path} niet lezen: {exc}")
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def write_csv(
    path: Path,
    rows: List[Dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    # Verzamel alle keys.
    keys = []

    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=keys,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


# ============================================================================
# HELPERS
# ============================================================================

def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentage(part: int, total: int) -> float:
    if total == 0:
        return 0.0

    return round((part / total) * 100, 1)


def first_value(
    row: Dict[str, Any],
    keys: List[str],
    default: Any = None,
) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]

    return default


def escape(value: Any) -> str:
    return html.escape(str(value))


def fmt(value: Any, decimals: int = 1) -> str:
    number = safe_float(value)

    if number is None:
        return "-"

    return f"{number:.{decimals}f}"


# ============================================================================
# RESULT NORMALIZATION
# ============================================================================

def normalize_result(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Probeert verschillende mogelijke formaten van all_results.json
    te normaliseren naar één intern formaat.
    """

    product = first_value(
        row,
        [
            "product",
            "product_id",
            "artikelnummer",
            "product_num",
        ],
    )

    package = first_value(
        row,
        [
            "package",
            "verpakking",
            "package_name",
        ],
    )

    fits = first_value(
        row,
        [
            "fits",
            "passed",
            "pass",
        ],
    )

    result = first_value(
        row,
        [
            "result",
            "status",
        ],
    )

    reason = first_value(
        row,
        [
            "reason",
            "failure_reason",
            "reden",
            "message",
        ],
    )

    volume_pct = first_value(
        row,
        [
            "volume_pct",
            "used_volume_pct",
            "gebruikt_volume_pct",
            "utilization_pct",
        ],
    )

    if isinstance(fits, str):
        fits_lower = fits.lower()

        if fits_lower in (
            "true",
            "yes",
            "pass",
            "passed",
            "1",
        ):
            fits = True

        elif fits_lower in (
            "false",
            "no",
            "fail",
            "failed",
            "0",
        ):
            fits = False

    if fits is True:
        status = "PASS"

    elif fits is False:
        status = "FAIL"

    elif result:
        status = str(result).upper()

    else:
        status = "UNKNOWN"

    return {
        "product": str(product) if product is not None else "",
        "package": str(package) if package is not None else "",
        "status": status,
        "fits": fits,
        "reason": str(reason) if reason is not None else "",
        "volume_pct": safe_float(volume_pct),
        "raw": row,
    }


# ============================================================================
# LOAD DATA
# ============================================================================

def load_data(input_dir: Path) -> Dict[str, Any]:

    summary = load_json(
        input_dir / "summary.json",
        {},
    )

    failures = load_json(
        input_dir / "failures.json",
        [],
    )

    counterexamples = load_json(
        input_dir / "counterexamples.json",
        [],
    )

    warnings = load_json(
        input_dir / "warnings.json",
        [],
    )

    all_results = load_json(
        input_dir / "all_results.json",
        [],
    )

    return {
        "summary": summary,
        "failures": failures,
        "counterexamples": counterexamples,
        "warnings": warnings,
        "all_results": all_results,
    }


# ============================================================================
# BUILD FULL RESULTS
# ============================================================================

def build_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:

    all_results = data["all_results"]

    if isinstance(all_results, list) and all_results:
        print(
            f"✓ all_results.json gevonden: "
            f"{len(all_results)} resultaten"
        )

        return [
            normalize_result(row)
            for row in all_results
            if isinstance(row, dict)
        ]

    print(
        "⚠ all_results.json niet gevonden of leeg."
    )

    print(
        "  De analyse wordt uitgevoerd op de beschikbare "
        "failures/counterexamples."
    )

    results = []

    # Failures.
    for row in data["failures"]:
        if not isinstance(row, dict):
            continue

        products = row.get("product_ids", [])
        package = row.get("package", "")

        for product in products:
            results.append(
                {
                    "product": str(product),
                    "package": str(package),
                    "status": "FAIL",
                    "fits": False,
                    "reason": row.get(
                        "category",
                        row.get("message", ""),
                    ),
                    "volume_pct": None,
                    "raw": row,
                }
            )

    # Counterexamples.
    for row in data["counterexamples"]:
        if not isinstance(row, dict):
            continue

        products = row.get("product_ids", [])
        package = row.get("package", "")

        for product in products:
            results.append(
                {
                    "product": str(product),
                    "package": str(package),
                    "status": "COUNTEREXAMPLE",
                    "fits": False,
                    "reason": row.get(
                        "category",
                        row.get("message", ""),
                    ),
                    "volume_pct": None,
                    "raw": row,
                }
            )

    return results


# ============================================================================
# PRODUCT ANALYSIS
# ============================================================================

def analyze_products(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for result in results:
        product = result["product"]

        if product:
            grouped[product].append(result)

    output = []

    for product, rows in sorted(grouped.items()):

        total = len(rows)

        passes = sum(
            1
            for row in rows
            if row["status"] == "PASS"
        )

        fails = sum(
            1
            for row in rows
            if row["status"] == "FAIL"
        )

        counterexamples = sum(
            1
            for row in rows
            if row["status"] == "COUNTEREXAMPLE"
        )

        packages_that_fit = sorted(
            {
                row["package"]
                for row in rows
                if row["status"] == "PASS"
            }
        )

        packages_that_fail = sorted(
            {
                row["package"]
                for row in rows
                if row["status"] != "PASS"
            }
        )

        output.append(
            {
                "product": product,
                "tests": total,
                "pass": passes,
                "fail": fails,
                "counterexamples": counterexamples,
                "pass_pct": percentage(
                    passes,
                    total,
                ),
                "packages_that_fit": ", ".join(
                    packages_that_fit
                ),
                "packages_that_fail": ", ".join(
                    packages_that_fail
                ),
                "number_of_passing_packages": len(
                    packages_that_fit
                ),
                "number_of_failing_packages": len(
                    packages_that_fail
                ),
            }
        )

    return output


# ============================================================================
# PACKAGE ANALYSIS
# ============================================================================

def analyze_packages(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for result in results:
        package = result["package"]

        if package:
            grouped[package].append(result)

    output = []

    for package, rows in sorted(grouped.items()):

        total = len(rows)

        passes = sum(
            1
            for row in rows
            if row["status"] == "PASS"
        )

        fails = sum(
            1
            for row in rows
            if row["status"] != "PASS"
        )

        utilization_values = [
            row["volume_pct"]
            for row in rows
            if row["volume_pct"] is not None
        ]

        average_utilization = (
            sum(utilization_values)
            / len(utilization_values)
            if utilization_values
            else None
        )

        output.append(
            {
                "package": package,
                "tests": total,
                "pass": passes,
                "fail": fails,
                "pass_pct": percentage(
                    passes,
                    total,
                ),
                "average_volume_pct": (
                    round(average_utilization, 1)
                    if average_utilization is not None
                    else None
                ),
            }
        )

    return output


# ============================================================================
# PASS / FAIL LISTS
# ============================================================================

def build_pass_list(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    return [
        {
            "product": row["product"],
            "package": row["package"],
            "status": row["status"],
            "volume_pct": row["volume_pct"],
        }
        for row in results
        if row["status"] == "PASS"
    ]


def build_fail_list(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    return [
        {
            "product": row["product"],
            "package": row["package"],
            "reason": row["reason"],
            "status": row["status"],
        }
        for row in results
        if row["status"] != "PASS"
    ]


# ============================================================================
# REASON ANALYSIS
# ============================================================================

def analyze_failure_reasons(
    results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    counter = Counter()

    for row in results:
        if row["status"] == "PASS":
            continue

        reason = row["reason"] or "UNKNOWN"

        counter[reason] += 1

    return [
        {
            "reason": reason,
            "count": count,
        }
        for reason, count in counter.most_common()
    ]


# ============================================================================
# HTML HELPERS
# ============================================================================

def html_table(
    headers: List[str],
    rows: List[List[Any]],
    max_rows: Optional[int] = None,
) -> str:

    if max_rows is not None:
        rows = rows[:max_rows]

    output = [
        "<table>",
        "<thead>",
        "<tr>",
    ]

    for header in headers:
        output.append(
            f"<th>{escape(header)}</th>"
        )

    output.extend(
        [
            "</tr>",
            "</thead>",
            "<tbody>",
        ]
    )

    for row in rows:
        output.append("<tr>")

        for value in row:
            output.append(
                f"<td>{escape(value)}</td>"
            )

        output.append("</tr>")

    output.extend(
        [
            "</tbody>",
            "</table>",
        ]
    )

    return "\n".join(output)


# ============================================================================
# HTML DASHBOARD
# ============================================================================

def build_dashboard(
    output_dir: Path,
    data: Dict[str, Any],
    results: List[Dict[str, Any]],
    product_summary: List[Dict[str, Any]],
    package_summary: List[Dict[str, Any]],
    pass_list: List[Dict[str, Any]],
    fail_list: List[Dict[str, Any]],
    reason_summary: List[Dict[str, Any]],
) -> None:

    total = len(results)

    passes = sum(
        1
        for row in results
        if row["status"] == "PASS"
    )

    failures = total - passes

    pass_pct = percentage(
        passes,
        total,
    )

    fail_pct = percentage(
        failures,
        total,
    )

    counterexamples = len(
        data["counterexamples"]
    )

    data_problems = len(
        load_json(
            DEFAULT_INPUT / "data_problems.json",
            [],
        )
    )

    # ------------------------------------------------------------------
    # JS data
    # ------------------------------------------------------------------

    package_chart = [
        {
            "name": row["package"],
            "pass": row["pass"],
            "fail": row["fail"],
        }
        for row in package_summary
    ]

    reason_chart = [
        {
            "name": row["reason"],
            "count": row["count"],
        }
        for row in reason_summary[:15]
    ]

    product_chart = sorted(
        [
            {
                "name": row["product"],
                "pass_pct": row["pass_pct"],
            }
            for row in product_summary
        ],
        key=lambda x: x["pass_pct"],
    )

    package_chart_json = json.dumps(
        package_chart,
        ensure_ascii=False,
    )

    reason_chart_json = json.dumps(
        reason_chart,
        ensure_ascii=False,
    )

    product_chart_json = json.dumps(
        product_chart,
        ensure_ascii=False,
    )

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------

    package_rows = [
        [
            row["package"],
            row["tests"],
            row["pass"],
            row["fail"],
            f'{row["pass_pct"]}%',
            fmt(row["average_volume_pct"]),
        ]
        for row in package_summary
    ]

    product_rows = [
        [
            row["product"],
            row["tests"],
            row["pass"],
            row["fail"],
            f'{row["pass_pct"]}%',
            row["number_of_passing_packages"],
        ]
        for row in product_summary
    ]

    fail_rows = [
        [
            row["product"],
            row["package"],
            row["status"],
            row["reason"],
        ]
        for row in fail_list
    ]

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------

    page = f"""
<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>ServiceSets Packing Analysis</title>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 30px;
    font-family:
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    background: #f5f6f8;
    color: #222;
}}

h1 {{
    margin-bottom: 5px;
}}

h2 {{
    margin-top: 40px;
}}

.subtitle {{
    color: #666;
    margin-bottom: 30px;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(220px, 1fr));
    gap: 20px;
}}

.card {{
    background: white;
    border-radius: 12px;
    padding: 22px;
    box-shadow:
        0 2px 8px rgba(0,0,0,.06);
}}

.metric {{
    font-size: 32px;
    font-weight: 700;
}}

.label {{
    color: #666;
    margin-top: 5px;
}}

.chart {{
    background: white;
    padding: 20px;
    border-radius: 12px;
    margin-top: 20px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 10px;
    overflow: hidden;
}}

th {{
    background: #eee;
    text-align: left;
}}

th, td {{
    padding: 10px;
    border-bottom: 1px solid #ddd;
}}

tr:hover {{
    background: #f8f8f8;
}}

.pass {{
    color: #16803c;
    font-weight: 600;
}}

.fail {{
    color: #b42318;
    font-weight: 600;
}}

.small {{
    color: #777;
    font-size: 13px;
}}

.section {{
    margin-top: 40px;
}}

.scroll {{
    overflow-x: auto;
}}

</style>
</head>

<body>

<h1>ServiceSets Packing Analysis</h1>

<div class="subtitle">
Automatische analyse van de resultaten van tester.py
</div>

<div class="grid">

<div class="card">
    <div class="metric">{total:,}</div>
    <div class="label">Tests</div>
</div>

<div class="card">
    <div class="metric">{passes:,}</div>
    <div class="label">PASS</div>
</div>

<div class="card">
    <div class="metric">{failures:,}</div>
    <div class="label">FAIL</div>
</div>

<div class="card">
    <div class="metric">{pass_pct}%</div>
    <div class="label">Pass percentage</div>
</div>

<div class="card">
    <div class="metric">{counterexamples:,}</div>
    <div class="label">Counterexamples</div>
</div>

<div class="card">
    <div class="metric">{data_problems:,}</div>
    <div class="label">Data problems</div>
</div>

</div>


<div class="section">

<h2>PASS versus FAIL</h2>

<div class="chart">
<canvas id="passFailChart"></canvas>
</div>

</div>


<div class="section">

<h2>Resultaten per verpakking</h2>

<div class="chart">
<canvas id="packageChart"></canvas>
</div>

</div>


<div class="section">

<h2>Pass percentage per product</h2>

<div class="chart">
<canvas id="productChart"></canvas>
</div>

</div>


<div class="section">

<h2>Meest voorkomende failure redenen</h2>

<div class="chart">
<canvas id="reasonChart"></canvas>
</div>

</div>


<div class="section">

<h2>Verpakkingen</h2>

<div class="scroll">

{html_table(
    [
        "Verpakking",
        "Tests",
        "PASS",
        "FAIL",
        "PASS %",
        "Gem. volume %",
    ],
    package_rows,
)}

</div>

</div>


<div class="section">

<h2>Producten</h2>

<div class="scroll">

{html_table(
    [
        "Product",
        "Tests",
        "PASS",
        "FAIL",
        "PASS %",
        "# passende verpakkingen",
    ],
    product_rows,
)}

</div>

</div>


<div class="section">

<h2>Wat past niet?</h2>

<div class="scroll">

{html_table(
    [
        "Product",
        "Verpakking",
        "Status",
        "Reden",
    ],
    fail_rows,
)}

</div>

</div>


<script>

const packageData =
    {package_chart_json};

const reasonData =
    {reason_chart_json};

const productData =
    {product_chart_json};


new Chart(
    document.getElementById("passFailChart"),
    {{
        type: "doughnut",

        data: {{
            labels: [
                "PASS",
                "FAIL"
            ],

            datasets: [{{
                data: [
                    {passes},
                    {failures}
                ]
            }}]
        }},

        options: {{
            responsive: true
        }}
    }}
);


new Chart(
    document.getElementById("packageChart"),
    {{
        type: "bar",

        data: {{
            labels:
                packageData.map(x => x.name),

            datasets: [
                {{
                    label: "PASS",
                    data:
                        packageData.map(x => x.pass)
                }},
                {{
                    label: "FAIL",
                    data:
                        packageData.map(x => x.fail)
                }}
            ]
        }},

        options: {{
            responsive: true,

            scales: {{
                y: {{
                    beginAtZero: true
                }}
            }}
        }}
    }}
);


new Chart(
    document.getElementById("productChart"),
    {{
        type: "bar",

        data: {{
            labels:
                productData.map(x => x.name),

            datasets: [{{
                label: "Pass percentage",

                data:
                    productData.map(
                        x => x.pass_pct
                    )
            }}]
        }},

        options: {{
            indexAxis: "y",

            responsive: true,

            scales: {{
                x: {{
                    beginAtZero: true,
                    max: 100
                }}
            }}
        }}
    }}
);


new Chart(
    document.getElementById("reasonChart"),
    {{
        type: "bar",

        data: {{
            labels:
                reasonData.map(x => x.name),

            datasets: [{{
                label: "Aantal",

                data:
                    reasonData.map(
                        x => x.count
                    )
            }}]
        }},

        options: {{
            indexAxis: "y",

            responsive: true,

            scales: {{
                x: {{
                    beginAtZero: true
                }}
            }}
        }}
    }}
);

</script>

</body>
</html>
"""

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    dashboard = output_dir / "dashboard.html"

    dashboard.write_text(
        page,
        encoding="utf-8",
    )

    print(
        f"✓ Dashboard: {dashboard}"
    )


# ============================================================================
# TEXT REPORT
# ============================================================================

def write_text_report(
    path: Path,
    data: Dict[str, Any],
    results: List[Dict[str, Any]],
    product_summary: List[Dict[str, Any]],
    package_summary: List[Dict[str, Any]],
    fail_list: List[Dict[str, Any]],
) -> None:

    total = len(results)

    passes = sum(
        1
        for row in results
        if row["status"] == "PASS"
    )

    fails = total - passes

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "SERVICESETS PACKING ANALYSIS\n"
        )

        f.write(
            "============================\n\n"
        )

        f.write(
            f"Tests: {total}\n"
        )

        f.write(
            f"PASS: {passes}\n"
        )

        f.write(
            f"FAIL: {fails}\n"
        )

        f.write(
            f"PASS percentage: "
            f"{percentage(passes, total)}%\n\n"
        )

        f.write(
            "VERPAKKINGEN\n"
            "------------\n"
        )

        for row in package_summary:
            f.write(
                f"{row['package']}: "
                f"{row['pass']} PASS / "
                f"{row['fail']} FAIL "
                f"({row['pass_pct']}%)\n"
            )

        f.write(
            "\nPRODUCTEN\n"
            "---------\n"
        )

        for row in product_summary:
            f.write(
                f"{row['product']}: "
                f"{row['pass']} PASS / "
                f"{row['fail']} FAIL "
                f"({row['pass_pct']}%)\n"
            )

            f.write(
                f"  Past in: "
                f"{row['packages_that_fit'] or '-'}\n"
            )

            f.write(
                f"  Past niet in: "
                f"{row['packages_that_fail'] or '-'}\n"
            )

        f.write(
            "\nNIET PASSENDE COMBINATIES\n"
            "-------------------------\n"
        )

        for row in fail_list:
            f.write(
                f"- Product: {row['product']}\n"
                f"  Verpakking: {row['package']}\n"
                f"  Status: {row['status']}\n"
                f"  Reden: {row['reason']}\n\n"
            )


# ============================================================================
# OPEN BROWSER
# ============================================================================

def open_dashboard(path: Path) -> None:

    url = path.resolve().as_uri()

    try:
        webbrowser.open(url)
        return
    except Exception:
        pass

    # Linux fallback.
    if platform.system() == "Linux":
        try:
            subprocess.Popen(
                ["xdg-open", str(path.resolve())]
            )
        except Exception:
            pass


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Analyseer de resultaten van "
            "ServiceSets tester.py."
        )
    )

    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help=(
            "Map met resultaten van tester.py "
            "(standaard: test_results)"
        ),
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=(
            "Map voor analyse-output "
            "(standaard: test_results/analysis)"
        ),
    )

    parser.add_argument(
        "--open",
        action="store_true",
        help="Open dashboard.html automatisch.",
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        sys.exit(
            f"Inputmap bestaat niet: {input_dir}"
        )

    print("=" * 70)
    print(" ServiceSets Packing Results Analyzer")
    print("=" * 70)

    print(
        f"\nResultaten lezen uit:\n"
        f"  {input_dir.resolve()}"
    )

    data = load_data(input_dir)

    results = build_results(data)

    if not results:
        print(
            "\n⚠ Geen testresultaten gevonden."
        )

        print(
            "\nJe tester.py moet minimaal "
            "all_results.json maken."
        )

        print(
            "\nVerwacht formaat:"
        )

        print(
            """
[
  {
    "product": "3560000",
    "package": "LW",
    "fits": true,
    "volume_pct": 63.2
  }
]
"""
        )

        sys.exit(1)

    print(
        f"\n{len(results):,} resultaten analyseren..."
    )

    product_summary = analyze_products(
        results
    )

    package_summary = analyze_packages(
        results
    )

    pass_list = build_pass_list(
        results
    )

    fail_list = build_fail_list(
        results
    )

    reason_summary = analyze_failure_reasons(
        results
    )

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    write_csv(
        output_dir / "all_results.csv",
        [
            {
                "product": row["product"],
                "package": row["package"],
                "status": row["status"],
                "fits": row["fits"],
                "reason": row["reason"],
                "volume_pct": row["volume_pct"],
            }
            for row in results
        ],
    )

    write_csv(
        output_dir / "product_summary.csv",
        product_summary,
    )

    write_csv(
        output_dir / "package_summary.csv",
        package_summary,
    )

    write_csv(
        output_dir / "passes.csv",
        pass_list,
    )

    write_csv(
        output_dir / "failures.csv",
        fail_list,
    )

    write_csv(
        output_dir / "failure_reasons.csv",
        reason_summary,
    )

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    save_json(
        output_dir / "product_summary.json",
        product_summary,
    )

    save_json(
        output_dir / "package_summary.json",
        package_summary,
    )

    save_json(
        output_dir / "failure_reasons.json",
        reason_summary,
    )

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    write_text_report(
        output_dir / "report.txt",
        data,
        results,
        product_summary,
        package_summary,
        fail_list,
    )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    build_dashboard(
        output_dir,
        data,
        results,
        product_summary,
        package_summary,
        pass_list,
        fail_list,
        reason_summary,
    )

    # ------------------------------------------------------------------
    # Console
    # ------------------------------------------------------------------

    total = len(results)

    passes = sum(
        1
        for row in results
        if row["status"] == "PASS"
    )

    fails = total - passes

    print("\n" + "=" * 70)
    print(" RESULTAAT")
    print("=" * 70)

    print(
        f"\nTests:       {total:,}"
    )

    print(
        f"PASS:        {passes:,}"
    )

    print(
        f"FAIL:        {fails:,}"
    )

    print(
        f"PASS ratio:  {percentage(passes, total)}%"
    )

    print(
        "\nBestanden:"
    )

    print(
        f"  {output_dir / 'dashboard.html'}"
    )

    print(
        f"  {output_dir / 'product_summary.csv'}"
    )

    print(
        f"  {output_dir / 'package_summary.csv'}"
    )

    print(
        f"  {output_dir / 'passes.csv'}"
    )

    print(
        f"  {output_dir / 'failures.csv'}"
    )

    print(
        f"  {output_dir / 'report.txt'}"
    )

    print("\n" + "=" * 70)

    if args.open:
        open_dashboard(
            output_dir / "dashboard.html"
        )


if __name__ == "__main__":
    main()
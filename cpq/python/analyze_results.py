#!/usr/bin/env python3
"""
ServiceSets.com - Packing Analysis Dashboard

Gebruik:
    streamlit run analyze_results.py

Verwachte bestanden:
    test_results/all_results.json

Optioneel:
    test_results/summary.json
    test_results/recommendations.json
    test_results/failures.json
    test_results/passes.json

Het dashboard toont:
- Productnummer + productnaam
- Productafmetingen L x B x H
- Productvolume en gewicht
- Verpakking + verpakkingsafmetingen
- PASS / FAIL
- Concrete foutreden
- Rotatie waarin een product past
- Volume-benutting
- Kleinste passende verpakking
- Filters en zoekfunctie
- Grafieken
- Detailtabel
- Servicesets.com-achtige huisstijl
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# CONFIG / HUISSTIJL
# ============================================================

APP_TITLE = "Servicesets Packing Analysis"
RESULTS_DIR = Path("test_results")

# De website gebruikt een frisse, eigentijdse uitstraling.
# Deze kleuren zijn bewust als dashboard-thema gekozen:
# donkergroen voor merk/headers, warm accent voor highlights.
BRAND_GREEN = "#173F35"
BRAND_GREEN_2 = "#245C4D"
BRAND_LIGHT = "#EAF3EF"
BRAND_ACCENT = "#D6A85F"
BRAND_DARK = "#14201D"
WHITE = "#FFFFFF"
GREY = "#66736F"
LIGHT_GREY = "#F5F7F6"
RED = "#B94A48"
GREEN = "#287A57"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    f"""
<style>
    .stApp {{
        background: #F7F8F7;
    }}

    [data-testid="stSidebar"] {{
        background: {BRAND_GREEN};
    }}

    [data-testid="stSidebar"] * {{
        color: white !important;
    }}

    .brand-header {{
        background: linear-gradient(
            135deg,
            {BRAND_GREEN} 0%,
            {BRAND_GREEN_2} 100%
        );
        padding: 28px 34px;
        border-radius: 18px;
        margin-bottom: 22px;
        color: white;
        box-shadow: 0 8px 25px rgba(23,63,53,.14);
    }}

    .brand-header h1 {{
        margin: 0;
        font-size: 2.25rem;
        font-weight: 750;
        letter-spacing: -0.03em;
    }}

    .brand-header p {{
        margin: 7px 0 0;
        opacity: .86;
        font-size: 1rem;
    }}

    .metric-card {{
        background: white;
        border: 1px solid #E4EAE7;
        border-radius: 16px;
        padding: 18px 20px;
        min-height: 115px;
        box-shadow: 0 4px 15px rgba(20,32,29,.05);
    }}

    .metric-label {{
        color: {GREY};
        font-size: .83rem;
        text-transform: uppercase;
        letter-spacing: .06em;
        font-weight: 700;
    }}

    .metric-value {{
        color: {BRAND_GREEN};
        font-size: 2rem;
        font-weight: 800;
        margin-top: 5px;
    }}

    .section-title {{
        color: {BRAND_GREEN};
        font-weight: 800;
        font-size: 1.35rem;
        margin: 28px 0 10px;
    }}

    .pass-badge {{
        display: inline-block;
        background: #E3F2EA;
        color: {GREEN};
        border-radius: 999px;
        padding: 4px 10px;
        font-weight: 750;
    }}

    .fail-badge {{
        display: inline-block;
        background: #F9E7E6;
        color: {RED};
        border-radius: 999px;
        padding: 4px 10px;
        font-weight: 750;
    }}

    .info-box {{
        background: {BRAND_LIGHT};
        border-left: 5px solid {BRAND_ACCENT};
        padding: 14px 18px;
        border-radius: 8px;
        color: {BRAND_DARK};
        margin: 10px 0 18px;
    }}

    div[data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
    }}

    .small-note {{
        color: {GREY};
        font-size: .82rem;
    }}

    button[kind="primary"] {{
        background: {BRAND_GREEN};
    }}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def fmt_num(value: Any, decimals: int = 1) -> str:
    if value is None or value == "":
        return "—"

    try:
        value = float(value)
        if decimals == 0:
            return f"{value:,.0f}".replace(",", ".")
        return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)


def dimensions_text(value: Any) -> str:
    if isinstance(value, dict):
        l = value.get("lengte", value.get("l"))
        w = value.get("breedte", value.get("w"))
        h = value.get("hoogte", value.get("h"))

        if l is not None and w is not None and h is not None:
            return (
                f"{fmt_num(l)} × "
                f"{fmt_num(w)} × "
                f"{fmt_num(h)} cm"
            )

    if isinstance(value, (list, tuple)) and len(value) == 3:
        return " × ".join(fmt_num(x) for x in value) + " cm"

    return "—"


def reason_text(row: pd.Series) -> str:
    reason = row.get("reason")

    mapping = {
        "PRODUCT_TOO_LARGE": "Product is te groot voor deze verpakking",
        "WEIGHT_LIMIT": "Gewichtslimiet van verpakking",
        "PACKING_ENGINE_REJECTED": "3D packing engine kon het product niet plaatsen",
        "ITEMS_DID_NOT_ALL_FIT": "Niet alle items passen",
        "PACKING_ENGINE_ERROR": "Fout in packing engine",
        "UNKNOWN_PACKING_FAILURE": "Onbekende packing failure",
    }

    if pd.isna(reason) or reason in ("", None):
        return ""

    return mapping.get(str(reason), str(reason))


def normalize_results(raw: Any) -> pd.DataFrame:
    if isinstance(raw, dict):
        for key in ("all_results", "results", "data"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break

    if not isinstance(raw, list):
        return pd.DataFrame()

    rows = []

    for r in raw:
        if not isinstance(r, dict):
            continue

        product_dims = r.get("product_dimensions_cm", {})
        package_dims = r.get("package_dimensions_cm", {})

        row = {
            "product": r.get("product", ""),
            "product_name": r.get("product_name", ""),
            "product_dimensions": dimensions_text(product_dims),
            "product_volume_cm3": r.get("product_volume_cm3"),
            "product_weight_g": r.get("product_weight_g"),
            "package": r.get("package", ""),
            "package_dimensions": dimensions_text(package_dims),
            "package_volume_cm3": r.get("package_volume_cm3"),
            "package_max_weight_g": r.get("package_max_weight_g"),
            "status": str(r.get("status", "")).upper(),
            "fits": r.get("fits"),
            "reason": r.get("reason"),
            "reason_text": "",
            "volume_pct": r.get("volume_pct"),
            "rotation": dimensions_text(r.get("rotation")),
            "quantity_instance": r.get("quantity_instance"),
            "requested_quantity": r.get("requested_quantity"),
        }

        rows.append(row)

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # Fallbacks voor oudere result-formaten.
    if "status" not in df:
        df["status"] = df["fits"].apply(
            lambda x: "PASS" if x is True else "FAIL"
        )

    df["status"] = df["status"].fillna("").astype(str).str.upper()

    df["reason_text"] = df.apply(
        reason_text,
        axis=1,
    )

    for col in [
        "product_volume_cm3",
        "product_weight_g",
        "package_volume_cm3",
        "package_max_weight_g",
        "volume_pct",
    ]:
        if col in df:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    df["product_label"] = (
        df["product"].fillna("").astype(str)
        + " — "
        + df["product_name"].fillna("").astype(str)
    )

    return df


def normalize_combinations(
    raw: Any,
) -> tuple[pd.DataFrame, pd.DataFrame]:

    """
    Zet combination_results.json (lijst van scenario's,
    elk met resultaten per verpakking) om naar twee
    platte DataFrames:

    - scenario_df: één rij per scenario (samenvatting)
    - detail_df:   één rij per scenario × verpakking
    """

    if not isinstance(raw, list):
        return pd.DataFrame(), pd.DataFrame()

    scenario_rows = []
    detail_rows = []

    for scenario in raw:
        if not isinstance(scenario, dict):
            continue

        items = scenario.get("items", []) or []

        items_text = ", ".join(
            f"{it.get('product_name', it.get('product_id', '?'))} "
            f"×{it.get('quantity', 1)}"
            for it in items
        )

        per_package = scenario.get(
            "results_per_package", []
        ) or []

        packages_total = len(per_package)

        packages_fit = sum(
            1
            for r in per_package
            if r.get("status") == "PASS"
        )

        pass_rate = (
            packages_fit / packages_total * 100
            if packages_total
            else 0.0
        )

        scenario_rows.append(
            {
                "scenario_id": scenario.get("scenario_id", ""),
                "scenario_name": scenario.get("scenario_name", ""),
                "category": scenario.get("category", "") or "—",
                "description": scenario.get("description", ""),
                "distinct_articles": scenario.get("distinct_articles", len(items)),
                "total_quantity": scenario.get(
                    "total_quantity",
                    sum(it.get("quantity", 1) for it in items),
                ),
                "items_text": items_text,
                "fits_any_package": scenario.get("fits_any_package", packages_fit > 0),
                "smallest_fitting_package": scenario.get(
                    "smallest_fitting_package"
                ) or "—",
                "packages_fit": packages_fit,
                "packages_total": packages_total,
                "pass_rate": round(pass_rate, 1),
            }
        )

        for r in per_package:
            detail_rows.append(
                {
                    "scenario_id": scenario.get("scenario_id", ""),
                    "scenario_name": scenario.get("scenario_name", ""),
                    "category": scenario.get("category", "") or "—",
                    "items_text": items_text,
                    "distinct_articles": scenario.get("distinct_articles", len(items)),
                    "total_quantity": scenario.get("total_quantity", ""),
                    "package": r.get("package", ""),
                    "package_dimensions": dimensions_text(
                        r.get("package_dimensions_cm", {})
                    ),
                    "status": str(r.get("status", "")).upper(),
                    "fits": r.get("fits"),
                    "volume_pct": r.get("volume_pct"),
                    "total_weight_g": r.get("total_weight_g"),
                    "package_max_weight_g": r.get("package_max_weight_g"),
                    "reason_text": reason_text(pd.Series(r)),
                    "fitted_count": r.get("fitted_count"),
                    "unfitted_count": r.get("unfitted_count"),
                    "number_of_products": r.get("number_of_products"),
                }
            )

    scenario_df = pd.DataFrame(scenario_rows)
    detail_df = pd.DataFrame(detail_rows)

    for col in ["volume_pct", "total_weight_g", "package_max_weight_g"]:
        if col in detail_df:
            detail_df[col] = pd.to_numeric(detail_df[col], errors="coerce")

    return scenario_df, detail_df


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="brand-header">
        <h1>Servicesets Packing Analysis</h1>
        <p>
            Analyse van productafmetingen, verpakkingen en 3D packing-resultaten
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATA
# ============================================================

all_results_path = RESULTS_DIR / "all_results.json"

raw_results = load_json(all_results_path)

if raw_results is None:
    st.error(
        f"Geen resultaten gevonden: `{all_results_path}`"
    )
    st.info(
        "Voer eerst `python tester.py --all` uit."
    )
    st.stop()

df = normalize_results(raw_results)

if df.empty:
    st.error("all_results.json bevat geen bruikbare resultaten.")
    st.stop()

combination_results_path = RESULTS_DIR / "combination_results.json"
raw_combinations = load_json(combination_results_path, default=[])
scenario_df, combo_detail_df = normalize_combinations(raw_combinations)


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.markdown("## Filters")

search = st.sidebar.text_input(
    "Zoek product",
    placeholder="Naam of artikelnummer...",
)

statuses = st.sidebar.multiselect(
    "Resultaat",
    options=["PASS", "FAIL", "ERROR"],
    default=["PASS", "FAIL"],
)

products = sorted(
    [
        x
        for x in df["product_name"].dropna().unique()
        if str(x).strip()
    ]
)

selected_products = st.sidebar.multiselect(
    "Producten",
    options=products,
)

packages = sorted(
    [
        x
        for x in df["package"].dropna().unique()
        if str(x).strip()
    ]
)

selected_packages = st.sidebar.multiselect(
    "Verpakkingen",
    options=packages,
)

min_volume, max_volume = st.sidebar.slider(
    "Volume-benutting (%)",
    min_value=0,
    max_value=100,
    value=(0, 100),
)

filtered = df.copy()

if search:
    needle = search.lower()
    filtered = filtered[
        filtered["product_name"].fillna("").str.lower().str.contains(
            needle,
            regex=False,
        )
        | filtered["product"].fillna("").astype(str).str.lower().str.contains(
            needle,
            regex=False,
        )
    ]

if statuses:
    filtered = filtered[
        filtered["status"].isin(statuses)
    ]

if selected_products:
    filtered = filtered[
        filtered["product_name"].isin(selected_products)
    ]

if selected_packages:
    filtered = filtered[
        filtered["package"].isin(selected_packages)
    ]

filtered = filtered[
    filtered["volume_pct"].fillna(0).between(
        min_volume,
        max_volume,
    )
]


# ============================================================
# KPI
# ============================================================

total = len(filtered)
passes = int((filtered["status"] == "PASS").sum())
fails = int((filtered["status"] == "FAIL").sum())
errors = int((filtered["status"] == "ERROR").sum())

pass_rate = (
    passes / total * 100
    if total
    else 0
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    metric_card("Tests", f"{total:,}".replace(",", "."))

with c2:
    metric_card("PASS", f"{passes:,}".replace(",", "."))

with c3:
    metric_card("FAIL", f"{fails:,}".replace(",", "."))

with c4:
    metric_card("Passpercentage", f"{pass_rate:.1f}%".replace(".", ","))


# ============================================================
# INFO
# ============================================================

st.markdown(
    f"""
    <div class="info-box">
        <strong>{len(filtered):,} tests geselecteerd.</strong>
        Gebruik links de filters om bijvoorbeeld één product,
        één verpakking of alleen failures te bekijken.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# TABBLADEN
# ============================================================

tab_overview, tab_products, tab_packages, tab_combinations, tab_failures, tab_details = st.tabs(
    [
        "Overzicht",
        "Per product",
        "Per verpakking",
        "Combinaties",
        "Failures",
        "Alle resultaten",
    ]
)


# ============================================================
# OVERVIEW
# ============================================================

with tab_overview:
    st.markdown(
        '<div class="section-title">Resultaat per verpakking</div>',
        unsafe_allow_html=True,
    )

    if not filtered.empty:
        package_stats = (
            filtered.groupby(["package", "status"])
            .size()
            .reset_index(name="tests")
        )

        fig = px.bar(
            package_stats,
            x="package",
            y="tests",
            color="status",
            barmode="group",
            text="tests",
            title="PASS / FAIL per verpakking",
            color_discrete_map={
                "PASS": GREEN,
                "FAIL": RED,
                "ERROR": BRAND_ACCENT,
            },
        )

        fig.update_layout(
            template="plotly_white",
            height=430,
            margin=dict(l=20, r=20, t=65, b=20),
            font=dict(color=BRAND_DARK),
            legend_title_text="Resultaat",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    st.markdown(
        '<div class="section-title">Verdeling van failure-redenen</div>',
        unsafe_allow_html=True,
    )

    failures = filtered[
        filtered["status"] != "PASS"
    ].copy()

    if failures.empty:
        st.success("Geen failures in de huidige selectie.")

    else:
        reason_counts = (
            failures["reason_text"]
            .replace("", "Onbekend")
            .value_counts()
            .reset_index()
        )

        reason_counts.columns = [
            "reden",
            "aantal",
        ]

        fig = px.bar(
            reason_counts,
            x="aantal",
            y="reden",
            orientation="h",
            text="aantal",
            title="Waarom producten niet passen",
        )

        fig.update_traces(
            marker_color=RED
        )

        fig.update_layout(
            template="plotly_white",
            height=max(
                320,
                55 * len(reason_counts),
            ),
            margin=dict(l=20, r=20, t=65, b=20),
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# PER PRODUCT
# ============================================================

with tab_products:
    st.markdown(
        '<div class="section-title">Productanalyse</div>',
        unsafe_allow_html=True,
    )

    product_stats = (
        filtered.groupby(
            [
                "product",
                "product_name",
                "product_dimensions",
            ],
            dropna=False,
        )
        .agg(
            tests=("status", "size"),
            passen=("status", lambda x: (x == "PASS").sum()),
            failures=("status", lambda x: (x != "PASS").sum()),
            beste_benutting=(
                "volume_pct",
                "min",
            ),
        )
        .reset_index()
    )

    product_stats["passpercentage"] = (
        product_stats["passen"]
        / product_stats["tests"]
        * 100
    )

    product_stats["product"] = product_stats[
        "product"
    ].astype(str)

    product_stats = product_stats.sort_values(
        [
            "passpercentage",
            "product_name",
        ]
    )

    display_products = product_stats.rename(
        columns={
            "product": "Artikelnummer",
            "product_name": "Productnaam",
            "product_dimensions": "Afmetingen L × B × H",
            "tests": "Tests",
            "passen": "Past",
            "failures": "Past niet",
            "passpercentage": "Pass %",
            "beste_benutting": "Beste volume %",
        }
    )

    display_products["Pass %"] = display_products[
        "Pass %"
    ].round(1)

    display_products["Beste volume %"] = display_products[
        "Beste volume %"
    ].round(1)

    st.dataframe(
        display_products[
            [
                "Artikelnummer",
                "Productnaam",
                "Afmetingen L × B × H",
                "Tests",
                "Past",
                "Past niet",
                "Pass %",
                "Beste volume %",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        '<div class="section-title">Passpercentage per product</div>',
        unsafe_allow_html=True,
    )

    chart_df = product_stats.head(50).copy()

    chart_df["label"] = (
        chart_df["product_name"]
        + " ("
        + chart_df["product"].astype(str)
        + ")"
    )

    fig = px.bar(
        chart_df.sort_values("passpercentage"),
        x="passpercentage",
        y="label",
        orientation="h",
        text="passpercentage",
        title="Producten met laagste passpercentage",
    )

    fig.update_traces(
        marker_color=BRAND_GREEN_2,
        texttemplate="%{text:.1f}%",
    )

    fig.update_layout(
        template="plotly_white",
        height=max(
            420,
            28 * len(chart_df),
        ),
        xaxis_title="Passpercentage",
        yaxis_title="",
        margin=dict(l=20, r=20, t=65, b=20),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# PER PACKAGE
# ============================================================

with tab_packages:
    st.markdown(
        '<div class="section-title">Verpakkingsanalyse</div>',
        unsafe_allow_html=True,
    )

    package_stats = (
        filtered.groupby(
            [
                "package",
                "package_dimensions",
            ],
            dropna=False,
        )
        .agg(
            tests=("status", "size"),
            passen=("status", lambda x: (x == "PASS").sum()),
            failures=("status", lambda x: (x != "PASS").sum()),
            gemiddelde_benutting=(
                "volume_pct",
                "mean",
            ),
        )
        .reset_index()
    )

    package_stats["passpercentage"] = (
        package_stats["passen"]
        / package_stats["tests"]
        * 100
    )

    package_display = package_stats.rename(
        columns={
            "package": "Verpakking",
            "package_dimensions": "Afmetingen L × B × H",
            "tests": "Tests",
            "passen": "Past",
            "failures": "Past niet",
            "passpercentage": "Pass %",
            "gemiddelde_benutting": "Gem. volume %",
        }
    )

    package_display["Pass %"] = package_display[
        "Pass %"
    ].round(1)

    package_display["Gem. volume %"] = package_display[
        "Gem. volume %"
    ].round(1)

    st.dataframe(
        package_display[
            [
                "Verpakking",
                "Afmetingen L × B × H",
                "Tests",
                "Past",
                "Past niet",
                "Pass %",
                "Gem. volume %",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        '<div class="section-title">Verpakkingen vergelijken</div>',
        unsafe_allow_html=True,
    )

    fig = px.bar(
        package_stats.sort_values("passpercentage"),
        x="package",
        y="passpercentage",
        text="passpercentage",
        title="Passpercentage per verpakking",
    )

    fig.update_traces(
        marker_color=BRAND_GREEN,
        texttemplate="%{text:.1f}%",
    )

    fig.update_layout(
        template="plotly_white",
        height=430,
        yaxis_title="Passpercentage",
        xaxis_title="",
        margin=dict(l=20, r=20, t=65, b=20),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# COMBINATIES (service-set scenario's met meerdere artikelen/aantallen)
# ============================================================

with tab_combinations:
    st.markdown(
        '<div class="section-title">Service-set combinaties &amp; aantallen</div>',
        unsafe_allow_html=True,
    )

    if scenario_df.empty:
        st.info(
            "Geen `combination_results.json` gevonden of leeg. "
            "Voer `python tester.py --all` uit (scenario's staan standaard aan) "
            "om benoemde service-set samenstellingen — met meerdere artikelen "
            "en aantallen (bv. 6× limonade) — samen te testen tegen alle "
            "verpakkingen."
        )

    else:
        st.markdown(
            f"""
            <div class="info-box">
                <strong>{len(scenario_df)} service-set scenario('s) getest.</strong>
                Elk scenario bevat meerdere artikelen — soms met meerdere
                stuks van hetzelfde artikel (bv. meerdere sticks limonade of
                koffiepads) — die <em>samen</em> in één verpakking moeten passen.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---- KPI's ----
        n_scenarios = len(scenario_df)
        n_fit_any = int(scenario_df["fits_any_package"].sum())
        n_no_fit = n_scenarios - n_fit_any
        avg_pass_rate = scenario_df["pass_rate"].mean()

        k1, k2, k3, k4 = st.columns(4)

        with k1:
            metric_card("Scenario's getest", f"{n_scenarios:,}".replace(",", "."))

        with k2:
            metric_card("Passen ergens", f"{n_fit_any:,}".replace(",", "."))

        with k3:
            metric_card("Passen nergens", f"{n_no_fit:,}".replace(",", "."))

        with k4:
            metric_card(
                "Gem. passpercentage",
                f"{avg_pass_rate:.1f}%".replace(".", ","),
            )

        # ---- Filter op categorie ----
        categories = sorted(scenario_df["category"].dropna().unique())

        selected_categories = st.multiselect(
            "Filter op categorie",
            options=categories,
            default=[],
            help="Bijv. koffie, bad_douche, schoonmaak, recreatie, gecombineerd",
        )

        scenario_view = scenario_df.copy()

        if selected_categories:
            scenario_view = scenario_view[
                scenario_view["category"].isin(selected_categories)
            ]

        # ---- Overzichtstabel per scenario ----
        st.markdown(
            '<div class="section-title">Welke combinaties, welke aantallen?</div>',
            unsafe_allow_html=True,
        )

        overview_display = scenario_view[
            [
                "scenario_name",
                "category",
                "items_text",
                "distinct_articles",
                "total_quantity",
                "smallest_fitting_package",
                "packages_fit",
                "packages_total",
                "pass_rate",
                "fits_any_package",
            ]
        ].rename(
            columns={
                "scenario_name": "Service-set",
                "category": "Categorie",
                "items_text": "Artikelen × aantallen",
                "distinct_articles": "# Verschillende artikelen",
                "total_quantity": "Totaal aantal stuks",
                "smallest_fitting_package": "Kleinste passende verpakking",
                "packages_fit": "Verpakkingen die passen",
                "packages_total": "Verpakkingen getest",
                "pass_rate": "Pass %",
                "fits_any_package": "Past ergens?",
            }
        )

        st.dataframe(
            overview_display,
            use_container_width=True,
            hide_index=True,
            height=min(70 + 45 * len(overview_display), 600),
        )

        st.download_button(
            "Download combinatie-overzicht als CSV",
            data=overview_display.to_csv(index=False).encode("utf-8"),
            file_name="servicesets_combinaties_overzicht.csv",
            mime="text/csv",
        )

        # ---- Passpercentage per scenario (chart) ----
        st.markdown(
            '<div class="section-title">Passpercentage per combinatie</div>',
            unsafe_allow_html=True,
        )

        chart_df = scenario_view.sort_values("pass_rate").copy()

        fig = px.bar(
            chart_df,
            x="pass_rate",
            y="scenario_name",
            orientation="h",
            text="pass_rate",
            color="category",
            title="Welk % van de verpakkingen is groot genoeg voor deze combinatie?",
        )

        fig.update_traces(
            texttemplate="%{text:.1f}%",
        )

        fig.update_layout(
            template="plotly_white",
            height=max(340, 55 * len(chart_df)),
            xaxis_title="Passpercentage over geteste verpakkingen",
            yaxis_title="",
            margin=dict(l=20, r=20, t=65, b=20),
            legend_title_text="Categorie",
        )

        st.plotly_chart(fig, use_container_width=True)

        # ---- Combinaties die nergens passen ----
        no_fit_df = scenario_view[
            ~scenario_view["fits_any_package"]
        ]

        if not no_fit_df.empty:
            st.markdown(
                '<div class="section-title">⚠ Combinaties die in géén enkele verpakking passen</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                """
                <div class="info-box">
                    Deze service-sets — met hun huidige artikelen en aantallen —
                    passen in geen van de geteste verpakkingen. Dit is direct
                    input voor de Maatwerk-behoefte 3D fit-check / gecombineerde
                    sets uit de Fit-Gap analyse: ofwel is een grotere/andere
                    verpakking nodig, ofwel moet de samenstelling (aantallen)
                    worden herzien.
                </div>
                """,
                unsafe_allow_html=True,
            )

            for _, row in no_fit_df.iterrows():
                st.markdown(
                    f"**{row['scenario_name']}** ({row['category']}) — "
                    f"{row['total_quantity']} stuks over "
                    f"{row['distinct_articles']} artikelen: "
                    f"<span class='small-note'>{row['items_text']}</span>",
                    unsafe_allow_html=True,
                )

        # ---- Detail per scenario x verpakking ----
        st.markdown(
            '<div class="section-title">Detail per combinatie × verpakking</div>',
            unsafe_allow_html=True,
        )

        scenario_pick = st.selectbox(
            "Kies een service-set voor het volledige verpakkingsoverzicht",
            options=scenario_view["scenario_name"].tolist(),
        )

        picked = combo_detail_df[
            combo_detail_df["scenario_name"] == scenario_pick
        ].copy()

        if not picked.empty:

            st.markdown(
                f"<span class='small-note'>{picked['items_text'].iloc[0]}</span>",
                unsafe_allow_html=True,
            )

            picked_display = picked[
                [
                    "package",
                    "package_dimensions",
                    "status",
                    "volume_pct",
                    "total_weight_g",
                    "reason_text",
                    "fitted_count",
                    "unfitted_count",
                ]
            ].rename(
                columns={
                    "package": "Verpakking",
                    "package_dimensions": "Afmetingen L × B × H",
                    "status": "Resultaat",
                    "volume_pct": "Volume %",
                    "total_weight_g": "Totaalgewicht g",
                    "reason_text": "Waarom (niet)?",
                    "fitted_count": "Items die passen",
                    "unfitted_count": "Items die niet passen",
                }
            )

            picked_display["Volume %"] = picked_display["Volume %"].round(1)

            st.dataframe(
                picked_display,
                use_container_width=True,
                hide_index=True,
                height=min(70 + 40 * len(picked_display), 450),
            )


# ============================================================
# FAILURES
# ============================================================

with tab_failures:
    st.markdown(
        '<div class="section-title">Concrete lijst van producten die niet passen</div>',
        unsafe_allow_html=True,
    )

    failure_df = filtered[
        filtered["status"] != "PASS"
    ].copy()

    if failure_df.empty:
        st.success(
            "Geen failures in de huidige selectie."
        )

    else:
        failure_display = failure_df[
            [
                "product",
                "product_name",
                "product_dimensions",
                "package",
                "package_dimensions",
                "status",
                "reason_text",
                "volume_pct",
                "rotation",
            ]
        ].copy()

        failure_display.columns = [
            "Artikelnummer",
            "Productnaam",
            "Productafmetingen",
            "Verpakking",
            "Verpakkingsafmetingen",
            "Status",
            "Waarom?",
            "Volume %",
            "Rotatie",
        ]

        failure_display["Volume %"] = (
            pd.to_numeric(
                failure_display["Volume %"],
                errors="coerce",
            ).round(1)
        )

        st.dataframe(
            failure_display,
            use_container_width=True,
            hide_index=True,
            height=620,
        )

        st.download_button(
            "Download failures als CSV",
            data=failure_display.to_csv(
                index=False
            ).encode("utf-8"),
            file_name="servicesets_failures.csv",
            mime="text/csv",
        )


# ============================================================
# ALL DETAILS
# ============================================================

with tab_details:
    st.markdown(
        '<div class="section-title">Alle testresultaten</div>',
        unsafe_allow_html=True,
    )

    detail_display = filtered[
        [
            "product",
            "product_name",
            "product_dimensions",
            "product_volume_cm3",
            "product_weight_g",
            "package",
            "package_dimensions",
            "package_volume_cm3",
            "status",
            "reason_text",
            "volume_pct",
            "rotation",
        ]
    ].copy()

    detail_display.columns = [
        "Artikelnummer",
        "Productnaam",
        "Productafmetingen",
        "Productvolume cm³",
        "Gewicht g",
        "Verpakking",
        "Verpakkingsafmetingen",
        "Verpakkingsvolume cm³",
        "Resultaat",
        "Reden",
        "Volume %",
        "Rotatie",
    ]

    st.dataframe(
        detail_display,
        use_container_width=True,
        hide_index=True,
        height=700,
    )

    st.download_button(
        "Download huidige selectie als CSV",
        data=detail_display.to_csv(
            index=False
        ).encode("utf-8"),
        file_name="servicesets_analysis.csv",
        mime="text/csv",
    )


# ============================================================
# PRODUCT DETAIL / BESTE VERPAKKING
# ============================================================

st.markdown(
    '<div class="section-title">Beste verpakking per product</div>',
    unsafe_allow_html=True,
)

passes_df = filtered[
    filtered["status"] == "PASS"
].copy()

if not passes_df.empty:

    best = (
        passes_df.sort_values(
            [
                "product",
                "package_volume_cm3",
            ]
        )
        .groupby(
            [
                "product",
                "product_name",
                "product_dimensions",
            ],
            as_index=False,
        )
        .first()
    )

    best_display = best[
        [
            "product",
            "product_name",
            "product_dimensions",
            "package",
            "package_dimensions",
            "volume_pct",
            "rotation",
        ]
    ].copy()

    best_display.columns = [
        "Artikelnummer",
        "Productnaam",
        "Productafmetingen",
        "Kleinste passende verpakking",
        "Verpakkingsafmetingen",
        "Volume %",
        "Rotatie",
    ]

    best_display["Volume %"] = best_display[
        "Volume %"
    ].round(1)

    st.dataframe(
        best_display,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.info(
        "Er zijn geen passende verpakkingen gevonden in de huidige selectie."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    f"""
    <hr style="border:0;border-top:1px solid #E1E7E4;margin-top:35px;">
    <div style="text-align:center;color:{GREY};padding:10px 0 25px;">
        <strong style="color:{BRAND_GREEN};">ServiceSets.com</strong>
        · Packing Analysis
        · gebaseerd op de testresultaten uit <code>all_results.json</code>
    </div>
    """,
    unsafe_allow_html=True,
)
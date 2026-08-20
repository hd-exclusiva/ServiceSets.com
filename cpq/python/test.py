#!/usr/bin/env python3

"""
ServiceSets.com - Packing Tester

Leest automatisch:
    https://github.com/hd-exclusiva/ServiceSets.com

Data:
    data/products.json
    data/package_dimensions.json
    data/combination_scenarios.json   (benoemde service-sets)

Output:
    test_results/
        all_results.json
        passes.json
        failures.json
        summary.json
        data_problems.json
        recommendations.json
        combination_results.json      (scenario's + ad-hoc combinatie)

Voorbeeld:

    python tester.py

Alles testen:

    python tester.py --all

Specifieke producten:

    python tester.py --select 3560000,3552520

Aantal meegeven:

    python tester.py --select 3560000:2,3552520:3

Lokale JSON-bestanden gebruiken:

    python tester.py \
        --products products.json \
        --packages package_dimensions.json

Benoemde service-set scenario's testen (standaard aan,
leest data/combination_scenarios.json indien aanwezig,
anders van GitHub):

    python tester.py --all

Scenario's overslaan:

    python tester.py --all --no-scenarios

Eigen scenario-bestand:

    python tester.py --all --scenarios mijn_scenarios.json

Ad-hoc combinatie los van scenario's (items + aantallen
SAMEN in één verpakking testen, bv. 6x limonade + 1x water):

    python tester.py --all --combination 3552520:6,3552528:1
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from py3dbp import Packer, Bin, Item
except ImportError:
    sys.exit(
        "De library 'py3dbp' is niet geïnstalleerd.\n\n"
        "Installeer met:\n"
        "    pip install py3dbp --break-system-packages"
    )


# ============================================================================
# CONFIG
# ============================================================================

GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "hd-exclusiva/ServiceSets.com/main/data/"
)

PRODUCTS_URL = GITHUB_RAW_BASE + "products.json"
PACKAGES_URL = GITHUB_RAW_BASE + "package_dimensions.json"
SCENARIOS_URL = GITHUB_RAW_BASE + "combination_scenarios.json"

DEFAULT_OUTPUT_DIR = Path("test_results")
DEFAULT_SCENARIOS_PATH = Path("data/combination_scenarios.json")


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class Product:
    product_id: str
    name: str
    lengte: float
    breedte: float
    hoogte: float
    gewicht: float = 0.0

    # Nieuw: stapelbare artikelen (bv. bekers die in elkaar
    # nesten). Bij N stuks samen is de werkelijke hoogte
    # NIET N × hoogte, maar hoogte + (N-1) × stack_increment_h.
    stackable: bool = False
    stack_increment_h: Optional[float] = None

    # Nieuw: vouwbare artikelen (bv. vuilniszakken). Deze
    # nemen bij het inpakken de "gevouwen" afmetingen in,
    # niet hun volledige/uitgepakte l×b×h.
    foldable: bool = False
    folded_dimensions: Optional[
        List[Dict[str, float]]
    ] = None

    @property
    def volume(self) -> float:
        return (
            self.lengte
            * self.breedte
            * self.hoogte
        )


@dataclass
class Package:
    naam: str
    lengte: float
    breedte: float
    hoogte: float
    max_gewicht: Optional[float] = None

    @property
    def volume(self) -> float:
        return (
            self.lengte
            * self.breedte
            * self.hoogte
        )


@dataclass
class PackingUnit:

    """
    Eén fysieke 'eenheid' zoals die daadwerkelijk aan de
    py3dbp packer wordt aangeboden. Meestal is dit één
    artikel, maar:

    - Bij STAPELBARE artikelen (bv. bekers die in elkaar
      nesten) vertegenwoordigt één PackingUnit een hele
      stapel van N exemplaren: de hoogte is niet N × h,
      maar h + (N-1) × stack_increment_h.

    - Bij VOUWBARE artikelen (bv. vuilniszakken) worden de
      gevouwen afmetingen gebruikt in plaats van de volledige
      l×b×h, omdat ze in de praktijk gevouwen worden ingepakt.

    `represented_count` geeft aan hoeveel losse, fysieke
    artikelen deze ene packing-eenheid vertegenwoordigt —
    nodig om fitted/unfitted-aantallen correct te tellen.
    """

    item_id: str
    product_id: str
    product_name: str

    pack_l: float
    pack_w: float
    pack_h: float
    weight_g: float

    kind: str  # "normal" | "stack" | "folded"
    represented_count: int

    # Alleen relevant voor kind == "stack"
    stack_unit_h: Optional[float] = None
    stack_increment_h: Optional[float] = None

    # Alleen relevant voor kind == "folded"
    original_dimensions: Optional[
        Dict[str, float]
    ] = None


def build_packing_units(
    products: List[Product],
) -> List[PackingUnit]:

    """
    Groepeert een platte lijst Product-instanties (waarin
    hetzelfde artikel meerdere keren kan voorkomen, zie
    expand_scenario_items) tot de daadwerkelijke
    packing-eenheden: gestapeld waar mogelijk, gevouwen
    waar van toepassing, anders gewoon los per stuk.
    """

    groups: Dict[str, List[Product]] = {}

    for product in products:
        groups.setdefault(
            product.product_id,
            [],
        ).append(product)

    units: List[PackingUnit] = []

    for product_id, group in groups.items():

        product = group[0]
        count = len(group)

        if (
            product.stackable
            and product.stack_increment_h
            is not None
        ):

            increment = (
                product.stack_increment_h
            )

            stacked_height = (
                product.hoogte
                + (count - 1) * increment
                if count > 1
                else product.hoogte
            )

            units.append(
                PackingUnit(
                    item_id=(
                        f"{product_id}#stack"
                    ),
                    product_id=product_id,
                    product_name=product.name,
                    pack_l=product.lengte,
                    pack_w=product.breedte,
                    pack_h=stacked_height,
                    weight_g=(
                        product.gewicht
                        * count
                    ),
                    kind="stack",
                    represented_count=count,
                    stack_unit_h=product.hoogte,
                    stack_increment_h=increment,
                )
            )

        elif (
            product.foldable
            and product.folded_dimensions
        ):

            # Kleinste gevouwen optie kiezen
            # (meest realistische inpaksituatie).
            best_fold = min(
                product.folded_dimensions,
                key=lambda d: (
                    d["l"] * d["w"] * d["h"]
                ),
            )

            for index in range(count):

                units.append(
                    PackingUnit(
                        item_id=(
                            f"{product_id}"
                            f"#folded{index}"
                        ),
                        product_id=product_id,
                        product_name=product.name,
                        pack_l=best_fold["l"],
                        pack_w=best_fold["w"],
                        pack_h=best_fold["h"],
                        weight_g=product.gewicht,
                        kind="folded",
                        represented_count=1,
                        original_dimensions={
                            "l": product.lengte,
                            "w": product.breedte,
                            "h": product.hoogte,
                        },
                    )
                )

        else:

            for index in range(count):

                units.append(
                    PackingUnit(
                        item_id=(
                            f"{product_id}"
                            f"#{index}"
                        ),
                        product_id=product_id,
                        product_name=product.name,
                        pack_l=product.lengte,
                        pack_w=product.breedte,
                        pack_h=product.hoogte,
                        weight_g=product.gewicht,
                        kind="normal",
                        represented_count=1,
                    )
                )

    return units


# ============================================================================
# JSON / HTTP
# ============================================================================

def load_json_file(path: Path) -> Any:
    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def download_json(url: str) -> Any:
    print(f"  Download: {url}")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ServiceSets-Packing-Tester/1.0"
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            content = response.read().decode(
                "utf-8"
            )

        return json.loads(content)

    except Exception as exc:
        raise RuntimeError(
            f"Kan GitHub-data niet ophalen:\n"
            f"{url}\n\n"
            f"Fout: {exc}"
        ) from exc


def unwrap_list(
    data: Any,
    possible_keys: List[str],
) -> List[Dict[str, Any]]:

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in possible_keys:

            value = data.get(key)

            if isinstance(value, list):
                return value

    raise ValueError(
        "JSON bevat geen lijst met records."
    )


# ============================================================================
# PRODUCT LOADING
# ============================================================================

def detect_product(
    row: Dict[str, Any],
    index: int,
) -> Product:

    """
    Verwacht:

        num
        name
        l
        w
        h
        weight_g
    """

    required = [
        "num",
        "name",
        "l",
        "w",
        "h",
    ]

    missing = [
        key
        for key in required
        if row.get(key) in (None, "")
    ]

    if missing:
        raise ValueError(
            f"Ontbrekende velden: "
            f"{', '.join(missing)}"
        )

    try:

        stackable = bool(
            row.get("stackable", False)
        )

        stack_increment_h = row.get(
            "stack_increment_h"
        )

        if stack_increment_h is not None:
            stack_increment_h = float(
                stack_increment_h
            )

        foldable = bool(
            row.get("foldable", False)
        )

        folded_dimensions_raw = row.get(
            "folded_dimensions"
        )

        folded_dimensions = None

        if isinstance(
            folded_dimensions_raw,
            list,
        ) and folded_dimensions_raw:

            folded_dimensions = []

            for option in folded_dimensions_raw:

                if not isinstance(
                    option,
                    dict,
                ):
                    continue

                try:
                    folded_dimensions.append(
                        {
                            "l": float(
                                option["l"]
                            ),
                            "w": float(
                                option["w"]
                            ),
                            "h": float(
                                option["h"]
                            ),
                        }
                    )

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue

            if not folded_dimensions:
                folded_dimensions = None

        return Product(
            product_id=str(row["num"]),
            name=str(row["name"]),
            lengte=float(row["l"]),
            breedte=float(row["w"]),
            hoogte=float(row["h"]),
            gewicht=float(
                row.get("weight_g", 0) or 0
            ),
            stackable=stackable,
            stack_increment_h=stack_increment_h,
            foldable=foldable,
            folded_dimensions=folded_dimensions,
        )

    except (TypeError, ValueError) as exc:

        raise ValueError(
            f"Ongeldige numerieke afmeting: "
            f"{exc}"
        ) from exc


def load_products(
    data: Any,
) -> Tuple[
    List[Product],
    List[Dict[str, Any]],
]:

    rows = unwrap_list(
        data,
        ["products"],
    )

    products = []
    problems = []

    for index, row in enumerate(
        rows,
        start=1,
    ):

        if not isinstance(row, dict):
            problems.append(
                {
                    "type": "INVALID_PRODUCT",
                    "index": index,
                    "error": "Record is geen object",
                    "record": row,
                }
            )
            continue

        try:
            product = detect_product(
                row,
                index,
            )

            # Basisvalidatie.
            if (
                product.lengte <= 0
                or product.breedte <= 0
                or product.hoogte <= 0
            ):
                raise ValueError(
                    "Afmetingen moeten groter dan 0 zijn"
                )

            if product.gewicht < 0:
                raise ValueError(
                    "Gewicht mag niet negatief zijn"
                )

            products.append(product)

        except Exception as exc:

            problems.append(
                {
                    "type": "INVALID_PRODUCT",
                    "index": index,
                    "error": str(exc),
                    "record": row,
                }
            )

    return products, problems


# ============================================================================
# PACKAGE LOADING
# ============================================================================

def detect_package(
    row: Dict[str, Any],
    index: int,
) -> Package:

    """
    Verwacht:

        naam
        lengte_cm
        hoogte_cm
        breedte_cm

    max_gewicht is optioneel.
    """

    required = [
        "naam",
        "lengte_cm",
        "breedte_cm",
        "hoogte_cm",
    ]

    missing = [
        key
        for key in required
        if row.get(key) in (None, "")
    ]

    if missing:
        raise ValueError(
            f"Ontbrekende velden: "
            f"{', '.join(missing)}"
        )

    max_gewicht = row.get(
        "max_gewicht"
    )

    if max_gewicht in (
        None,
        "",
    ):
        max_gewicht = None

    else:
        max_gewicht = float(
            max_gewicht
        )

    try:
        package = Package(
            naam=str(row["naam"]),
            lengte=float(
                row["lengte_cm"]
            ),
            breedte=float(
                row["breedte_cm"]
            ),
            hoogte=float(
                row["hoogte_cm"]
            ),
            max_gewicht=max_gewicht,
        )

    except (TypeError, ValueError) as exc:

        raise ValueError(
            f"Ongeldige verpakking: {exc}"
        ) from exc

    if (
        package.lengte <= 0
        or package.breedte <= 0
        or package.hoogte <= 0
    ):
        raise ValueError(
            "Afmetingen moeten groter dan 0 zijn"
        )

    return package


def load_packages(
    data: Any,
) -> Tuple[
    List[Package],
    List[Dict[str, Any]],
]:

    rows = unwrap_list(
        data,
        [
            "package_dimensions",
            "packages",
        ],
    )

    packages = []
    problems = []

    for index, row in enumerate(
        rows,
        start=1,
    ):

        if not isinstance(row, dict):
            problems.append(
                {
                    "type": "INVALID_PACKAGE",
                    "index": index,
                    "error": "Record is geen object",
                    "record": row,
                }
            )
            continue

        try:
            packages.append(
                detect_package(
                    row,
                    index,
                )
            )

        except Exception as exc:

            problems.append(
                {
                    "type": "INVALID_PACKAGE",
                    "index": index,
                    "error": str(exc),
                    "record": row,
                }
            )

    return packages, problems


# ============================================================================
# COMBINATION SCENARIOS (benoemde service-set samenstellingen)
# ============================================================================

def load_scenarios(
    data: Any,
    products: List[Product],
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:

    """
    Laadt benoemde combinatie-scenario's ("service-sets") uit JSON.

    Verwacht per scenario:

        id
        name
        items: [{product_id, quantity}, ...]

    category en description zijn optioneel.
    """

    rows = unwrap_list(
        data,
        ["scenarios"],
    )

    lookup = {
        product.product_id: product
        for product in products
    }

    scenarios = []
    problems = []

    for index, row in enumerate(
        rows,
        start=1,
    ):

        if not isinstance(row, dict):
            problems.append(
                {
                    "type": "INVALID_SCENARIO",
                    "index": index,
                    "error": "Record is geen object",
                    "record": row,
                }
            )
            continue

        scenario_id = row.get(
            "id",
            f"scenario_{index}",
        )

        items_raw = row.get("items")

        if not isinstance(
            items_raw,
            list,
        ) or not items_raw:

            problems.append(
                {
                    "type": "INVALID_SCENARIO",
                    "index": index,
                    "error": (
                        f"Scenario '{scenario_id}' "
                        f"heeft geen (geldige) items-lijst"
                    ),
                    "record": row,
                }
            )
            continue

        resolved_items = []
        missing_products = []

        for item in items_raw:

            if not isinstance(item, dict):
                continue

            product_id = str(
                item.get(
                    "product_id",
                    "",
                )
            )

            quantity = item.get(
                "quantity",
                1,
            )

            try:
                quantity = int(quantity)

            except (TypeError, ValueError):
                quantity = 0

            product = lookup.get(
                product_id
            )

            if product is None:
                missing_products.append(
                    product_id
                )
                continue

            if quantity <= 0:
                missing_products.append(
                    f"{product_id} "
                    f"(ongeldig aantal: "
                    f"{item.get('quantity')})"
                )
                continue

            resolved_items.append(
                {
                    "product": product,
                    "quantity": quantity,
                    "note": item.get(
                        "note",
                        "",
                    ),
                }
            )

        if missing_products:
            problems.append(
                {
                    "type": "SCENARIO_MISSING_PRODUCTS",
                    "index": index,
                    "error": (
                        f"Scenario '{scenario_id}' "
                        f"verwijst naar onbekende of "
                        f"ongeldige producten"
                    ),
                    "record": missing_products,
                }
            )

        if not resolved_items:
            continue

        scenarios.append(
            {
                "id": scenario_id,
                "name": row.get(
                    "name",
                    scenario_id,
                ),
                "category": row.get(
                    "category",
                    "",
                ),
                "description": row.get(
                    "description",
                    "",
                ),
                "items": resolved_items,
            }
        )

    return scenarios, problems


def expand_scenario_items(
    items: List[Dict[str, Any]],
) -> List[Product]:

    """
    Zet [{product, quantity}, ...] om naar een platte
    lijst van Product-instanties (elk artikel zoveel keer
    herhaald als de gevraagde hoeveelheid), zodat alle
    exemplaren SAMEN in één verpakking getest worden.
    """

    expanded = []

    for entry in items:

        expanded.extend(
            [entry["product"]] * entry["quantity"]
        )

    return expanded


def run_scenario_across_packages(
    scenario: Dict[str, Any],
    packages: List[Package],
) -> Dict[str, Any]:

    """
    Test een volledig scenario (alle items + aantallen
    samen) tegen elke verpakking, en bepaalt de kleinste
    passende verpakking.
    """

    combination_products = expand_scenario_items(
        scenario["items"]
    )

    per_package_results = []

    for package in sorted(
        packages,
        key=lambda p: p.volume,
    ):

        result = test_products_together(
            combination_products,
            package,
        )

        per_package_results.append(
            result
        )

    fitting = [
        result
        for result in per_package_results
        if result["status"] == "PASS"
    ]

    fitting.sort(
        key=lambda result: result.get(
            "package_volume_cm3",
            float("inf"),
        )
    )

    items_summary = [
        {
            "product_id": entry["product"].product_id,
            "product_name": entry["product"].name,
            "quantity": entry["quantity"],
            "note": entry["note"],
        }
        for entry in scenario["items"]
    ]

    total_quantity = sum(
        entry["quantity"]
        for entry in scenario["items"]
    )

    return {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "category": scenario["category"],
        "description": scenario["description"],

        "items": items_summary,
        "distinct_articles": len(
            items_summary
        ),
        "total_quantity": total_quantity,

        "fits_any_package": len(fitting) > 0,

        "smallest_fitting_package": (
            fitting[0]["package"]
            if fitting
            else None
        ),

        "packages_that_fit": [
            result["package"]
            for result in fitting
        ],

        "packages_that_do_not_fit": [
            result["package"]
            for result in per_package_results
            if result["status"] != "PASS"
        ],

        "results_per_package": per_package_results,
    }


# ============================================================================
# ROTATION / DIMENSION CHECK
# ============================================================================

def find_possible_rotations(
    product: Product,
    package: Package,
) -> List[Tuple[float, float, float]]:

    """
    Bepaal alle unieke rotaties waarbij het product
    als rechthoekig blok in de verpakking past.
    """

    dimensions = [
        product.lengte,
        product.breedte,
        product.hoogte,
    ]

    rotations = set()

    import itertools

    for rotation in itertools.permutations(
        dimensions
    ):

        if (
            rotation[0] <= package.lengte
            and rotation[1] <= package.breedte
            and rotation[2] <= package.hoogte
        ):
            rotations.add(
                tuple(
                    round(x, 3)
                    for x in rotation
                )
            )

    return sorted(rotations)


def dimension_failure_reason(
    product: Product,
    package: Package,
) -> Dict[str, Any]:

    """
    Probeert uit te leggen waarom een product
    niet in een verpakking past.
    """

    product_dims = sorted(
        [
            product.lengte,
            product.breedte,
            product.hoogte,
        ],
        reverse=True,
    )

    package_dims = sorted(
        [
            package.lengte,
            package.breedte,
            package.hoogte,
        ],
        reverse=True,
    )

    failures = []

    for product_dim, package_dim in zip(
        product_dims,
        package_dims,
    ):

        if product_dim > package_dim:
            failures.append(
                {
                    "product_dimension_cm": product_dim,
                    "package_dimension_cm": package_dim,
                    "difference_cm": round(
                        product_dim - package_dim,
                        3,
                    ),
                }
            )

    if failures:

        return {
            "reason": "PRODUCT_TOO_LARGE",
            "details": failures,
        }

    return {
        "reason": "UNKNOWN_PACKING_FAILURE",
        "details": [],
    }


# ============================================================================
# SINGLE PRODUCT TEST
# ============================================================================

def _extract_placements(
    bin_result: Any,
    unit_by_item_id: Optional[
        Dict[str, "PackingUnit"]
    ] = None,
) -> List[Dict[str, Any]]:

    """
    Zet de py3dbp bin_result.items (na packing) om naar
    een platte, JSON-vriendelijke lijst met per item de
    werkelijke positie (x, y, z) en de werkelijk gebruikte
    afmetingen ná rotatie — dit is de basis voor een 3D
    plaatsingstekening.

    Als unit_by_item_id is meegegeven, wordt ook de
    PackingUnit-metadata (kind: normal/stack/folded,
    represented_count, stack-informatie) toegevoegd, zodat
    het dashboard gestapelde/gevouwen artikelen apart kan
    tonen.
    """

    unit_by_item_id = unit_by_item_id or {}

    placements = []

    for item in bin_result.items:

        # Werkelijke, gedraaide afmetingen. py3dbp had in
        # oudere voorbeelden "getDimension" (camelCase) —
        # de geïnstalleerde versie heeft "get_dimension"
        # (snake_case). Beide worden geprobeerd zodat dit
        # ook op oudere/nieuwere py3dbp-versies werkt.
        try:
            dims = item.get_dimension()

        except AttributeError:

            try:
                dims = item.getDimension()

            except Exception:
                dims = [
                    item.width,
                    item.height,
                    item.depth,
                ]

        try:
            position = [
                float(coord)
                for coord in item.position
            ]

        except Exception:
            position = [0.0, 0.0, 0.0]

        try:
            dimension = [
                float(dim)
                for dim in dims
            ]

        except Exception:
            dimension = [
                float(item.width),
                float(item.height),
                float(item.depth),
            ]

        raw_name = str(item.name)
        unit = unit_by_item_id.get(raw_name)

        if unit is not None:
            product_id = unit.product_id
            product_name = unit.product_name
            kind = unit.kind
            represented_count = (
                unit.represented_count
            )
            stack_unit_h = unit.stack_unit_h
            stack_increment_h = (
                unit.stack_increment_h
            )
            original_dimensions = (
                unit.original_dimensions
            )

        else:
            # Backwards compatible fallback
            # (geen PackingUnit meegegeven).
            product_id = raw_name.split("#")[0]
            product_name = product_id
            kind = "normal"
            represented_count = 1
            stack_unit_h = None
            stack_increment_h = None
            original_dimensions = None

        placements.append(
            {
                "item_name": raw_name,
                "product_id": product_id,
                "product_name": product_name,
                "position": position,
                "dimensions": dimension,
                "rotation_type": item.rotation_type,

                "kind": kind,
                "represented_count": represented_count,
                "stack_unit_h": stack_unit_h,
                "stack_increment_h": stack_increment_h,
                "original_dimensions": original_dimensions,
            }
        )

    return placements


def test_product_in_package(
    product: Product,
    package: Package,
) -> Dict[str, Any]:

    rotations = find_possible_rotations(
        product,
        package,
    )

    # Eerst simpele geometrische check.
    if not rotations:

        dimension_reason = (
            dimension_failure_reason(
                product,
                package,
            )
        )

        return {
            "product": product.product_id,
            "product_name": product.name,

            "product_dimensions_cm": {
                "lengte": product.lengte,
                "breedte": product.breedte,
                "hoogte": product.hoogte,
            },

            "package": package.naam,

            "package_dimensions_cm": {
                "lengte": package.lengte,
                "breedte": package.breedte,
                "hoogte": package.hoogte,
            },

            "product_weight_g": product.gewicht,

            "package_max_weight_g": (
                package.max_gewicht
            ),

            "fits": False,
            "status": "FAIL",

            "reason": dimension_reason[
                "reason"
            ],

            "reason_details": dimension_reason[
                "details"
            ],

            "rotation": None,

            "volume_pct": round(
                (
                    product.volume
                    / package.volume
                ) * 100,
                1,
            ),

            "product_volume_cm3": round(
                product.volume,
                2,
            ),

            "package_volume_cm3": round(
                package.volume,
                2,
            ),
        }

    # Gewicht controleren.
    if (
        package.max_gewicht is not None
        and product.gewicht
        > package.max_gewicht
    ):

        return {
            "product": product.product_id,
            "product_name": product.name,

            "product_dimensions_cm": {
                "lengte": product.lengte,
                "breedte": product.breedte,
                "hoogte": product.hoogte,
            },

            "package": package.naam,

            "package_dimensions_cm": {
                "lengte": package.lengte,
                "breedte": package.breedte,
                "hoogte": package.hoogte,
            },

            "product_weight_g": product.gewicht,

            "package_max_weight_g": (
                package.max_gewicht
            ),

            "fits": False,
            "status": "FAIL",

            "reason": "WEIGHT_LIMIT",

            "reason_details": [
                {
                    "product_weight_g": product.gewicht,
                    "max_weight_g": package.max_gewicht,
                }
            ],

            "rotation": list(
                rotations[0]
            ),

            "volume_pct": round(
                (
                    product.volume
                    / package.volume
                ) * 100,
                1,
            ),

            "product_volume_cm3": round(
                product.volume,
                2,
            ),

            "package_volume_cm3": round(
                package.volume,
                2,
            ),
        }

    # ------------------------------------------------------------------
    # py3dbp
    # ------------------------------------------------------------------

    packer = Packer()

    max_weight = (
        package.max_gewicht
        if package.max_gewicht is not None
        else 1_000_000_000
    )

    packer.add_bin(
        Bin(
            package.naam,
            package.lengte,
            package.breedte,
            package.hoogte,
            max_weight,
        )
    )

    packer.add_item(
        Item(
            product.product_id,
            product.lengte,
            product.breedte,
            product.hoogte,
            product.gewicht,
        )
    )

    try:

        packer.pack(
            bigger_first=True,
            distribute_items=False,
            number_of_decimals=2,
        )

    except Exception as exc:

        return {
            "product": product.product_id,
            "product_name": product.name,
            "package": package.naam,
            "fits": False,
            "status": "ERROR",
            "reason": "PACKING_ENGINE_ERROR",
            "reason_details": [
                str(exc)
            ],
        }

    bin_result = packer.bins[0]

    unfitted = len(
        bin_result.unfitted_items
    )

    if unfitted == 0:

        used_pct = (
            product.volume
            / package.volume
        ) * 100

        # py3dbp kan positie/dimensies bevatten.
        fitted_item = None

        if bin_result.items:
            fitted_item = (
                bin_result.items[0]
            )

        rotation = None

        if fitted_item is not None:

            try:
                rotation = _extract_placements(
                    bin_result,
                    {
                        product.product_id: product.name
                    },
                )[0]["dimensions"]

            except Exception:
                rotation = list(
                    rotations[0]
                )

        if rotation is None:
            rotation = list(
                rotations[0]
            )

        return {
            "product": product.product_id,
            "product_name": product.name,

            "product_dimensions_cm": {
                "lengte": product.lengte,
                "breedte": product.breedte,
                "hoogte": product.hoogte,
            },

            "package": package.naam,

            "package_dimensions_cm": {
                "lengte": package.lengte,
                "breedte": package.breedte,
                "hoogte": package.hoogte,
            },

            "product_weight_g": product.gewicht,

            "package_max_weight_g": (
                package.max_gewicht
            ),

            "fits": True,
            "status": "PASS",

            "reason": None,
            "reason_details": [],

            "rotation": rotation,

            "volume_pct": round(
                min(
                    used_pct,
                    100.0,
                ),
                1,
            ),

            "product_volume_cm3": round(
                product.volume,
                2,
            ),

            "package_volume_cm3": round(
                package.volume,
                2,
            ),
        }

    # py3dbp zegt dat het niet past.
    return {
        "product": product.product_id,
        "product_name": product.name,

        "product_dimensions_cm": {
            "lengte": product.lengte,
            "breedte": product.breedte,
            "hoogte": product.hoogte,
        },

        "package": package.naam,

        "package_dimensions_cm": {
            "lengte": package.lengte,
            "breedte": package.breedte,
            "hoogte": package.hoogte,
        },

        "product_weight_g": product.gewicht,

        "package_max_weight_g": (
            package.max_gewicht
        ),

        "fits": False,
        "status": "FAIL",

        "reason": "PACKING_ENGINE_REJECTED",

        "reason_details": [],

        "rotation": None,

        "volume_pct": round(
            (
                product.volume
                / package.volume
            ) * 100,
            1,
        ),

        "product_volume_cm3": round(
            product.volume,
            2,
        ),

        "package_volume_cm3": round(
            package.volume,
            2,
        ),
    }


# ============================================================================
# MULTI ITEM TEST
# ============================================================================

def test_products_together(
    products: List[Product],
    package: Package,
) -> Dict[str, Any]:

    packing_units = build_packing_units(
        products
    )

    packer = Packer()

    max_weight = (
        package.max_gewicht
        if package.max_gewicht is not None
        else 1_000_000_000
    )

    packer.add_bin(
        Bin(
            package.naam,
            package.lengte,
            package.breedte,
            package.hoogte,
            max_weight,
        )
    )

    for unit in packing_units:

        packer.add_item(
            Item(
                unit.item_id,
                unit.pack_l,
                unit.pack_w,
                unit.pack_h,
                unit.weight_g,
            )
        )

    try:

        packer.pack(
            bigger_first=True,
            distribute_items=False,
            number_of_decimals=2,
        )

    except Exception as exc:

        return {
            "fits": False,
            "status": "ERROR",
            "reason": "PACKING_ENGINE_ERROR",
            "reason_details": [
                str(exc)
            ],
        }

    unit_by_item_id = {
        unit.item_id: unit
        for unit in packing_units
    }

    bin_result = packer.bins[0]

    # unfitted/fitted op niveau van py3dbp-eenheden
    # (een "stack"-eenheid is hier één regel, ook al
    # vertegenwoordigt die meerdere fysieke artikelen).
    unfitted_units = [
        unit_by_item_id[item.name]
        for item in bin_result.unfitted_items
        if item.name in unit_by_item_id
    ]

    fitted_units = [
        unit_by_item_id[item.name]
        for item in bin_result.items
        if item.name in unit_by_item_id
    ]

    unfitted = [
        item.name
        for item in bin_result.unfitted_items
    ]

    fitted = [
        item.name
        for item in bin_result.items
    ]

    # Werkelijk ingenomen volume — gebaseerd op de
    # PACK-afmetingen (dus MET stapel-/vouwreductie), niet
    # op de "uitgepakte" l×b×h. Dit is ook wat de packer
    # zelf gebruikt om te bepalen of het past.
    total_volume = sum(
        unit.pack_l * unit.pack_w * unit.pack_h
        for unit in packing_units
    )

    # Totaalgewicht verandert niet door stapelen/vouwen.
    total_weight = sum(
        product.gewicht
        for product in products
    )

    # Fitted/unfitted in ECHTE artikel-aantallen (een
    # gestapelde eenheid van bv. 6 bekers telt als 6, niet
    # als 1).
    fitted_article_count = sum(
        unit.represented_count
        for unit in fitted_units
    )

    unfitted_article_count = sum(
        unit.represented_count
        for unit in unfitted_units
    )

    stacked_units = [
        unit
        for unit in packing_units
        if unit.kind == "stack"
    ]

    folded_units = [
        unit
        for unit in packing_units
        if unit.kind == "folded"
    ]

    return {
        "fits": len(unfitted) == 0,
        "status": (
            "PASS"
            if len(unfitted) == 0
            else "FAIL"
        ),

        "reason": (
            None
            if len(unfitted) == 0
            else "ITEMS_DID_NOT_ALL_FIT"
        ),

        "reason_details": {
            "unfitted_items": unfitted,
            "fitted_items": fitted,
        },

        "placements": _extract_placements(
            bin_result,
            unit_by_item_id,
        ),

        "package": package.naam,

        "package_dimensions_cm": {
            "lengte": package.lengte,
            "breedte": package.breedte,
            "hoogte": package.hoogte,
        },

        "total_product_volume_cm3": round(
            total_volume,
            2,
        ),

        "package_volume_cm3": round(
            package.volume,
            2,
        ),

        "volume_pct": round(
            min(
                (
                    total_volume
                    / package.volume
                ) * 100,
                100.0,
            ),
            1,
        ),

        "total_weight_g": round(
            total_weight,
            2,
        ),

        "package_max_weight_g": (
            package.max_gewicht
        ),

        "number_of_products": len(
            products
        ),

        "fitted_count": fitted_article_count,

        "unfitted_count": unfitted_article_count,

        # Nieuw: inzicht in stapelen/vouwen voor deze
        # combinatie, direct bruikbaar voor het dashboard.
        "stacked_articles": {
            "count": len(stacked_units),
            "details": [
                {
                    "product_id": unit.product_id,
                    "product_name": unit.product_name,
                    "stacked_count": unit.represented_count,
                    "unit_height_cm": unit.stack_unit_h,
                    "stack_increment_cm": unit.stack_increment_h,
                    "effective_height_cm": unit.pack_h,
                    "fits": unit.item_id in fitted,
                }
                for unit in stacked_units
            ],
        },

        "folded_articles": {
            "count": len(folded_units),
            "details": [
                {
                    "product_id": unit.product_id,
                    "product_name": unit.product_name,
                    "original_dimensions_cm": unit.original_dimensions,
                    "folded_dimensions_cm": {
                        "l": unit.pack_l,
                        "w": unit.pack_w,
                        "h": unit.pack_h,
                    },
                    "fits": unit.item_id in fitted,
                }
                for unit in folded_units
            ],
        },
    }


# ============================================================================
# SELECTIE
# ============================================================================

def select_products(
    products: List[Product],
    selection: Optional[str],
) -> List[Tuple[Product, int]]:

    if not selection:
        return [
            (
                product,
                1,
            )
            for product in products
        ]

    lookup = {
        product.product_id: product
        for product in products
    }

    selected = []

    for part in selection.split(","):

        part = part.strip()

        if not part:
            continue

        if ":" in part:
            product_id, amount = (
                part.split(
                    ":",
                    1,
                )
            )

            try:
                amount = int(amount)

            except ValueError:
                print(
                    f"⚠ Ongeldig aantal: {part}"
                )
                continue

        else:
            product_id = part
            amount = 1

        product = lookup.get(
            product_id
        )

        if product is None:

            print(
                f"⚠ Product niet gevonden: "
                f"{product_id}"
            )

            continue

        if amount <= 0:

            print(
                f"⚠ Aantal moet > 0 zijn: "
                f"{part}"
            )

            continue

        selected.append(
            (
                product,
                amount,
            )
        )

    return selected


# ============================================================================
# OUTPUT
# ============================================================================

def save_json(
    path: Path,
    data: Any,
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def write_summary(
    output_dir: Path,
    results: List[Dict[str, Any]],
    data_problems: List[Dict[str, Any]],
) -> None:

    total = len(results)

    passes = sum(
        1
        for result in results
        if result.get("status") == "PASS"
    )

    failures = sum(
        1
        for result in results
        if result.get("status") == "FAIL"
    )

    errors = sum(
        1
        for result in results
        if result.get("status") == "ERROR"
    )

    products = len(
        {
            result.get("product")
            for result in results
            if result.get("product")
        }
    )

    packages = len(
        {
            result.get("package")
            for result in results
            if result.get("package")
        }
    )

    summary = {
        "total_tests": total,
        "pass": passes,
        "fail": failures,
        "errors": errors,
        "pass_percentage": round(
            (
                passes / total * 100
            )
            if total
            else 0,
            1,
        ),
        "products_tested": products,
        "packages_tested": packages,
        "data_problems": len(
            data_problems
        ),
    }

    save_json(
        output_dir / "summary.json",
        summary,
    )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Test ServiceSets producten "
            "tegen alle verpakkingen."
        )
    )

    parser.add_argument(
        "--products",
        help=(
            "Lokaal products.json. "
            "Als dit ontbreekt wordt GitHub gebruikt."
        ),
    )

    parser.add_argument(
        "--packages",
        help=(
            "Lokaal package_dimensions.json. "
            "Als dit ontbreekt wordt GitHub gebruikt."
        ),
    )

    parser.add_argument(
        "--select",
        help=(
            "Producten testen. "
            "Bijvoorbeeld: 3560000,3552520:2"
        ),
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Alle producten individueel "
            "tegen alle verpakkingen testen."
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            DEFAULT_OUTPUT_DIR
        ),
        help=(
            "Outputmap. "
            "Standaard: test_results"
        ),
    )

    parser.add_argument(
        "--combination",
        nargs="+",
        help=(
            "Test geselecteerde producten "
            "samen in verpakkingen. "
            "Bijvoorbeeld: 3552520:6,3552528:1"
        ),
    )

    parser.add_argument(
        "--scenarios",
        help=(
            "Lokaal combination_scenarios.json met "
            "benoemde service-set samenstellingen "
            "(artikelen + aantallen). Standaard: "
            f"{DEFAULT_SCENARIOS_PATH} indien aanwezig, "
            "anders GitHub."
        ),
    )

    parser.add_argument(
        "--no-scenarios",
        action="store_true",
        help=(
            "Sla het testen van combinatie-scenario's "
            "over."
        ),
    )

    args = parser.parse_args()

    output_dir = Path(
        args.output
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 70)
    print(
        " ServiceSets.com Packing Tester"
    )
    print("=" * 70)

    # ------------------------------------------------------------------
    # PRODUCTS
    # ------------------------------------------------------------------

    print("\nProductdata laden...")

    try:

        if args.products:

            product_data = load_json_file(
                Path(args.products)
            )

        else:

            product_data = download_json(
                PRODUCTS_URL
            )

        products, product_problems = (
            load_products(
                product_data
            )
        )

    except Exception as exc:

        sys.exit(
            f"\n❌ Productdata fout:\n{exc}"
        )

    print(
        f"  ✓ {len(products):,} producten geladen"
    )

    # ------------------------------------------------------------------
    # PACKAGES
    # ------------------------------------------------------------------

    print("\nVerpakkingsdata laden...")

    try:

        if args.packages:

            package_data = load_json_file(
                Path(args.packages)
            )

        else:

            package_data = download_json(
                PACKAGES_URL
            )

        packages, package_problems = (
            load_packages(
                package_data
            )
        )

    except Exception as exc:

        sys.exit(
            f"\n❌ Verpakkingsdata fout:\n{exc}"
        )

    print(
        f"  ✓ {len(packages)} verpakkingen geladen"
    )

    # ------------------------------------------------------------------
    # DATA PROBLEMS
    # ------------------------------------------------------------------

    data_problems = (
        product_problems
        + package_problems
    )

    save_json(
        output_dir / "data_problems.json",
        data_problems,
    )

    if data_problems:

        print(
            f"\n⚠ {len(data_problems)} "
            f"dataproblemen gevonden."
        )

        print(
            f"  Zie: "
            f"{output_dir / 'data_problems.json'}"
        )

    # ------------------------------------------------------------------
    # SELECT PRODUCTS
    # ------------------------------------------------------------------

    selected = select_products(
        products,
        args.select,
    )

    if not selected:

        sys.exit(
            "\nGeen geldige producten geselecteerd."
        )

    # --all betekent alle producten.
    if args.all:

        selected = [
            (
                product,
                1,
            )
            for product in products
        ]

    # ------------------------------------------------------------------
    # INDIVIDUAL PRODUCT × PACKAGE
    # ------------------------------------------------------------------

    print(
        "\nIndividuele packing-tests uitvoeren..."
    )

    all_results = []

    for product, amount in selected:

        for package in sorted(
            packages,
            key=lambda p: p.volume,
        ):

            # Test ieder exemplaar apart.
            #
            # Bij amount > 1 wordt ieder exemplaar
            # afzonderlijk getest.
            for instance in range(
                amount
            ):

                result = (
                    test_product_in_package(
                        product,
                        package,
                    )
                )

                result[
                    "quantity_instance"
                ] = instance + 1

                result[
                    "requested_quantity"
                ] = amount

                all_results.append(
                    result
                )

    # ------------------------------------------------------------------
    # SAVE ALL RESULTS
    # ------------------------------------------------------------------

    save_json(
        output_dir / "all_results.json",
        all_results,
    )

    passes = [
        result
        for result in all_results
        if result["status"] == "PASS"
    ]

    failures = [
        result
        for result in all_results
        if result["status"] != "PASS"
    ]

    save_json(
        output_dir / "passes.json",
        passes,
    )

    save_json(
        output_dir / "failures.json",
        failures,
    )

    write_summary(
        output_dir,
        all_results,
        data_problems,
    )

    # ------------------------------------------------------------------
    # BEST PACKAGE PER PRODUCT
    # ------------------------------------------------------------------

    recommendations = []

    for product, amount in selected:

        product_results = [
            result
            for result in all_results
            if result["product"]
            == product.product_id
        ]

        fitting = [
            result
            for result in product_results
            if result["status"]
            == "PASS"
        ]

        fitting.sort(
            key=lambda result:
                result.get(
                    "package_volume_cm3",
                    float("inf"),
                )
        )

        recommendations.append(
            {
                "product": product.product_id,
                "product_name": product.name,
                "requested_quantity": amount,

                "smallest_package": (
                    fitting[0]["package"]
                    if fitting
                    else None
                ),

                "packages_that_fit": [
                    result["package"]
                    for result in fitting
                ],

                "packages_that_do_not_fit": [
                    result["package"]
                    for result in product_results
                    if result["status"]
                    != "PASS"
                ],
            }
        )

    save_json(
        output_dir
        / "recommendations.json",
        recommendations,
    )

    # ------------------------------------------------------------------
    # COMBINATIONS / SERVICE-SET SCENARIO'S
    # ------------------------------------------------------------------
    #
    # Twee bronnen worden hier samengevoegd tot één bestand
    # (combination_results.json), zodat het dashboard maar
    # één format hoeft te lezen:
    #
    #   1) Benoemde scenario's uit data/combination_scenarios.json
    #      (herhaalbaar, bv. "Koffie service-set", "Limonade-set").
    #   2) Een eventuele ad-hoc combinatie via --combination.
    #
    # Bij elk scenario worden ALLE items + aantallen SAMEN
    # in één verpakking getest (niet los na elkaar), zodat
    # zichtbaar wordt of bv. 6x "Stick Limonade" samen met de
    # rest van de set nog past.

    scenario_problems: List[Dict[str, Any]] = []
    combination_results: List[Dict[str, Any]] = []

    if not args.no_scenarios:

        print(
            "\nCombinatie-scenario's laden..."
        )

        scenario_data = None
        scenario_source = None

        if args.scenarios:

            candidate_paths = [Path(args.scenarios)]

        else:

            # Meerdere logische locaties proberen, zodat het
            # niet uitmaakt vanuit welke map je het script
            # start.
            candidate_paths = [
                DEFAULT_SCENARIOS_PATH,
                Path("combination_scenarios.json"),
                Path(__file__).resolve().parent
                / "data"
                / "combination_scenarios.json",
                Path(__file__).resolve().parent
                / "combination_scenarios.json",
            ]

        for candidate in candidate_paths:

            if candidate.exists():

                try:
                    scenario_data = load_json_file(
                        candidate
                    )
                    scenario_source = str(
                        candidate
                    )
                    break

                except Exception as exc:
                    print(
                        f"  ⚠ Kon {candidate} niet "
                        f"lezen: {exc}"
                    )

        if scenario_data is None:

            try:
                scenario_data = download_json(
                    SCENARIOS_URL
                )
                scenario_source = SCENARIOS_URL

            except Exception as exc:

                print(
                    "\n"
                    "  ╔═══════════════════════════════"
                    "══════════════════════════════╗"
                )
                print(
                    "  ⚠ GEEN COMBINATIE-SCENARIO'S "
                    "GELADEN — service-sets/aantallen "
                    "worden NIET getest."
                )
                print(
                    "  Gezocht op: "
                    + ", ".join(
                        str(p) for p in candidate_paths
                    )
                )
                print(
                    f"  GitHub-fallback ({SCENARIOS_URL}) "
                    f"gaf: {exc}"
                )
                print(
                    "  Los op met: "
                    "--scenarios pad/naar/"
                    "combination_scenarios.json"
                )
                print(
                    "  ╚═══════════════════════════════"
                    "══════════════════════════════╝"
                )

        if scenario_data is not None:

            print(
                f"  Bron: {scenario_source}"
            )

        if scenario_data is not None:

            scenarios, scenario_problems = (
                load_scenarios(
                    scenario_data,
                    products,
                )
            )

            print(
                f"  ✓ {len(scenarios)} scenario('s) "
                f"geladen"
            )

            if scenario_problems:

                print(
                    f"  ⚠ {len(scenario_problems)} "
                    f"scenario-problemen "
                    f"(zie data_problems.json)"
                )

            print(
                "\nScenario's testen "
                "(items + aantallen samen "
                "per verpakking)..."
            )

            for scenario in scenarios:

                combination_results.append(
                    run_scenario_across_packages(
                        scenario,
                        packages,
                    )
                )

    if args.combination:

        combination_selection = select_products(
            products,
            ",".join(
                args.combination
            ),
        )

        adhoc_items = [
            {
                "product": product,
                "quantity": amount,
                "note": "",
            }
            for product, amount in (
                combination_selection
            )
        ]

        print(
            "\nAd-hoc combinatie testen..."
        )

        combination_results.append(
            run_scenario_across_packages(
                {
                    "id": "adhoc",
                    "name": "Ad-hoc combinatie (--combination)",
                    "category": "adhoc",
                    "description": (
                        "Handmatig opgegeven via "
                        "--combination."
                    ),
                    "items": adhoc_items,
                },
                packages,
            )
        )

    save_json(
        output_dir
        / "combination_results.json",
        combination_results,
    )

    if not combination_results:

        print(
            "\n  ⚠ combination_results.json is LEEG "
            "(0 scenario's/combinaties getest)."
        )

    if scenario_problems:

        data_problems.extend(
            scenario_problems
        )

        save_json(
            output_dir / "data_problems.json",
            data_problems,
        )

    # ------------------------------------------------------------------
    # CONSOLE SUMMARY
    # ------------------------------------------------------------------

    total = len(
        all_results
    )

    pass_count = len(
        passes
    )

    fail_count = len(
        failures
    )

    print()
    print("=" * 70)
    print(" RESULTAAT")
    print("=" * 70)

    print(
        f"\nProducten:        "
        f"{len(selected):,}"
    )

    print(
        f"Verpakkingen:     "
        f"{len(packages):,}"
    )

    print(
        f"Tests:            "
        f"{total:,}"
    )

    print(
        f"PASS:             "
        f"{pass_count:,}"
    )

    print(
        f"FAIL:             "
        f"{fail_count:,}"
    )

    print(
        f"Pass percentage:  "
        f"{(
            pass_count / total * 100
        ) if total else 0:.1f}%"
    )

    print(
        "\nOutput:"
    )

    print(
        f"  ✓ {output_dir / 'all_results.json'}"
    )

    print(
        f"  ✓ {output_dir / 'passes.json'}"
    )

    print(
        f"  ✓ {output_dir / 'failures.json'}"
    )

    print(
        f"  ✓ {output_dir / 'recommendations.json'}"
    )

    print(
        f"  ✓ {output_dir / 'summary.json'}"
    )

    print(
        f"  ✓ {output_dir / 'data_problems.json'}"
    )

    scenarios_fit = sum(
        1
        for r in combination_results
        if r["fits_any_package"]
    )

    print(
        f"  {'✓' if combination_results else '⚠'} "
        f"{output_dir / 'combination_results.json'} "
        f"({len(combination_results)} scenario('s), "
        f"{scenarios_fit} passen ergens)"
    )

    print(
        "\nAnalyse uitvoeren met:"
    )

    print(
        "  python analyze_results.py --open"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
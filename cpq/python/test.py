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
        return Product(
            product_id=str(row["num"]),
            name=str(row["name"]),
            lengte=float(row["l"]),
            breedte=float(row["w"]),
            hoogte=float(row["h"]),
            gewicht=float(
                row.get("weight_g", 0) or 0
            ),
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
    id_to_name: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:

    """
    Zet de py3dbp bin_result.items (na packing) om naar
    een platte, JSON-vriendelijke lijst met per item de
    werkelijke positie (x, y, z) en de werkelijk gebruikte
    afmetingen ná rotatie — dit is de basis voor een 3D
    plaatsingstekening.

    Itemnamen zijn opgebouwd als "{product_id}#{index}"
    (zie test_products_together), zodat meerdere
    exemplaren van hetzelfde artikel uit elkaar te houden
    zijn.
    """

    id_to_name = id_to_name or {}

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
        product_id = raw_name.split("#")[0]

        placements.append(
            {
                "item_name": raw_name,
                "product_id": product_id,
                "product_name": id_to_name.get(
                    product_id,
                    product_id,
                ),
                "position": position,
                "dimensions": dimension,
                "rotation_type": item.rotation_type,
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

    for index, product in enumerate(
        products
    ):

        packer.add_item(
            Item(
                f"{product.product_id}#{index}",
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
            "fits": False,
            "status": "ERROR",
            "reason": "PACKING_ENGINE_ERROR",
            "reason_details": [
                str(exc)
            ],
        }

    id_to_name = {
        product.product_id: product.name
        for product in products
    }

    bin_result = packer.bins[0]

    unfitted = [
        item.name
        for item in bin_result.unfitted_items
    ]

    fitted = [
        item.name
        for item in bin_result.items
    ]

    total_volume = sum(
        product.volume
        for product in products
    )

    total_weight = sum(
        product.gewicht
        for product in products
    )

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
            id_to_name,
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

        "fitted_count": len(
            fitted
        ),

        "unfitted_count": len(
            unfitted
        ),
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
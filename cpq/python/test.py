#!/usr/bin/env python3
"""ServiceSets.com Packing Tester — alleen combinatie- en scenario-tests.

Data (lokaal of via GitHub):
    data/products.json
    data/package_dimensions.json
    data/combination_scenarios.json

Voorbeelden:
    python tester_combinaties.py
    python tester_combinaties.py --no-scenarios
    python tester_combinaties.py --scenarios mijn_scenarios.json
    python tester_combinaties.py --combination 3552520:6,3552528:1
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from py3dbp import Bin, Item, Packer
except ImportError:
    sys.exit(
        "De library 'py3dbp' is niet geïnstalleerd.\n\n"
        "Installeer met:\n"
        "    pip install py3dbp --break-system-packages"
    )

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/hd-exclusiva/ServiceSets.com/main/data/"
PRODUCTS_URL = GITHUB_RAW_BASE + "products.json"
PACKAGES_URL = GITHUB_RAW_BASE + "package_dimensions.json"
SCENARIOS_URL = GITHUB_RAW_BASE + "combination_scenarios.json"
DEFAULT_OUTPUT_DIR = Path("test_results")
DEFAULT_SCENARIOS_PATH = Path("data/combination_scenarios.json")


@dataclass
class Product:
    product_id: str
    name: str
    lengte: float
    breedte: float
    hoogte: float
    gewicht: float = 0.0
    stackable: bool = False
    stack_increment_h: Optional[float] = None
    foldable: bool = False
    folded_dimensions: Optional[List[Dict[str, float]]] = None


@dataclass
class Package:
    naam: str
    lengte: float
    breedte: float
    hoogte: float
    max_gewicht: Optional[float] = None

    @property
    def volume(self) -> float:
        return self.lengte * self.breedte * self.hoogte


@dataclass
class PackingUnit:
    item_id: str
    product_id: str
    product_name: str
    pack_l: float
    pack_w: float
    pack_h: float
    weight_g: float
    kind: str
    represented_count: int
    stack_unit_h: Optional[float] = None
    stack_increment_h: Optional[float] = None
    original_dimensions: Optional[Dict[str, float]] = None


def build_packing_units(products: List[Product]) -> List[PackingUnit]:
    groups: Dict[str, List[Product]] = {}
    for product in products:
        groups.setdefault(product.product_id, []).append(product)

    units: List[PackingUnit] = []
    for product_id, group in groups.items():
        product = group[0]
        count = len(group)

        if product.stackable and product.stack_increment_h is not None:
            effective_height = product.hoogte + (count - 1) * product.stack_increment_h
            units.append(PackingUnit(
                item_id=f"{product_id}#stack",
                product_id=product_id,
                product_name=product.name,
                pack_l=product.lengte,
                pack_w=product.breedte,
                pack_h=effective_height,
                weight_g=product.gewicht * count,
                kind="stack",
                represented_count=count,
                stack_unit_h=product.hoogte,
                stack_increment_h=product.stack_increment_h,
            ))
            continue

        if product.foldable and product.folded_dimensions:
            folded = min(product.folded_dimensions, key=lambda d: d["l"] * d["w"] * d["h"])
            for index in range(count):
                units.append(PackingUnit(
                    item_id=f"{product_id}#folded{index}",
                    product_id=product_id,
                    product_name=product.name,
                    pack_l=folded["l"],
                    pack_w=folded["w"],
                    pack_h=folded["h"],
                    weight_g=product.gewicht,
                    kind="folded",
                    represented_count=1,
                    original_dimensions={"l": product.lengte, "w": product.breedte, "h": product.hoogte},
                ))
            continue

        for index in range(count):
            units.append(PackingUnit(
                item_id=f"{product_id}#{index}",
                product_id=product_id,
                product_name=product.name,
                pack_l=product.lengte,
                pack_w=product.breedte,
                pack_h=product.hoogte,
                weight_g=product.gewicht,
                kind="normal",
                represented_count=1,
            ))
    return units


def load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def download_json(url: str) -> Any:
    print(f"  Download: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "ServiceSets-Packing-Tester/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Kan GitHub-data niet ophalen:\n{url}\n\nFout: {exc}") from exc


def unwrap_list(data: Any, possible_keys: List[str]) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in possible_keys:
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError("JSON bevat geen lijst met records.")


def detect_product(row: Dict[str, Any]) -> Product:
    required = ["num", "name", "l", "w", "h"]
    missing = [key for key in required if row.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Ontbrekende velden: {', '.join(missing)}")

    folded_dimensions = []
    for option in row.get("folded_dimensions") or []:
        if not isinstance(option, dict):
            continue
        try:
            folded_dimensions.append({"l": float(option["l"]), "w": float(option["w"]), "h": float(option["h"])})
        except (KeyError, TypeError, ValueError):
            continue

    try:
        stack_increment_h = row.get("stack_increment_h")
        return Product(
            product_id=str(row["num"]),
            name=str(row["name"]),
            lengte=float(row["l"]),
            breedte=float(row["w"]),
            hoogte=float(row["h"]),
            gewicht=float(row.get("weight_g", 0) or 0),
            stackable=bool(row.get("stackable", False)),
            stack_increment_h=float(stack_increment_h) if stack_increment_h is not None else None,
            foldable=bool(row.get("foldable", False)),
            folded_dimensions=folded_dimensions or None,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Ongeldige numerieke afmeting: {exc}") from exc


def load_products(data: Any) -> Tuple[List[Product], List[Dict[str, Any]]]:
    products, problems = [], []
    for index, row in enumerate(unwrap_list(data, ["products"]), start=1):
        try:
            if not isinstance(row, dict):
                raise ValueError("Record is geen object")
            product = detect_product(row)
            if min(product.lengte, product.breedte, product.hoogte) <= 0:
                raise ValueError("Afmetingen moeten groter dan 0 zijn")
            if product.gewicht < 0:
                raise ValueError("Gewicht mag niet negatief zijn")
            products.append(product)
        except Exception as exc:
            problems.append({"type": "INVALID_PRODUCT", "index": index, "error": str(exc), "record": row})
    return products, problems


def detect_package(row: Dict[str, Any]) -> Package:
    required = ["naam", "lengte_cm", "breedte_cm", "hoogte_cm"]
    missing = [key for key in required if row.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Ontbrekende velden: {', '.join(missing)}")
    try:
        max_gewicht = row.get("max_gewicht")
        package = Package(
            naam=str(row["naam"]),
            lengte=float(row["lengte_cm"]),
            breedte=float(row["breedte_cm"]),
            hoogte=float(row["hoogte_cm"]),
            max_gewicht=None if max_gewicht in (None, "") else float(max_gewicht),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Ongeldige verpakking: {exc}") from exc
    if min(package.lengte, package.breedte, package.hoogte) <= 0:
        raise ValueError("Afmetingen moeten groter dan 0 zijn")
    return package


def load_packages(data: Any) -> Tuple[List[Package], List[Dict[str, Any]]]:
    packages, problems = [], []
    for index, row in enumerate(unwrap_list(data, ["package_dimensions", "packages"]), start=1):
        try:
            if not isinstance(row, dict):
                raise ValueError("Record is geen object")
            packages.append(detect_package(row))
        except Exception as exc:
            problems.append({"type": "INVALID_PACKAGE", "index": index, "error": str(exc), "record": row})
    return packages, problems


def load_scenarios(data: Any, products: List[Product]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    lookup = {product.product_id: product for product in products}
    scenarios, problems = [], []

    for index, row in enumerate(unwrap_list(data, ["scenarios"]), start=1):
        if not isinstance(row, dict):
            problems.append({"type": "INVALID_SCENARIO", "index": index, "error": "Record is geen object", "record": row})
            continue
        scenario_id = row.get("id", f"scenario_{index}")
        if not isinstance(row.get("items"), list) or not row["items"]:
            problems.append({"type": "INVALID_SCENARIO", "index": index, "error": f"Scenario '{scenario_id}' heeft geen (geldige) items-lijst", "record": row})
            continue

        resolved_items, missing_products = [], []
        for item in row["items"]:
            if not isinstance(item, dict):
                continue
            product_id = str(item.get("product_id", ""))
            try:
                quantity = int(item.get("quantity", 1))
            except (TypeError, ValueError):
                quantity = 0
            product = lookup.get(product_id)
            if product is None or quantity <= 0:
                missing_products.append(product_id if product is None else f"{product_id} (ongeldig aantal: {item.get('quantity')})")
                continue
            resolved_items.append({"product": product, "quantity": quantity, "note": item.get("note", "")})

        if missing_products:
            problems.append({"type": "SCENARIO_MISSING_PRODUCTS", "index": index, "error": f"Scenario '{scenario_id}' verwijst naar onbekende of ongeldige producten", "record": missing_products})
        if resolved_items:
            scenarios.append({
                "id": scenario_id,
                "name": row.get("name", scenario_id),
                "category": row.get("category", ""),
                "description": row.get("description", ""),
                "items": resolved_items,
            })
    return scenarios, problems


def extract_placements(bin_result: Any, unit_by_item_id: Dict[str, PackingUnit]) -> List[Dict[str, Any]]:
    placements = []
    for item in bin_result.items:
        try:
            dimensions = [float(value) for value in item.get_dimension()]
        except AttributeError:
            dimensions = [float(item.width), float(item.height), float(item.depth)]
        try:
            position = [float(value) for value in item.position]
        except Exception:
            position = [0.0, 0.0, 0.0]

        unit = unit_by_item_id.get(str(item.name))
        if unit is None:
            continue
        placements.append({
            "item_name": str(item.name),
            "product_id": unit.product_id,
            "product_name": unit.product_name,
            "position": position,
            "dimensions": dimensions,
            "rotation_type": item.rotation_type,
            "kind": unit.kind,
            "represented_count": unit.represented_count,
            "stack_unit_h": unit.stack_unit_h,
            "stack_increment_h": unit.stack_increment_h,
            "original_dimensions": unit.original_dimensions,
        })
    return placements


def test_products_together(products: List[Product], package: Package) -> Dict[str, Any]:
    units = build_packing_units(products)
    packer = Packer()
    max_weight = package.max_gewicht if package.max_gewicht is not None else 1_000_000_000
    packer.add_bin(Bin(package.naam, package.lengte, package.breedte, package.hoogte, max_weight))
    for unit in units:
        packer.add_item(Item(unit.item_id, unit.pack_l, unit.pack_w, unit.pack_h, unit.weight_g))

    try:
        packer.pack(bigger_first=True, distribute_items=False, number_of_decimals=2)
    except Exception as exc:
        return {"fits": False, "status": "ERROR", "reason": "PACKING_ENGINE_ERROR", "reason_details": [str(exc)], "package": package.naam}

    unit_by_item_id = {unit.item_id: unit for unit in units}
    bin_result = packer.bins[0]
    unfitted = [str(item.name) for item in bin_result.unfitted_items]
    fitted = [str(item.name) for item in bin_result.items]
    fitted_units = [unit_by_item_id[name] for name in fitted if name in unit_by_item_id]
    unfitted_units = [unit_by_item_id[name] for name in unfitted if name in unit_by_item_id]
    total_volume = sum(unit.pack_l * unit.pack_w * unit.pack_h for unit in units)
    total_weight = sum(product.gewicht for product in products)
    stacked = [unit for unit in units if unit.kind == "stack"]
    folded = [unit for unit in units if unit.kind == "folded"]

    return {
        "fits": not unfitted,
        "status": "PASS" if not unfitted else "FAIL",
        "reason": None if not unfitted else "ITEMS_DID_NOT_ALL_FIT",
        "reason_details": {"unfitted_items": unfitted, "fitted_items": fitted},
        "placements": extract_placements(bin_result, unit_by_item_id),
        "package": package.naam,
        "package_dimensions_cm": {"lengte": package.lengte, "breedte": package.breedte, "hoogte": package.hoogte},
        "total_product_volume_cm3": round(total_volume, 2),
        "package_volume_cm3": round(package.volume, 2),
        "volume_pct": round(min(total_volume / package.volume * 100, 100.0), 1),
        "total_weight_g": round(total_weight, 2),
        "package_max_weight_g": package.max_gewicht,
        "number_of_products": len(products),
        "fitted_count": sum(unit.represented_count for unit in fitted_units),
        "unfitted_count": sum(unit.represented_count for unit in unfitted_units),
        "stacked_articles": {"count": len(stacked), "details": [
            {"product_id": unit.product_id, "product_name": unit.product_name, "stacked_count": unit.represented_count, "unit_height_cm": unit.stack_unit_h, "stack_increment_cm": unit.stack_increment_h, "effective_height_cm": unit.pack_h, "fits": unit.item_id in fitted}
            for unit in stacked
        ]},
        "folded_articles": {"count": len(folded), "details": [
            {"product_id": unit.product_id, "product_name": unit.product_name, "original_dimensions_cm": unit.original_dimensions, "folded_dimensions_cm": {"l": unit.pack_l, "w": unit.pack_w, "h": unit.pack_h}, "fits": unit.item_id in fitted}
            for unit in folded
        ]},
    }


def run_scenario_across_packages(scenario: Dict[str, Any], packages: List[Package]) -> Dict[str, Any]:
    products = [entry["product"] for entry in scenario["items"] for _ in range(entry["quantity"])]
    results = [test_products_together(products, package) for package in sorted(packages, key=lambda package: package.volume)]
    fitting = sorted((result for result in results if result["status"] == "PASS"), key=lambda result: result["package_volume_cm3"])
    items = [{"product_id": entry["product"].product_id, "product_name": entry["product"].name, "quantity": entry["quantity"], "note": entry["note"]} for entry in scenario["items"]]
    return {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "category": scenario["category"],
        "description": scenario["description"],
        "items": items,
        "distinct_articles": len(items),
        "total_quantity": sum(entry["quantity"] for entry in scenario["items"]),
        "fits_any_package": bool(fitting),
        "smallest_fitting_package": fitting[0]["package"] if fitting else None,
        "packages_that_fit": [result["package"] for result in fitting],
        "packages_that_do_not_fit": [result["package"] for result in results if result["status"] != "PASS"],
        "results_per_package": results,
    }


def select_products(products: List[Product], selection: str) -> List[Tuple[Product, int]]:
    lookup = {product.product_id: product for product in products}
    selected = []
    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue
        product_id, separator, raw_amount = part.partition(":")
        try:
            amount = int(raw_amount) if separator else 1
        except ValueError:
            print(f"⚠ Ongeldig aantal: {part}")
            continue
        product = lookup.get(product_id)
        if product is None:
            print(f"⚠ Product niet gevonden: {product_id}")
        elif amount <= 0:
            print(f"⚠ Aantal moet > 0 zijn: {part}")
        else:
            selected.append((product, amount))
    return selected


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test ServiceSets-combinaties tegen alle verpakkingen.")
    parser.add_argument("--products", help="Lokaal products.json; standaard wordt GitHub gebruikt.")
    parser.add_argument("--packages", help="Lokaal package_dimensions.json; standaard wordt GitHub gebruikt.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Outputmap; standaard: test_results")
    parser.add_argument("--combination", nargs="+", help="Test producten samen, bijvoorbeeld: 3552520:6,3552528:1")
    parser.add_argument("--scenarios", help="Lokaal combination_scenarios.json-bestand.")
    parser.add_argument("--no-scenarios", action="store_true", help="Sla de benoemde combinatie-scenario's over.")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print("\n" + "=" * 70 + "\n ServiceSets.com Combination Packing Tester\n" + "=" * 70)

    try:
        product_data = load_json_file(Path(args.products)) if args.products else download_json(PRODUCTS_URL)
        products, product_problems = load_products(product_data)
    except Exception as exc:
        sys.exit(f"\n❌ Productdata fout:\n{exc}")
    print(f"\nProducten geladen: {len(products):,}")

    try:
        package_data = load_json_file(Path(args.packages)) if args.packages else download_json(PACKAGES_URL)
        packages, package_problems = load_packages(package_data)
    except Exception as exc:
        sys.exit(f"\n❌ Verpakkingsdata fout:\n{exc}")
    print(f"Verpakkingen geladen: {len(packages):,}")

    data_problems = product_problems + package_problems
    all_results: List[Dict[str, Any]] = []

    if not args.no_scenarios:
        scenario_data, scenario_source = None, None
        candidates = [Path(args.scenarios)] if args.scenarios else [
            DEFAULT_SCENARIOS_PATH,
            Path("combination_scenarios.json"),
            Path(__file__).resolve().parent / "data" / "combination_scenarios.json",
            Path(__file__).resolve().parent / "combination_scenarios.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    scenario_data, scenario_source = load_json_file(candidate), str(candidate)
                    break
                except Exception as exc:
                    print(f"⚠ Kon {candidate} niet lezen: {exc}")
        if scenario_data is None:
            try:
                scenario_data, scenario_source = download_json(SCENARIOS_URL), SCENARIOS_URL
            except Exception as exc:
                print(f"⚠ Geen combinatie-scenario's geladen: {exc}")

        if scenario_data is not None:
            scenarios, scenario_problems = load_scenarios(scenario_data, products)
            data_problems.extend(scenario_problems)
            print(f"\nScenario-bron: {scenario_source}\nScenario's geladen: {len(scenarios)}")
            for scenario in scenarios:
                all_results.append(run_scenario_across_packages(scenario, packages))

    if args.combination:
        selected = select_products(products, ",".join(args.combination))
        if selected:
            all_results.append(run_scenario_across_packages({
                "id": "adhoc",
                "name": "Ad-hoc combinatie (--combination)",
                "category": "adhoc",
                "description": "Handmatig opgegeven via --combination.",
                "items": [{"product": product, "quantity": amount, "note": ""} for product, amount in selected],
            }, packages))

    save_json(output_dir / "data_problems.json", data_problems)
    save_json(output_dir / "all_results.json", all_results)

    fits = sum(1 for result in all_results if result["fits_any_package"])
    print("\n" + "=" * 70 + "\n RESULTAAT\n" + "=" * 70)
    print(f"\nCombinaties:      {len(all_results):,}")
    print(f"Passen ergens:    {fits:,}")
    print(f"\nOutput:\n  ✓ {output_dir / 'all_results.json'}\n  ✓ {output_dir / 'data_problems.json'}")
    print("=" * 70)


if __name__ == "__main__":
    main()

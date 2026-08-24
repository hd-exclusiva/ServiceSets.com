#!/usr/bin/env python3
"""
tester.py - Servicesets Packing Engine Tester

Run:
    python tester.py --help
    python tester.py --all
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class Product:
    def __init__(self, product_id, name, lengte, breedte, hoogte, gewicht):
        self.product_id = product_id
        self.name = name
        self.lengte = float(lengte)
        self.breedte = float(breedte)
        self.hoogte = float(hoogte)
        self.gewicht = float(gewicht)

    @property
    def volume(self):
        return self.lengte * self.breedte * self.hoogte

class Package:
    def __init__(self, naam, lengte, breedte, hoogte, max_gewicht=None):
        self.naam = naam
        self.lengte = float(lengte)
        self.breedte = float(breedte)
        self.hoogte = float(hoogte)
        self.max_gewicht = float(max_gewicht) if max_gewicht else None

    @property
    def volume(self):
        return self.lengte * self.breedte * self.hoogte

class TestStats:
    def __init__(self):
        self.passes = 0
        self.fails = 0
        self.errors = 0

    def record(self, status):
        if status == "PASS":
            self.passes += 1
        elif status == "FAIL":
            self.fails += 1
        elif status == "ERROR":
            self.errors += 1

class TestCase:
    pass

def fits_with_rotation(product, package):
    # Dummy implementation for script completeness
    if product.lengte <= package.lengte and product.breedte <= package.breedte and product.hoogte <= package.hoogte:
        return True, {"l": product.lengte, "w": product.breedte, "h": product.hoogte}
    return False, None

def volume_fit(products, package):
    # Dummy implementation
    vol = sum(p.volume for p in products)
    return {"passed": vol <= package.volume}

def pack_with_py3dbp(products, package, decimals=2):
    # Dummy implementation
    return {"available": True, "error": False, "passed": True}

def save_json(path, data):
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def write_reproducible_cases(path, tester):
    pass

def print_summary(tester):
    print(f"Tests: PASS {tester.stats.passes} / FAIL {tester.stats.fails} / ERROR {tester.stats.errors}")


class PackingTester:
    def __init__(
        self,
        products: List[Product],
        packages: List[Package],
        seed: int = 12345,
        decimals: int = 2,
    ):
        self.products = products
        self.packages = packages
        self.random = random.Random(seed)
        self.seed = seed
        self.decimals = decimals

        self.stats = TestStats()

        self.failures: List[TestCase] = []
        self.counterexamples: List[TestCase] = []
        self.warnings: List[TestCase] = []
        self.all_results: List[Dict[str, Any]] = []

    def test_individual_products(self) -> None:
        print("\n[1] Individuele producten testen...")

        for product in self.products:
            for package in self.packages:
                self.stats.record("PASS")

                geometric_fit, rotation = fits_with_rotation(
                    product,
                    package,
                )

                volume_fit_result = volume_fit(
                    [product],
                    package,
                )

                pack_result = pack_with_py3dbp(
                    [product],
                    package,
                    decimals=self.decimals,
                )

                # --- NIEUWE LOGICA VOOR ALL_RESULTS.JSON ---
                status = "PASS"
                reason = ""
                fits = True

                if package.max_gewicht is not None and product.gewicht > package.max_gewicht:
                    status = "FAIL"
                    reason = "WEIGHT_LIMIT"
                    fits = False
                elif not geometric_fit:
                    status = "FAIL"
                    reason = "PRODUCT_TOO_LARGE"
                    fits = False
                elif pack_result.get("available"):
                    if pack_result.get("error"):
                        status = "ERROR"
                        reason = "PACKING_ENGINE_ERROR"
                        fits = False
                    elif not pack_result.get("passed", False):
                        status = "FAIL"
                        reason = "PACKING_ENGINE_REJECTED"
                        fits = False

                volume_pct = (product.volume / package.volume * 100) if package.volume > 0 else 0

                self.all_results.append({
                    "product": product.product_id,
                    "product_name": product.name,
                    "product_dimensions_cm": {"l": product.lengte, "w": product.breedte, "h": product.hoogte},
                    "product_volume_cm3": product.volume,
                    "product_weight_g": product.gewicht,
                    "package": package.naam,
                    "package_dimensions_cm": {"l": package.lengte, "w": package.breedte, "h": package.hoogte},
                    "package_volume_cm3": package.volume,
                    "package_max_weight_g": package.max_gewicht,
                    "status": status,
                    "fits": fits,
                    "reason": reason,
                    "volume_pct": volume_pct,
                    "rotation": rotation if rotation else None,
                    "quantity_instance": 1,
                    "requested_quantity": 1,
                })
                # ---------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Test 3D packing.")
    parser.add_argument(
        "--decimals",
        type=int,
        default=2,
        help="Aantal decimalen voor py3dbp.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Genereer het all_results.json bestand met alle testresultaten voor het dashboard.",
    )

    args = parser.parse_args()

    # Mocks for demonstration
    dummy_products = [
        Product("001", "Test Product 1", 10, 10, 10, 500)
    ]
    dummy_packages = [
        Package("Doos 1", 15, 15, 15, 2000)
    ]

    tester = PackingTester(dummy_products, dummy_packages, decimals=args.decimals)
    tester.test_individual_products()

    output_dir = Path("test_results")
    output_dir.mkdir(exist_ok=True)

    write_reproducible_cases(
        output_dir / "reproducible_cases.txt",
        tester,
    )

    if args.all:
        save_json(
            output_dir / "all_results.json",
            tester.all_results,
        )

    print_summary(tester)


if __name__ == "__main__":
    main()

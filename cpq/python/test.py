
#!/usr/bin/env python3
"""
tester.py
=========
Automatische diagnose/tester voor de verpakkingslogica van ServiceSets.com.

De tool haalt standaard de actuele data rechtstreeks uit GitHub:

    https://github.com/hd-exclusiva/ServiceSets.com

Bestanden:
    data/products.json
    data/package_dimensions.json

Installatie:
    pip install py3dbp

Gebruik:
    python tester.py
    python tester.py --quick
    python tester.py --deep
    python tester.py --combinations 500
    python tester.py --seed 12345

Rapporten:
    test_results/summary.json
    test_results/data_problems.json
    test_results/failures.json
    test_results/counterexamples.json
    test_results/reproducible_cases.txt
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.request import Request, urlopen


# ============================================================================
# CONFIGURATIE
# ============================================================================

REPO_RAW = (
    "https://raw.githubusercontent.com/"
    "hd-exclusiva/ServiceSets.com/main/data"
)

PRODUCTS_URL = f"{REPO_RAW}/products.json"
PACKAGES_URL = f"{REPO_RAW}/package_dimensions.json"

DEFAULT_OUTPUT_DIR = Path("test_results")

try:
    from py3dbp import Packer, Bin, Item
except ImportError:
    Packer = None
    Bin = None
    Item = None


# ============================================================================
# DATAMODELLEN
# ============================================================================

@dataclass
class Product:
    product_id: str
    name: str
    lengte: float
    breedte: float
    hoogte: float
    gewicht: float = 0.0
    stackable: bool = False
    stack_increment_h: float = 0.0
    foldable: bool = False
    folded_dimensions: Optional[List[Tuple[float, float, float]]] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def volume(self) -> float:
        return self.lengte * self.breedte * self.hoogte

    @property
    def dimensions(self) -> Tuple[float, float, float]:
        return self.lengte, self.breedte, self.hoogte

    @property
    def behavior(self) -> str:
        if self.foldable and self.folded_dimensions:
            return "foldable"
        if self.stackable:
            return "stackable"
        return "rigid"


@dataclass
class Package:
    naam: str
    lengte: float
    breedte: float
    hoogte: float
    max_gewicht: Optional[float] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def volume(self) -> float:
        return self.lengte * self.breedte * self.hoogte

    @property
    def dimensions(self) -> Tuple[float, float, float]:
        return self.lengte, self.breedte, self.hoogte


@dataclass
class TestCase:
    case_id: str
    category: str
    product_ids: List[str]
    package: str
    quantity: Dict[str, int]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestStats:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    warnings: int = 0
    errors: int = 0

    def record(self, result: str) -> None:
        self.total += 1
        if result == "PASS":
            self.passed += 1
        elif result == "FAIL":
            self.failed += 1
        elif result == "SKIP":
            self.skipped += 1
        elif result == "WARNING":
            self.warnings += 1
        elif result == "ERROR":
            self.errors += 1


# ============================================================================
# JSON / HTTP
# ============================================================================

def download_json(url: str, timeout: int = 30) -> Any:
    """Download JSON from GitHub Raw."""
    request = Request(
        url,
        headers={
            "User-Agent": "ServiceSets-Packing-Tester/1.0",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        content = response.read()

    return json.loads(content.decode("utf-8"))


def unwrap_list(data: Any, preferred_keys: Sequence[str]) -> List[Dict[str, Any]]:
    """
    Ondersteunt zowel:

        [...]
    
    als:

        {"products": [...]}

    en:

        {"package_dimensions": [...]}
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in preferred_keys:
            value = data.get(key)
            if isinstance(value, list):
                return value

        # Fallback: zoek eerste list met dicts.
        for value in data.values():
            if isinstance(value, list) and all(
                isinstance(x, dict) for x in value
            ):
                return value

    raise ValueError("Kon geen lijst met records vinden in JSON.")


# ============================================================================
# FLEXIBELE VELDHERKENNING
# ============================================================================

def first_value(
    row: Dict[str, Any],
    candidates: Sequence[str],
    default: Any = None,
) -> Any:
    for key in candidates:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default

    if isinstance(value, bool):
        return float(value)

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return default


def to_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "": return default
    if isinstance(value, bool): return value
    if isinstance(value, (int, float)): return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "ja", "y", "on"}


def parse_folded_dimensions(row: Dict[str, Any]) -> Optional[List[Tuple[float, float, float]]]:
    raw = row.get("folded_dimensions")
    if isinstance(raw, dict): raw = [raw]
    candidates = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            l=first_value(item,["l","lengte","lengte_cm","length","length_cm"]); w=first_value(item,["w","breedte","breedte_cm","width","width_cm"]); h=first_value(item,["h","hoogte","hoogte_cm","height","height_cm"])
            if None not in (l,w,h):
                dims=(to_float(l),to_float(w),to_float(h))
                if all(x>0 for x in dims): candidates.append(dims)
        elif isinstance(item,(list,tuple)) and len(item)==3:
            dims=tuple(to_float(x) for x in item)
            if all(x>0 for x in dims): candidates.append(dims)
    l=first_value(row,["folded_l","folded_lengte","folded_length","folded_length_cm"]); w=first_value(row,["folded_w","folded_breedte","folded_width","folded_width_cm"]); h=first_value(row,["folded_h","folded_hoogte","folded_height","folded_height_cm"])
    if None not in (l,w,h):
        dims=(to_float(l),to_float(w),to_float(h))
        if all(x>0 for x in dims): candidates.append(dims)
    return candidates or None


def effective_dimensions(product: Product, quantity: int = 1) -> Tuple[Tuple[float,float,float], Dict[str,Any]]:
    quantity=max(1,int(quantity))
    if product.foldable and product.folded_dimensions:
        dims=min(product.folded_dimensions,key=lambda d:d[0]*d[1]*d[2])
        return dims,{"mode":"foldable","quantity":quantity,"original_dimensions_cm":list(product.dimensions),"effective_dimensions_cm":list(dims),"folded_options_cm":[list(x) for x in product.folded_dimensions]}
    if product.stackable and quantity>1:
        inc=max(0.0,product.stack_increment_h); dims=(product.lengte,product.breedte,product.hoogte+(quantity-1)*inc)
        return dims,{"mode":"stacked","quantity":quantity,"original_dimensions_cm":list(product.dimensions),"effective_dimensions_cm":list(dims),"stack_increment_h_cm":inc}
    return product.dimensions,{"mode":"rigid","quantity":quantity,"original_dimensions_cm":list(product.dimensions),"effective_dimensions_cm":list(product.dimensions)}


def effective_volume(product: Product, quantity: int = 1) -> float:
    dims,_=effective_dimensions(product,quantity); return dims[0]*dims[1]*dims[2]


def pack_units_from_products(products: Sequence[Product]):
    grouped={}; order=[]
    for product in products:
        if product.product_id not in grouped: grouped[product.product_id]=(product,0); order.append(product.product_id)
        p,q=grouped[product.product_id]; grouped[product.product_id]=(p,q+1)
    units=[]
    for pid in order:
        product,quantity=grouped[pid]; dims,meta=effective_dimensions(product,quantity); units.append((product,quantity,dims,meta))
    return units


def detect_product(row: Dict[str, Any], index: int) -> Product:
    product_id = first_value(
        row,
        [
            "artikelnummer",
            "product_id",
            "productnummer",
            "id",
            "sku",
            "code",
            "num",
        ],
        default=f"ROW-{index}",
    )

    name = first_value(
        row,
        [
            "artikelnaam",
            "productnaam",
            "name",
            "naam",
            "title",
        ],
        default=str(product_id),
    )

    lengte = to_float(
        first_value(
            row,
            [
                "lengte",
                "lengte_cm",
                "length",
                "l",
                "product_length_cm",
            ],
        )
    )

    breedte = to_float(
        first_value(
            row,
            [
                "breedte",
                "breedte_cm",
                "w",
                "width_cm",
                "product_width_cm",
            ],
        )
    )

    hoogte = to_float(
        first_value(
            row,
            [
                "hoogte",
                "h",
                "height",
                "height_cm",
                "product_height_cm",
            ],
        )
    )

    gewicht = to_float(
        first_value(
            row,
            [
                "gewicht",
                "gewicht_g",
                "weight",
                "weight_g",
                "product_weight_g",
            ],
        ),
        default=0.0,
    )

    return Product(
        product_id=str(product_id),
        name=str(name),
        lengte=lengte,
        breedte=breedte,
        hoogte=hoogte,
        gewicht=gewicht,
        stackable=to_bool(row.get("stackable", False)),
        stack_increment_h=to_float(first_value(row, ["stack_increment_h", "stack_increment_h_cm", "stapel_increment_h"]), default=0.0),
        foldable=to_bool(row.get("foldable", False)),
        folded_dimensions=parse_folded_dimensions(row),
        raw=row,
    )


def detect_package(row: Dict[str, Any], index: int) -> Package:
    naam = first_value(
        row,
        [
            "naam",
            "name",
            "package_name",
            "verpakking",
            "id",
        ],
        default=f"PACKAGE-{index}",
    )

    lengte = to_float(
        first_value(
            row,
            [
                "lengte",
                "lengte_cm",
                "length",
                "length_cm",
            ],
        )
    )

    breedte = to_float(
        first_value(
            row,
            [
                "breedte",
                "breedte_cm",
                "width",
                "width_cm",
            ],
        )
    )

    hoogte = to_float(
        first_value(
            row,
            [
                "hoogte",
                "hoogte_cm",
                "height",
                "height_cm",
            ],
        )
    )

    max_gewicht_raw = first_value(
        row,
        [
            "max_gewicht",
            "max_gewicht_g",
            "max_weight",
            "max_weight_g",
            "maximum_weight",
        ],
        default=None,
    )

    max_gewicht = (
        None
        if max_gewicht_raw in (None, "")
        else to_float(max_gewicht_raw)
    )

    return Package(
        naam=str(naam),
        lengte=lengte,
        breedte=breedte,
        hoogte=hoogte,
        max_gewicht=max_gewicht,
        raw=row,
    )


# ============================================================================
# GEOMETRIE
# ============================================================================

def unique_rotations(
    dimensions: Tuple[float, float, float]
) -> List[Tuple[float, float, float]]:
    """
    Alle unieke oriëntaties van een rechthoekig blok.
    """
    return list(set(itertools.permutations(dimensions, 3)))


def fits_with_rotation(
    product: Product,
    package: Package,
    tolerance: float = 1e-9,
) -> Tuple[bool, Optional[Tuple[float, float, float]]]:
    """
    Pure geometrische test.

    Dit is bewust onafhankelijk van py3dbp.
    """
    box = package.dimensions

    for rotation in unique_rotations(product.dimensions):
        if all(
            rotation[i] <= box[i] + tolerance
            for i in range(3)
        ):
            return True, rotation

    return False, None


def volume_fit(products: Sequence[Product], package: Package) -> bool:
    total = sum(p.volume for p in products)
    return total <= package.volume + 1e-9


# ============================================================================
# PY3DBP
# ============================================================================

def py3dbp_available() -> bool:
    return Packer is not None


def pack_with_py3dbp(
    products: Sequence[Product],
    package: Package,
    decimals: int = 2,
) -> Dict[str, Any]:
    """
    Test een combinatie met py3dbp.

    Retourneert een uitgebreid diagnose-object.
    """
    if not py3dbp_available():
        return {
            "available": False,
            "error": "py3dbp is niet geïnstalleerd.",
        }

    packer = Packer()

    # py3dbp verwacht een maximumgewicht.
    # Wanneer er geen maximumgewicht in de data staat,
    # gebruiken we een zeer hoge waarde.
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

    for index, (product, quantity, dims, behavior) in enumerate(pack_units_from_products(products)):
        packer.add_item(
            Item(f"{product.product_id}#{index}", dims[0], dims[1], dims[2], product.gewicht * quantity)
        )

    try:
        packer.pack(
            bigger_first=True,
            distribute_items=False,
            number_of_decimals=decimals,
        )
    except Exception as exc:
        return {
            "available": True,
            "error": repr(exc),
        }

    bin_result = packer.bins[0]

    fitted = [
        getattr(item, "name", str(item))
        for item in bin_result.items
    ]

    unfitted = [
        getattr(item, "name", str(item))
        for item in bin_result.unfitted_items
    ]

    units = pack_units_from_products(products)
    return {
        "available": True, "passed": len(unfitted) == 0,
        "fitted": fitted, "unfitted": unfitted,
        "fitted_count": len(fitted), "unfitted_count": len(unfitted),
        "packing_units": [{"product_id": p.product_id, "product_name": p.name, "quantity": q, "behavior": meta["mode"], **meta} for p,q,dims,meta in units],
    }


# ============================================================================
# DATA VALIDATIE
# ============================================================================

def validate_products(products: Sequence[Product]) -> List[Dict[str, Any]]:
    problems: List[Dict[str, Any]] = []

    seen: Dict[str, int] = {}

    for product in products:
        seen[product.product_id] = seen.get(product.product_id, 0) + 1

        dimensions = product.dimensions

        if any(math.isnan(x) for x in dimensions):
            problems.append({
                "type": "NAN_DIMENSION",
                "product": product.product_id,
                "dimensions": dimensions,
            })

        if any(math.isinf(x) for x in dimensions):
            problems.append({
                "type": "INFINITE_DIMENSION",
                "product": product.product_id,
                "dimensions": dimensions,
            })

        if any(x < 0 for x in dimensions):
            problems.append({
                "type": "NEGATIVE_DIMENSION",
                "product": product.product_id,
                "dimensions": dimensions,
            })

        if any(x == 0 for x in dimensions):
            problems.append({
                "type": "ZERO_DIMENSION",
                "product": product.product_id,
                "dimensions": dimensions,
            })

        if product.gewicht < 0:
            problems.append({
                "type": "NEGATIVE_WEIGHT",
                "product": product.product_id,
                "weight": product.gewicht,
            })

        if product.stackable and product.stack_increment_h < 0:
            problems.append({"type":"NEGATIVE_STACK_INCREMENT","product":product.product_id,"stack_increment_h":product.stack_increment_h})
        if product.foldable and not product.folded_dimensions:
            problems.append({"type":"FOLDABLE_WITHOUT_FOLDED_DIMENSIONS","product":product.product_id,"message":"foldable=true maar geen folded_dimensions/folded_l/w/h opgegeven."})
        for dims in product.folded_dimensions or []:
            if any(x <= 0 for x in dims): problems.append({"type":"INVALID_FOLDED_DIMENSION","product":product.product_id,"dimensions":dims})

    for product_id, count in seen.items():
        if count > 1:
            problems.append({
                "type": "DUPLICATE_PRODUCT_ID",
                "product": product_id,
                "count": count,
            })

    return problems


def validate_packages(packages: Sequence[Package]) -> List[Dict[str, Any]]:
    problems: List[Dict[str, Any]] = []

    seen: Dict[str, int] = {}

    for package in packages:
        seen[package.naam] = seen.get(package.naam, 0) + 1

        dimensions = package.dimensions

        if any(math.isnan(x) for x in dimensions):
            problems.append({
                "type": "NAN_DIMENSION",
                "package": package.naam,
                "dimensions": dimensions,
            })

        if any(math.isinf(x) for x in dimensions):
            problems.append({
                "type": "INFINITE_DIMENSION",
                "package": package.naam,
                "dimensions": dimensions,
            })

        if any(x < 0 for x in dimensions):
            problems.append({
                "type": "NEGATIVE_DIMENSION",
                "package": package.naam,
                "dimensions": dimensions,
            })

        if any(x == 0 for x in dimensions):
            problems.append({
                "type": "ZERO_DIMENSION",
                "package": package.naam,
                "dimensions": dimensions,
            })

        if (
            package.max_gewicht is not None
            and package.max_gewicht < 0
        ):
            problems.append({
                "type": "NEGATIVE_MAX_WEIGHT",
                "package": package.naam,
                "max_weight": package.max_gewicht,
            })

    for name, count in seen.items():
        if count > 1:
            problems.append({
                "type": "DUPLICATE_PACKAGE_NAME",
                "package": name,
                "count": count,
            })

    return problems


# ============================================================================
# TEST ENGINE
# ============================================================================

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

    # ------------------------------------------------------------------
    # individuele producttests
    # ------------------------------------------------------------------

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

                if not geometric_fit:
                    if volume_fit_result:
                        self.counterexamples.append(
                            TestCase(
                                case_id=self.make_case_id(),
                                category="VOLUME_BUT_GEOMETRY_FAIL",
                                product_ids=[product.product_id],
                                package=package.naam,
                                quantity={product.product_id: 1},
                                message=(
                                    "Volume zegt PASS, maar geen enkele "
                                    "oriëntatie past."
                                ),
                                details={
                                    "product_dimensions": product.dimensions,
                                    "package_dimensions": package.dimensions,
                                    "product_volume": product.volume,
                                    "package_volume": package.volume,
                                },
                            )
                        )

                if pack_result.get("available") and not pack_result.get(
                    "passed",
                    False,
                ):
                    self.failures.append(
                        TestCase(
                            case_id=self.make_case_id(),
                            category="SINGLE_PRODUCT_PY3DBP_FAIL",
                            product_ids=[product.product_id],
                            package=package.naam,
                            quantity={product.product_id: 1},
                            message="Product past niet volgens py3dbp.",
                            details={
                                "geometric_fit": geometric_fit,
                                "rotation": rotation,
                                "volume_fit": volume_fit_result,
                                "py3dbp": pack_result,
                            },
                        )
                    )

    # ------------------------------------------------------------------
    # aantalstests
    # ------------------------------------------------------------------

    def test_quantities(self, max_quantity: int = 5) -> None:
        print(
            f"\n[2] Aantallen 1..{max_quantity} testen..."
        )

        for product in self.products:
            for package in self.packages:
                previous_pass = True

                for quantity in range(1, max_quantity + 1):
                    products = [product] * quantity

                    pack_result = pack_with_py3dbp(
                        products,
                        package,
                        decimals=self.decimals,
                    )

                    if not pack_result.get("available"):
                        continue

                    passed = bool(pack_result.get("passed"))

                    if not passed and previous_pass:
                        self.warnings.append(
                            TestCase(
                                case_id=self.make_case_id(),
                                category="CAPACITY_THRESHOLD",
                                product_ids=[product.product_id],
                                package=package.naam,
                                quantity={product.product_id: quantity},
                                message=(
                                    f"{quantity - 1} exemplaar(s) passen, "
                                    f"{quantity} niet."
                                ),
                                details={
                                    "previous_quantity": quantity - 1,
                                    "current_quantity": quantity,
                                    "py3dbp": pack_result,
                                },
                            )
                        )

                    previous_pass = passed

    # ------------------------------------------------------------------
    # gewicht
    # ------------------------------------------------------------------

    def test_weights(self) -> None:
        print("\n[3] Gewichtsbeperkingen testen...")

        packages_with_weight = [
            p
            for p in self.packages
            if p.max_gewicht is not None
        ]

        if not packages_with_weight:
            print("    Geen verpakkingen met max_gewicht gevonden.")
            return

        for package in packages_with_weight:
            for product in self.products:
                if product.gewicht <= 0:
                    continue

                if product.gewicht > package.max_gewicht:
                    self.failures.append(
                        TestCase(
                            case_id=self.make_case_id(),
                            category="WEIGHT_LIMIT",
                            product_ids=[product.product_id],
                            package=package.naam,
                            quantity={product.product_id: 1},
                            message=(
                                "Productgewicht overschrijdt "
                                "maximaal verpakkingsgewicht."
                            ),
                            details={
                                "product_weight": product.gewicht,
                                "max_weight": package.max_gewicht,
                            },
                        )
                    )

    # ------------------------------------------------------------------
    # willekeurige combinaties
    # ------------------------------------------------------------------

    def generate_random_combination(
        self,
        max_items: int = 5,
    ) -> List[Product]:
        if not self.products:
            return []

        count = self.random.randint(2, max_items)

        return [
            self.random.choice(self.products)
            for _ in range(count)
        ]

    def test_random_combinations(
        self,
        number_of_combinations: int = 250,
        max_items: int = 5,
    ) -> None:
        print(
            f"\n[4] {number_of_combinations} willekeurige "
            "combinaties testen..."
        )

        if not self.products or not self.packages:
            return

        for _ in range(number_of_combinations):
            products = self.generate_random_combination(max_items)

            package = self.random.choice(self.packages)

            volume_pass = volume_fit(products, package)

            geometric_pass = all(
                fits_with_rotation(product, package)[0]
                for product in products
            )

            py_result = pack_with_py3dbp(
                products,
                package,
                decimals=self.decimals,
            )

            if not py_result.get("available"):
                continue

            py_pass = bool(py_result.get("passed"))

            product_ids = [p.product_id for p in products]

            quantities: Dict[str, int] = {}
            for product in products:
                quantities[product.product_id] = (
                    quantities.get(product.product_id, 0) + 1
                )

            # Volume PASS maar py3dbp FAIL.
            if volume_pass and not py_pass:
                self.counterexamples.append(
                    TestCase(
                        case_id=self.make_case_id(),
                        category="VOLUME_PASS_PY3DBP_FAIL",
                        product_ids=product_ids,
                        package=package.naam,
                        quantity=quantities,
                        message=(
                            "Totaal volume past in de verpakking, "
                            "maar de 3D-packer krijgt niet alles geplaatst."
                        ),
                        details={
                            "volume_pass": volume_pass,
                            "geometric_individual_pass": geometric_pass,
                            "py3dbp": py_result,
                            "total_product_volume": sum(
                                p.volume for p in products
                            ),
                            "package_volume": package.volume,
                        },
                    )
                )

            # Pure geometrie zegt PASS maar py3dbp FAIL.
            if geometric_pass and not py_pass:
                self.counterexamples.append(
                    TestCase(
                        case_id=self.make_case_id(),
                        category="GEOMETRY_PASS_PY3DBP_FAIL",
                        product_ids=product_ids,
                        package=package.naam,
                        quantity=quantities,
                        message=(
                            "Alle individuele producten passen geometrisch, "
                            "maar de combinatie past niet."
                        ),
                        details={
                            "py3dbp": py_result,
                            "total_product_volume": sum(
                                p.volume for p in products
                            ),
                            "package_volume": package.volume,
                        },
                    )
                )

    # ------------------------------------------------------------------
    # volledige productparen
    # ------------------------------------------------------------------

    def test_product_pairs(
        self,
        limit: int = 1000,
    ) -> None:
        print("\n[5] Productparen testen...")

        pairs = list(itertools.combinations_with_replacement(
            self.products,
            2,
        ))

        if len(pairs) > limit:
            pairs = self.random.sample(pairs, limit)

        for a, b in pairs:
            for package in self.packages:
                products = [a, b]

                volume_pass = volume_fit(products, package)

                py_result = pack_with_py3dbp(
                    products,
                    package,
                    decimals=self.decimals,
                )

                if not py_result.get("available"):
                    continue

                py_pass = bool(py_result.get("passed"))

                if volume_pass and not py_pass:
                    quantities = {
                        a.product_id: 1,
                        b.product_id: (
                            2 if a.product_id == b.product_id else 1
                        ),
                    }

                    self.counterexamples.append(
                        TestCase(
                            case_id=self.make_case_id(),
                            category="PAIR_VOLUME_PASS_3DBP_FAIL",
                            product_ids=[
                                a.product_id,
                                b.product_id,
                            ],
                            package=package.naam,
                            quantity=quantities,
                            message=(
                                "Productpaar heeft voldoende volume, "
                                "maar kan niet worden geplaatst."
                            ),
                            details={
                                "py3dbp": py_result,
                                "volume_products": [
                                    a.volume,
                                    b.volume,
                                ],
                                "package_volume": package.volume,
                            },
                        )
                    )

    # ------------------------------------------------------------------
    # grensgevallen
    # ------------------------------------------------------------------

    def test_boundaries(self) -> None:
        print("\n[6] Grensgevallen testen...")

        for product in self.products:
            for package in self.packages:
                geometric, rotation = fits_with_rotation(
                    product,
                    package,
                )

                if geometric:
                    max_difference = max(
                        abs(rotation[i] - package.dimensions[i])
                        for i in range(3)
                    )

                    if max_difference < 0.01:
                        self.warnings.append(
                            TestCase(
                                case_id=self.make_case_id(),
                                category="BOUNDARY_DIMENSION",
                                product_ids=[product.product_id],
                                package=package.naam,
                                quantity={product.product_id: 1},
                                message=(
                                    "Productafmeting ligt zeer dicht "
                                    "bij verpakkingsafmeting."
                                ),
                                details={
                                    "rotation": rotation,
                                    "package_dimensions": package.dimensions,
                                    "difference": max_difference,
                                },
                            )
                        )

    # ------------------------------------------------------------------
    # reproduceerbare cases
    # ------------------------------------------------------------------

    def make_case_id(self) -> str:
        return f"CASE-{len(self.failures) + len(self.counterexamples) + len(self.warnings) + 1:05d}"

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(
        self,
        quick: bool = False,
        deep: bool = False,
        combinations: int = 250,
    ) -> None:
        self.test_individual_products()

        if quick:
            self.test_quantities(max_quantity=3)
            self.test_weights()
            self.test_boundaries()
            return

        self.test_quantities(
            max_quantity=10 if deep else 5
        )

        self.test_weights()

        self.test_random_combinations(
            number_of_combinations=(
                combinations * 5 if deep else combinations
            ),
            max_items=8 if deep else 5,
        )

        self.test_product_pairs(
            limit=5000 if deep else 1000,
        )

        self.test_boundaries()


# ============================================================================
# RAPPORTAGE
# ============================================================================

def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def case_to_dict(case: TestCase) -> Dict[str, Any]:
    return asdict(case)


def write_reproducible_cases(
    path: Path,
    tester: PackingTester,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    cases = (
        tester.failures
        + tester.counterexamples
        + tester.warnings
    )

    with path.open("w", encoding="utf-8") as f:
        f.write(
            "SERVICESETS PACKING TESTER\n"
            "===========================\n\n"
        )

        f.write(
            f"Random seed: {tester.seed}\n"
            f"Cases: {len(cases)}\n\n"
        )

        for case in cases:
            f.write("=" * 80 + "\n")
            f.write(f"{case.case_id}\n")
            f.write(f"Type: {case.category}\n")
            f.write(f"Package: {case.package}\n")
            f.write(
                "Products: "
                + ", ".join(case.product_ids)
                + "\n"
            )
            f.write(
                "Quantity: "
                + json.dumps(
                    case.quantity,
                    ensure_ascii=False,
                )
                + "\n"
            )
            f.write(f"Message: {case.message}\n")

            if case.details:
                f.write("\nDetails:\n")
                f.write(
                    json.dumps(
                        case.details,
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                f.write("\n")

            f.write("\n")


def print_summary(
    products: List[Product],
    packages: List[Package],
    data_problems: List[Dict[str, Any]],
    tester: PackingTester,
    duration: float,
) -> None:
    print("\n")
    print("=" * 72)
    print(" SERVICESETS PACKING DIAGNOSTIC REPORT")
    print("=" * 72)

    print(f"\nProducten:        {len(products)}")
    print(f"Verpakkingen:     {len(packages)}")
    print(f"Data-problemen:   {len(data_problems)}")

    print("\nTests:")
    print(f"  Counterexamples: {len(tester.counterexamples)}")
    print(f"  Failures:        {len(tester.failures)}")
    print(f"  Warnings:        {len(tester.warnings)}")

    print(f"\nDuur: {duration:.2f} seconden")

    if not py3dbp_available():
        print("\n⚠ py3dbp NIET geïnstalleerd.")
        print("  Installeer met:")
        print("  pip install py3dbp")

    if data_problems:
        print("\n⚠ DATA-PROBLEMEN")
        for problem in data_problems[:15]:
            print(
                "  - "
                + problem.get("type", "UNKNOWN")
                + ": "
                + json.dumps(
                    problem,
                    ensure_ascii=False,
                )
            )

        if len(data_problems) > 15:
            print(
                f"  ... en nog {len(data_problems) - 15}"
            )

    if tester.counterexamples:
        print("\n⚠ INTERESSANTE TEGENVOORBEELDEN")

        categories: Dict[str, int] = {}

        for case in tester.counterexamples:
            categories[case.category] = (
                categories.get(case.category, 0) + 1
            )

        for category, count in sorted(
            categories.items(),
            key=lambda x: (-x[1], x[0]),
        ):
            print(f"  - {category}: {count}")

    if tester.failures:
        print("\n❌ FAILURES")

        for case in tester.failures[:10]:
            print(
                f"  - {case.case_id}: "
                f"{case.category} - {case.message}"
            )

        if len(tester.failures) > 10:
            print(
                f"  ... en nog {len(tester.failures) - 10}"
            )

    print("\nRapporten staan in:")
    print("  test_results/")

    print("\nBelangrijkste bestanden:")
    print("  summary.json")
    print("  data_problems.json")
    print("  failures.json")
    print("  counterexamples.json")
    print("  reproducible_cases.txt")

    print("\n" + "=" * 72)


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Automatische diagnose- en stresstest voor "
            "ServiceSets 3D-verpakkingslogica."
        )
    )

    parser.add_argument(
        "--products-url",
        default=PRODUCTS_URL,
        help="URL van products.json",
    )

    parser.add_argument(
        "--packages-url",
        default=PACKAGES_URL,
        help="URL van package_dimensions.json",
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Map voor testresultaten.",
    )

    parser.add_argument(
        "--quick",
        action="store_true",
        help="Snelle testset.",
    )

    parser.add_argument(
        "--deep",
        action="store_true",
        help="Uitgebreide testset.",
    )

    parser.add_argument(
        "--combinations",
        type=int,
        default=250,
        help="Aantal random combinaties.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="Random seed voor reproduceerbare tests.",
    )

    parser.add_argument(
        "--decimals",
        type=int,
        default=2,
        help="Aantal decimalen voor py3dbp.",
    )

    args = parser.parse_args()

    output_dir = Path(args.output)

    print("=" * 72)
    print(" ServiceSets Packing Tester")
    print("=" * 72)

    print("\nData ophalen uit GitHub...")

    try:
        products_raw = download_json(args.products_url)
    except Exception as exc:
        sys.exit(
            f"Kan products.json niet ophalen:\n{exc}"
        )

    try:
        packages_raw = download_json(args.packages_url)
    except Exception as exc:
        sys.exit(
            f"Kan package_dimensions.json niet ophalen:\n{exc}"
        )

    try:
        product_rows = unwrap_list(
            products_raw,
            [
                "products",
                "artikelen",
                "articles",
            ],
        )

        package_rows = unwrap_list(
            packages_raw,
            [
                "package_dimensions",
                "packages",
                "verpakkingen",
            ],
        )
    except ValueError as exc:
        sys.exit(
            f"JSON-structuur wordt niet herkend:\n{exc}"
        )

    products = [
        detect_product(row, index)
        for index, row in enumerate(product_rows, start=1)
    ]

    packages = [
        detect_package(row, index)
        for index, row in enumerate(package_rows, start=1)
    ]

    print(f"  Producten gevonden:    {len(products)}")
    print(f"  Verpakkingen gevonden: {len(packages)}")

    print("\nData valideren...")

    data_problems = (
        validate_products(products)
        + validate_packages(packages)
    )

    tester = PackingTester(
        products=products,
        packages=packages,
        seed=args.seed,
        decimals=args.decimals,
    )

    start = time.perf_counter()

    try:
        tester.run(
            quick=args.quick,
            deep=args.deep,
            combinations=args.combinations,
        )
    except KeyboardInterrupt:
        print("\n\nTest onderbroken door gebruiker.")
    except Exception as exc:
        print(
            "\n❌ Onverwachte fout tijdens testen:"
        )
        print(f"   {type(exc).__name__}: {exc}")

        import traceback

        traceback.print_exc()

    duration = time.perf_counter() - start

    # ------------------------------------------------------------------
    # Rapporten
    # ------------------------------------------------------------------

    summary = {
        "repository": "hd-exclusiva/ServiceSets.com",
        "products_url": args.products_url,
        "packages_url": args.packages_url,
        "seed": args.seed,
        "decimals": args.decimals,
        "mode": (
            "deep"
            if args.deep
            else "quick"
            if args.quick
            else "normal"
        ),
        "products": len(products),
        "packages": len(packages),
        "data_problems": len(data_problems),
        "failures": len(tester.failures),
        "counterexamples": len(tester.counterexamples),
        "warnings": len(tester.warnings),
        "duration_seconds": round(duration, 3),
        "py3dbp_available": py3dbp_available(),
        "behavior": {"stackable_products": sum(1 for p in products if p.stackable), "foldable_products": sum(1 for p in products if p.foldable), "rigid_products": sum(1 for p in products if not p.stackable and not p.foldable)},
    }

    save_json(
        output_dir / "summary.json",
        summary,
    )

    save_json(
        output_dir / "data_problems.json",
        data_problems,
    )

    save_json(
        output_dir / "failures.json",
        [
            case_to_dict(case)
            for case in tester.failures
        ],
    )

    save_json(
        output_dir / "counterexamples.json",
        [
            case_to_dict(case)
            for case in tester.counterexamples
        ],
    )

    save_json(
        output_dir / "warnings.json",
        [
            case_to_dict(case)
            for case in tester.warnings
        ],
    )

    write_reproducible_cases(
        output_dir / "reproducible_cases.txt",
        tester,
    )

    print_summary(
        products,
        packages,
        data_problems,
        tester,
        duration,
    )


if __name__ == "__main__":
    main()
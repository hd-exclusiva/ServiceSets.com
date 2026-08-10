"""
Pure-Python 3D bin packing (guillotine, best-fit, 6 rotaties).

BEWUST GEEN externe dependencies (geen py3dbp, geen numpy) — dit bestand
moet ongewijzigd kunnen draaien in twee omgevingen:

  1. Lokaal via CPython (VS Code, `python3 test_cpq.py`)
  2. In de browser via Pyodide (WebAssembly) op GitHub Pages, waar geen
     pip/micropip-installatie van derde-partij packages nodig is.

Dit is dezelfde plek waar je later py3dbp voor in de plaats kunt zetten
als je toch de externe library wilt gebruiken voor lokale/offline runs —
de functiehandtekeningen (`pack_bin`, `select_box`) blijven dan gelijk.
"""

from itertools import permutations


def _orientations(l, w, h):
    """Alle unieke rotaties van een doos (max 6, minder bij gelijke zijden)."""
    seen = set()
    out = []
    for p in permutations([l, w, h]):
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def pack_bin(items, box):
    """
    items: lijst van dicts {"name": str, "l": float, "w": float, "h": float}
           (al uitgeklapt naar losse instanties — dus qty=1 per entry)
    box:   dict {"name": str, "l": float, "w": float, "h": float}

    Retourneert dict:
        fits: bool (past alles?)
        placements: lijst van geplaatste items met positie (x,y,z) en gebruikte oriëntatie (l,w,h)
        unplaced: items die niet meer pasten
        placed_count / total_count
    """
    free_spaces = [{"x": 0.0, "y": 0.0, "z": 0.0, "l": box["l"], "w": box["w"], "h": box["h"]}]
    placements = []
    unplaced = []

    sorted_items = sorted(items, key=lambda it: it["l"] * it["w"] * it["h"], reverse=True)

    for item in sorted_items:
        best = None
        for idx, sp in enumerate(free_spaces):
            for (il, iw, ih) in _orientations(item["l"], item["w"], item["h"]):
                if il <= sp["l"] + 1e-6 and iw <= sp["w"] + 1e-6 and ih <= sp["h"] + 1e-6:
                    waste = sp["l"] * sp["w"] * sp["h"] - il * iw * ih
                    if best is None or waste < best["waste"]:
                        best = {"space_idx": idx, "l": il, "w": iw, "h": ih, "waste": waste}

        if best is None:
            unplaced.append(item)
            continue

        sp = free_spaces[best["space_idx"]]
        placements.append({
            "name": item["name"],
            "x": sp["x"], "y": sp["y"], "z": sp["z"],
            "l": best["l"], "w": best["w"], "h": best["h"],
        })

        # guillotine split: tot 3 nieuwe vrije ruimtes uit de rest
        new_spaces = []
        if sp["l"] - best["l"] > 1e-6:
            new_spaces.append({"x": sp["x"] + best["l"], "y": sp["y"], "z": sp["z"],
                                "l": sp["l"] - best["l"], "w": sp["w"], "h": sp["h"]})
        if sp["w"] - best["w"] > 1e-6:
            new_spaces.append({"x": sp["x"], "y": sp["y"] + best["w"], "z": sp["z"],
                                "l": best["l"], "w": sp["w"] - best["w"], "h": sp["h"]})
        if sp["h"] - best["h"] > 1e-6:
            new_spaces.append({"x": sp["x"], "y": sp["y"], "z": sp["z"] + best["h"],
                                "l": best["l"], "w": best["w"], "h": sp["h"] - best["h"]})

        del free_spaces[best["space_idx"]]
        free_spaces.extend(new_spaces)

    return {
        "fits": len(unplaced) == 0,
        "placements": placements,
        "unplaced": unplaced,
        "placed_count": len(placements),
        "total_count": len(items),
    }


def select_box(items, candidate_boxes):
    """
    Probeert kandidaat-dozen van klein naar groot en geeft de eerste
    passende terug, plus alle tussenliggende pogingen (handig voor
    diagnose als niets past: welke kwam het dichtst?).
    """
    boxes_sorted = sorted(candidate_boxes, key=lambda b: b["l"] * b["w"] * b["h"])
    attempts = []
    for box in boxes_sorted:
        result = pack_bin(items, box)
        attempts.append({"box": box, "result": result})
        if result["fits"]:
            return {"chosen_box": box, "result": result, "attempts": attempts}
    return {"chosen_box": None, "result": None, "attempts": attempts}

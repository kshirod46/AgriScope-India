"""
Fertilizer bag + cost calculator.

Standard Indian agronomic bag-blending method:
  1. Use DAP to meet the P2O5 requirement (DAP also supplies some N).
  2. Subtract the N already supplied by DAP from the total N requirement,
     and supply the remainder from Urea.
  3. Use MOP to meet the K2O requirement.

This is the same method extension officers and farmer-advisory sites
(e.g. Dept. of Agriculture guides) use for translating an N-P2O5-K2O
recommendation into "how many bags do I actually buy". It is not a
statistical estimate -- it's a direct nutrient-balance calculation.
"""

from .fertilizer_reference import FERTILIZER_PRODUCTS

ACRE_TO_HECTARE = 0.404686


def compute_fertilizer_plan(n_kg_ha: float, p2o5_kg_ha: float, k2o_kg_ha: float,
                             area_value: float, area_unit: str = "acre"):
    """
    Returns a dict with per-hectare and per-area nutrient totals, the
    product quantities (Urea/DAP/MOP) needed, bags required, and total
    cost at current MRP.
    """
    area_ha = area_value * ACRE_TO_HECTARE if area_unit == "acre" else area_value

    total_N = n_kg_ha * area_ha
    total_P2O5 = p2o5_kg_ha * area_ha
    total_K2O = k2o_kg_ha * area_ha

    dap = FERTILIZER_PRODUCTS["DAP"]
    urea = FERTILIZER_PRODUCTS["Urea"]
    mop = FERTILIZER_PRODUCTS["MOP"]

    # Step 1: DAP supplies all P2O5
    dap_kg = total_P2O5 / dap["P2O5_pct"] if dap["P2O5_pct"] else 0.0
    n_from_dap = dap_kg * dap["N_pct"]

    # Step 2: remaining N from Urea (never negative)
    remaining_N = max(total_N - n_from_dap, 0.0)
    urea_kg = remaining_N / urea["N_pct"]

    # Step 3: MOP supplies all K2O
    mop_kg = total_K2O / mop["K2O_pct"] if mop["K2O_pct"] else 0.0

    def bags(kg, bag_kg):
        return kg / bag_kg

    def cost(kg, product):
        return (kg / product["bag_kg"]) * product["price_inr"]

    plan = {
        "area_ha": round(area_ha, 3),
        "area_display": f"{area_value} {area_unit}",
        "targets_per_ha": {"N": n_kg_ha, "P2O5": p2o5_kg_ha, "K2O": k2o_kg_ha},
        "totals_kg": {
            "N": round(total_N, 1), "P2O5": round(total_P2O5, 1), "K2O": round(total_K2O, 1)
        },
        "products": {
            "DAP": {
                "kg": round(dap_kg, 1),
                "bags": round(bags(dap_kg, dap["bag_kg"]), 2),
                "bag_kg": dap["bag_kg"],
                "cost_inr": round(cost(dap_kg, dap), 2),
            },
            "Urea": {
                "kg": round(urea_kg, 1),
                "bags": round(bags(urea_kg, urea["bag_kg"]), 2),
                "bag_kg": urea["bag_kg"],
                "cost_inr": round(cost(urea_kg, urea), 2),
            },
            "MOP": {
                "kg": round(mop_kg, 1),
                "bags": round(bags(mop_kg, mop["bag_kg"]), 2),
                "bag_kg": mop["bag_kg"],
                "cost_inr": round(cost(mop_kg, mop), 2),
            },
        },
    }
    plan["total_cost_inr"] = round(
        plan["products"]["DAP"]["cost_inr"]
        + plan["products"]["Urea"]["cost_inr"]
        + plan["products"]["MOP"]["cost_inr"], 2
    )
    plan["cost_per_ha_inr"] = round(plan["total_cost_inr"] / area_ha, 2) if area_ha else 0
    return plan

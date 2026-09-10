"""
Real-world fertilizer reference data for Odisha.

Every number in this file is sourced from a published agronomic or
government reference -- NOT model output, NOT invented. Where Odisha-
specific figures were not found in the time available, the general
ICAR national RDF is used and flagged as such (`source` field), so the
UI can tell the farmer/user which numbers are state-verified and which
are general guidelines to be refined with a local soil test.

Recommended doses are expressed in the standard Indian convention:
N : P2O5 : K2O  (kg per hectare), which is how OUAT/ICAR/CRRI publish
package-of-practice numbers -- this matches directly onto fertilizer
bag nutrient content (Urea/DAP/MOP are labelled in N/P2O5/K2O too).

Sources:
  [CRRI]  ICAR-Central Rice Research Institute, Cuttack -- FAQ,
          https://icar-crri.in/faq/  (accessed 2026-09)
  [OUAT]  Odisha University of Agriculture & Technology package-of-
          practice figures as cited in Garnayak & Mishra, "Effect of
          Nutrient Management ... Rice-Groundnut Cropping System in
          Coastal Odisha"
  [ICAR-NAT] General ICAR national Recommended Dose of Fertilizer,
          used where no Odisha-specific figure was found.

Fertilizer retail prices are the Govt of India statutory / NBS-scheme
MRP for 2025-26 / Kharif-Rabi 2026, sourced from:
  - Department of Fertilizers, Govt of India (fert.nic.in) - Urea MRP
  - DD News / PIB coverage of Rabi 2025-26 NBS rates - DAP, MOP, NPK
These are national MRPs (fertilizer is a centrally price-controlled
commodity in India, so state-level MRP variation is minimal / dealer
margin only). Refresh via the data.gov.in Fertilizer Availability &
Price API (needs a free API key) for a live feed -- see live_data.py.
"""

from dataclasses import dataclass


@dataclass
class FertDose:
    crop: str
    season: str          # Kharif / Rabi / Summer / General
    ecology: str          # e.g. "Rainfed upland", "Lowland irrigated", "Hybrid"
    N: float              # kg/ha
    P2O5: float           # kg/ha
    K2O: float            # kg/ha
    source: str
    note: str = ""


# --- Odisha / ICAR recommended doses (N-P2O5-K2O kg/ha) ---------------------
FERT_DOSES = [
    FertDose("Rice", "Kharif", "Rainfed upland", 40, 20, 20, "CRRI",
             "Unfavourable rainfed upland ecology"),
    FertDose("Rice", "Kharif", "Lowland irrigated", 60, 30, 30, "CRRI",
             "Standard irrigated Kharif paddy"),
    FertDose("Rice", "Rabi", "Irrigated", 80, 40, 40, "CRRI",
             "Rabi (dry season) irrigated rice"),
    FertDose("Rice", "General", "Hybrid variety", 100, 60, 60, "CRRI",
             "Hybrid rice, any season"),
    FertDose("Rice", "General", "Aromatic variety", 60, 30, 30, "CRRI",
             "Plus 25 kg/ha ZnSO4 recommended"),
    FertDose("Groundnut", "Kharif", "Rainfed", 20, 40, 40, "ICAR-NAT",
             "Legume: only a small starter N dose needed (rhizobium fixes rest); "
             "P & K matter most for pod filling"),
    FertDose("Maize", "Kharif", "Rainfed/Irrigated", 120, 60, 40, "ICAR-NAT",
             "General ICAR maize RDF -- refine with soil test"),
    FertDose("Maize", "Rabi", "Irrigated", 150, 75, 60, "ICAR-NAT",
             "Rabi maize needs a higher dose than Kharif"),
    FertDose("Arhar/Tur", "Kharif", "Rainfed", 20, 50, 30, "ICAR-NAT",
             "Pulse crop -- low N need"),
    FertDose("Sugarcane", "General", "Irrigated", 280, 90, 90, "ICAR-NAT",
             "Long-duration crop, applied in 3-4 split doses"),
    FertDose("Jute", "Kharif", "Rainfed", 60, 30, 30, "ICAR-NAT", ""),
    FertDose("Wheat", "Rabi", "Irrigated", 120, 60, 40, "ICAR-NAT", ""),
    FertDose("Urad", "Kharif", "Rainfed", 20, 40, 20, "ICAR-NAT", "Pulse crop"),
    FertDose("Horse-gram", "Rabi", "Rainfed", 15, 30, 20, "ICAR-NAT", "Pulse crop"),
    FertDose("Sesamum", "Kharif", "Rainfed", 40, 20, 20, "ICAR-NAT", ""),
    FertDose("Ragi", "Kharif", "Rainfed", 40, 20, 20, "ICAR-NAT", ""),
    FertDose("Potato", "Rabi", "Irrigated", 180, 80, 100, "ICAR-NAT",
             "Heavy K requirement for tuber quality"),
]

# Fallback used only if a crop truly has no entry above and no ICAR-NAT
# default is sensible to guess -- forces the UI to say "no verified
# recommendation available" rather than inventing one.
GENERIC_FALLBACK = None


# --- Fertilizer products: nutrient content + current MRP -------------------
# bag_kg = standard retail bag size, price_inr = govt-fixed/NBS MRP per bag
FERTILIZER_PRODUCTS = {
    "Urea": {
        "N_pct": 0.46, "P2O5_pct": 0.0, "K2O_pct": 0.0,
        "bag_kg": 45, "price_inr": 268,
        "source": "Dept. of Fertilizers, GoI (fert.nic.in) - statutory MRP",
    },
    "DAP": {
        "N_pct": 0.18, "P2O5_pct": 0.46, "K2O_pct": 0.0,
        "bag_kg": 50, "price_inr": 1350,
        "source": "GoI NBS scheme, Rabi 2025-26 held rate (unchanged into 2026)",
    },
    "MOP": {
        "N_pct": 0.0, "P2O5_pct": 0.0, "K2O_pct": 0.60,
        "bag_kg": 50, "price_inr": 1710.54,
        "source": "GoI NBS scheme average retail price, 2025-26",
    },
    "NPK 10:26:26": {
        "N_pct": 0.10, "P2O5_pct": 0.26, "K2O_pct": 0.26,
        "bag_kg": 50, "price_inr": 1814.82,
        "source": "GoI NBS scheme average retail price, 2025-26",
    },
    "NPK 12:32:16": {
        "N_pct": 0.12, "P2O5_pct": 0.32, "K2O_pct": 0.16,
        "bag_kg": 50, "price_inr": 1711.87,
        "source": "GoI NBS scheme average retail price, 2025-26",
    },
}

PRICE_LAST_VERIFIED = "2026-09 (web search of Dept. of Fertilizers / DD News coverage)"


def get_dose_options(crop: str):
    """Return all known FertDose entries for a crop (may differ by season/ecology)."""
    return [d for d in FERT_DOSES if d.crop.lower() == crop.lower()]


def list_known_crops():
    return sorted({d.crop for d in FERT_DOSES})

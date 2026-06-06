"""Project configuration for EV dynamic tariff optimization."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Dataset paths
# Raw data — see README for download instructions
ACN_XLSX = ROOT / "data" / "ACN" / "acndata_sessions.json.xlsx"
URBANEV_DIR = ROOT / "data" / "UrbanEV"

# Processed / output directories
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS_DIR = ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
MODELS_DIR = ROOT / "models"

# Pricing assumptions (INR/kWh baseline per problem statement)
BASELINE_TARIFF_INR = 15.0
ENERGY_COST_INR = 8.0  # procurement cost proxy for margin checks

# Optimized utilization thresholds (adjusted from 80/30 with justification in README)
SURGE_UTIL_THRESHOLD = 0.75   # surge when predicted util exceeds 75%
DISCOUNT_UTIL_THRESHOLD = 0.35  # discount when below 35%
MAX_SURGE_MULTIPLIER = 1.25   # cap at +25% vs baseline (not 2x)
MAX_DISCOUNT_MULTIPLIER = 0.85  # floor at -15%
MAX_TARIFF_CHANGE_PCT = 0.10  # max 10% change per interval (smooth pricing)

# Demand elasticity for customer response simulation (ACN)
PRICE_ELASTICITY = -0.35  # typical short-run EV charging elasticity range

# Train/test split
TEST_SIZE = 0.2
RANDOM_STATE = 42

"""Hardware lifecycle and fleet age analysis.

Analyzes the age distribution of the server fleet, identifies servers
past warranty or useful life, and estimates efficiency gains from
hardware refresh.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter

# Age buckets (upper bounds in months, exclusive).
_AGE_BUCKETS = {
    "under_12mo": 12,
    "12_to_36mo": 36,
    "36_to_60mo": 60,
}

# Threshold beyond which a server is considered past useful life.
_USEFUL_LIFE_MONTHS = 60

# Threshold beyond which a server becomes a refresh candidate.
_REFRESH_CANDIDATE_MONTHS = 48

# Assumed efficiency improvement factor for refreshed hardware.
# Newer hardware is approximately 30 % more efficient per watt.
_REFRESH_EFFICIENCY_GAIN = 0.30


def analyze_hardware_lifecycle(dc: DataCenter) -> dict:
    """Analyze server fleet age and refresh needs.

    Returns a dictionary with the following keys:

    - ``age_distribution`` -- dict mapping bucket labels to server counts:
      ``under_12mo``, ``12_to_36mo``, ``36_to_60mo``, ``over_60mo``
    - ``past_warranty_count`` -- servers whose age exceeds warranty length
    - ``past_warranty_pct`` -- past-warranty servers as a percentage
    - ``past_useful_life_count`` -- servers older than 60 months
    - ``refresh_candidates`` -- count of servers that are either older
      than 48 months **or** past their warranty period
    - ``estimated_refresh_savings_kwh`` -- estimated monthly kWh savings
      if refresh candidates were replaced with hardware that is 30 %
      more efficient
    """
    servers = dc.servers
    total = len(servers)

    if total == 0:
        return {
            "age_distribution": {
                "under_12mo": 0,
                "12_to_36mo": 0,
                "36_to_60mo": 0,
                "over_60mo": 0,
            },
            "past_warranty_count": 0,
            "past_warranty_pct": 0.0,
            "past_useful_life_count": 0,
            "refresh_candidates": 0,
            "estimated_refresh_savings_kwh": 0.0,
        }

    age_dist = {
        "under_12mo": 0,
        "12_to_36mo": 0,
        "36_to_60mo": 0,
        "over_60mo": 0,
    }

    past_warranty_count = 0
    past_useful_life_count = 0
    refresh_candidates_count = 0
    refresh_candidate_power_watts = 0.0

    for server in servers:
        age = server.age_months

        # Age bucket classification.
        if age < _AGE_BUCKETS["under_12mo"]:
            age_dist["under_12mo"] += 1
        elif age < _AGE_BUCKETS["12_to_36mo"]:
            age_dist["12_to_36mo"] += 1
        elif age < _AGE_BUCKETS["36_to_60mo"]:
            age_dist["36_to_60mo"] += 1
        else:
            age_dist["over_60mo"] += 1

        # Warranty check -- uses the computed property from the model.
        if server.is_past_warranty:
            past_warranty_count += 1

        # Useful life check.
        if age > _USEFUL_LIFE_MONTHS:
            past_useful_life_count += 1

        # Refresh candidate: age exceeds threshold or past warranty.
        if age > _REFRESH_CANDIDATE_MONTHS or server.is_past_warranty:
            refresh_candidates_count += 1
            refresh_candidate_power_watts += server.current_power_watts

    past_warranty_pct = (past_warranty_count / total) * 100

    # Estimated savings: refresh candidates consume 30 % less power
    # after replacement.  Convert watts to monthly kWh.
    saved_watts = refresh_candidate_power_watts * _REFRESH_EFFICIENCY_GAIN
    estimated_refresh_savings_kwh = saved_watts * 24 * 30 / 1000

    return {
        "age_distribution": age_dist,
        "past_warranty_count": past_warranty_count,
        "past_warranty_pct": round(past_warranty_pct, 2),
        "past_useful_life_count": past_useful_life_count,
        "refresh_candidates": refresh_candidates_count,
        "estimated_refresh_savings_kwh": round(estimated_refresh_savings_kwh, 2),
    }

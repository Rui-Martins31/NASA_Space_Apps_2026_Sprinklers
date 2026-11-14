"""HAR-12 applicability for the sensor inventory documented by Sprinklers."""

import numpy as np
import pandas as pd

from .common import require_columns


REASON = (
    "The documented dataset has continuous MODIS observations and NOAA-20 VIIRS "
    "from 2018. It does not contain the S-NPP 2012 sensor transition required "
    "for the proposed residual-step analysis."
)
COLUMNS = ["country", "scope", "status", "reason", "transition_year",
           "step_raw", "step_adjusted"]


def har12_residual_step(monthly: pd.DataFrame) -> pd.DataFrame:
    """Report HAR-12 as unavailable for the documented current sensor inventory.

    This is an applicability report, not a fitted segmented regression. No
    transition is inferred from the start of simultaneous sensor observations.
    A different transition requires an explicit scientific definition and a
    compatible source series before a numerical estimate can be implemented.
    """
    if monthly.empty:
        countries = []
    else:
        require_columns(monthly, ["country", "year", "month", "series"])
        keys = ["country", "year", "month", "series"]
        if monthly.duplicated(keys).any():
            raise ValueError(f"Duplicate monthly keys: {', '.join(keys)}")
        countries = monthly.country.drop_duplicates().astype("object").tolist()
        if "ALL" not in countries:
            countries.append("ALL")
    records = [
        [country, "global" if country == "ALL" else "country",
         "not_applicable", REASON, pd.NA, np.nan, np.nan]
        for country in countries
    ]
    result = pd.DataFrame(records, columns=COLUMNS)
    for column in ["country", "scope", "status", "reason"]:
        result[column] = result[column].astype("object")
    result["transition_year"] = result.transition_year.astype("Int64")
    result["step_raw"] = result.step_raw.astype("float64")
    result["step_adjusted"] = result.step_adjusted.astype("float64")
    return result.sort_values("country").reset_index(drop=True)

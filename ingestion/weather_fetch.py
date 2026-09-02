"""
Pulls daily ERA5 weather (temperature, precipitation, humidity, wind) per
field's bounding box from the Copernicus Climate Data Store.

Setup (one-time):
    pip install cdsapi
    Create an account at https://cds.climate.copernicus.eu, accept the
    ERA5 license, then create ~/.cdsapirc with:
        url: https://cds.climate.copernicus.eu/api
        key: <your-uid>:<your-api-key>

ERA5 is gridded at ~0.25 degrees (~28km) - one request per field's bounding
box is enough; you don't need per-field requests if fields are close together
(check FIELDS in ingestion/config.py and merge nearby fields' boxes to save
CDS queue time, which can be slow - a year of daily data typically takes
several minutes to a few hours to process, plan around that).

Run:
    python -m ingestion.weather_fetch
"""

import zipfile
from pathlib import Path

import cdsapi
import xarray as xr

from ingestion.config import END_DATE, FIELDS, RAW_DIR, START_DATE

WEATHER_DIR = RAW_DIR / "weather"


def _ensure_real_netcdf(path: Path) -> Path:
    """The new CDS API returns a ZIP archive even though the requested output
    filename ends in .nc (observed in practice - raw bytes start with the ZIP
    magic number PK\\x03\\x04, not HDF5/netCDF's). Worse, for this variable
    mix the zip contains TWO separate .nc files - one for instantaneous
    variables (temperature, dewpoint, wind) and one for accumulated variables
    (precipitation) - confirmed by inspecting a real response's
    zf.namelist(): ['data_stream-oper_stepType-instant.nc',
    'data_stream-oper_stepType-accum.nc']. Extracting only the first member
    silently drops precipitation. This merges all .nc members in the zip
    into one real netCDF file, replacing path's contents, so downstream code
    never needs to know any of this happened."""
    with open(path, "rb") as f:
        header = f.read(4)

    if header != b"PK\x03\x04":
        return path  # already real netCDF

    tmp_files = []
    try:
        with zipfile.ZipFile(path) as zf:
            nc_members = sorted(n for n in zf.namelist() if n.endswith(".nc"))
            if not nc_members:
                raise ValueError(f"{path} is a zip but contains no .nc file: {zf.namelist()}")

            datasets = []
            for i, member in enumerate(nc_members):
                tmp_path = path.with_name(f"{path.stem}.part{i}.tmp.nc")
                tmp_path.write_bytes(zf.read(member))
                tmp_files.append(tmp_path)
                datasets.append(xr.open_dataset(tmp_path))

        merged = xr.merge(datasets, compat="override", join="outer")
        if "valid_time" in merged.dims and "time" not in merged.dims:
            merged = merged.rename({"valid_time": "time"})
        merged.load()

        for ds in datasets:
            ds.close()

        merged.to_netcdf(path)
    finally:
        for tmp_path in tmp_files:
            tmp_path.unlink(missing_ok=True)

    return path

VARIABLES = [
    "2m_temperature",
    "total_precipitation",
    "2m_dewpoint_temperature",  # relative humidity is derived from this + temperature below
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
]


def _bbox_for_field(geometry: list, pad_deg: float = 0.2) -> list[float]:
    """Returns [north, west, south, east] padded around the field polygon,
    the format the CDS API expects. ERA5's native grid is ~0.25 degrees;
    a too-small pad (0.05 was tried first) can fail to straddle any grid
    point depending on alignment, which CDS reports as a MARS
    'non-empty area crop/mask' error - confirmed happening in practice for
    one of three fields even though the other two succeeded with 0.05.
    0.2 comfortably covers a full grid cell regardless of alignment."""
    lons = [pt[0] for ring in geometry for pt in ring]
    lats = [pt[1] for ring in geometry for pt in ring]
    return [max(lats) + pad_deg, min(lons) - pad_deg, min(lats) - pad_deg, max(lons) + pad_deg]


def fetch_era5_for_field(field: dict) -> list[Path]:
    """Submits one CDS request PER YEAR rather than one big multi-year
    request - a single request spanning several years easily exceeds CDS's
    per-request cost/size limit (hit in practice: '403 cost limits exceeded'
    on a 4-year, 4x-daily, 5-variable request). Splitting by year keeps each
    request small and reliable; results are merged back together in
    to_daily_csv()."""
    client = cdsapi.Client()
    bbox = _bbox_for_field(field["geometry"])

    years = range(int(START_DATE[:4]), int(END_DATE[:4]) + 1)
    out_paths = []

    for year in years:
        out_nc = WEATHER_DIR / f"{field['field_id']}_era5_{year}.nc"
        if out_nc.exists():
            print(f"  {out_nc.name} already downloaded, skipping")
            _ensure_real_netcdf(out_nc)
            out_paths.append(out_nc)
            continue

        print(f"  requesting {field['field_id']} / {year}...")
        client.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": "reanalysis",
                "variable": VARIABLES,
                "year": str(year),
                "month": [f"{m:02d}" for m in range(1, 13)],
                "day": [f"{d:02d}" for d in range(1, 32)],
                "time": ["00:00", "12:00"],  # 2x/day is enough for a daily mean, keeps requests small
                "area": bbox,
                "format": "netcdf",
            },
            str(out_nc),
        )
        _ensure_real_netcdf(out_nc)
        out_paths.append(out_nc)

    return out_paths


def to_daily_csv(nc_paths: list[Path], field_id: str) -> Path:
    # Opened + concatenated individually (rather than open_mfdataset) to avoid
    # needing dask as a dependency for what's only a handful of yearly files.
    datasets = [xr.open_dataset(p) for p in nc_paths]
    ds = xr.concat(datasets, dim="time") if len(datasets) > 1 else datasets[0]
    daily = ds.resample(time="1D").mean()

    df = daily.mean(dim=["latitude", "longitude"]).to_dataframe().reset_index()
    df["temp_c"] = df["t2m"] - 273.15

    # ERA5 `tp` at time t is precipitation ACCUMULATED OVER THE PRECEDING HOUR,
    # in metres. The resample above takes the MEAN of the day's sampled steps,
    # so `tp * 1000` is mm per HOUR, not per day - labelling that "precip_mm"
    # (as this did originally) understates rainfall by ~24x. Caught by sanity-
    # checking against climatology: it reported 54.6 mm/YEAR for Amritsar,
    # Punjab, whose real annual rainfall is ~600-700 mm, and it left
    # HarvestTimingEnv.RAIN_RISK_THRESHOLD_MM (25 mm) unreachable, silently
    # disabling the entire weather-risk term of the harvest optimisation.
    #
    # CAVEAT, do not present this as an exact daily total: VARIABLES is
    # requested at only 2 steps/day (00:00, 12:00 - see fetch_era5_for_field,
    # kept small to stay under CDS per-request cost limits), so scaling the
    # 2-sample mean to 24h is an ESTIMATE that misses the diurnal rainfall
    # cycle (monsoon rain skews to late afternoon/night). It restores the
    # right order of magnitude, not gauge-accurate totals. For publication-
    # grade rainfall, re-request ERA5 at hourly resolution and sum, or use a
    # daily-aggregated product.
    HOURS_PER_DAY = 24
    df["precip_mm"] = df["tp"] * 1000 * HOURS_PER_DAY

    # approximate relative humidity from dewpoint + temperature (Magnus formula)
    import numpy as np

    dewpoint_c = df["d2m"] - 273.15
    df["humidity_pct"] = 100 * (
        np.exp((17.625 * dewpoint_c) / (243.04 + dewpoint_c))
        / np.exp((17.625 * df["temp_c"]) / (243.04 + df["temp_c"]))
    )
    df["wind_speed_ms"] = np.sqrt(df["u10"] ** 2 + df["v10"] ** 2)

    out = df[["time", "temp_c", "precip_mm", "humidity_pct", "wind_speed_ms"]].rename(columns={"time": "date"})
    out_path = WEATHER_DIR / f"{field_id}_weather_daily.csv"
    out.to_csv(out_path, index=False)
    return out_path


def main():
    for field in FIELDS:
        print(f"Fetching ERA5 weather for {field['field_id']} ({field['name']})...")
        nc_paths = fetch_era5_for_field(field)
        csv_path = to_daily_csv(nc_paths, field["field_id"])
        print(f"  wrote daily weather -> {csv_path}")


if __name__ == "__main__":
    main()

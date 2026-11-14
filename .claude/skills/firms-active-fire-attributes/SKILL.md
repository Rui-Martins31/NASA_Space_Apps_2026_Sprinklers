---
name: firms-active-fire-attributes
description: "Explains the columns in NASA FIRMS MODIS and VIIRS active fire data. Use when reading, cleaning, harmonising, or analysing detections from annual country archives, CSV files, shapefiles, or the FIRMS API."
---

# NASA FIRMS active fire data attributes (MODIS and VIIRS)

## What a detection represents

Treat each row as a thermal anomaly detected in a pixel during a satellite overpass. The coordinates mark the centre of the pixel. One fire can produce several detections in different pixels or overpasses, and several small fires can fall within the same pixel.

| Attribute | MODIS | VIIRS |
| --- | --- | --- |
| Nominal resolution at nadir | About 1 km | About 375 m |
| Satellites | Terra and Aqua | Suomi NPP, NOAA-20, and NOAA-21 |
| Confidence | Score from 0 to 100 | Classes `l`, `n`, `h` |
| `type` | May be present in standard processing (SP) products | May be present in standard processing (SP) products |
| Brightness temperature (K) | `brightness` and `bright_t31` | `bright_ti4` and `bright_ti5` |

Use Suomi NPP data for historical analyses. For new VIIRS detections, check availability from NOAA-20 or NOAA-21.

## Common columns

- `latitude` and `longitude` give the pixel centre in decimal degrees.
- `scan` and `track` give the pixel dimensions in **kilometres**, across the scan and along the satellite track, respectively. The dimensions vary with the viewing angle. Use `scan * track` to approximate the pixel area in km². Use a dedicated burned area product to measure the area burned.
- `acq_date` and `acq_time` give the acquisition date and time in **UTC**. The project CSV files use `YYYY-MM-DD` and `HHMM`. Preserve `acq_time` as text. If it contains fewer than four digits, pad it with leading zeros and validate the time before combining the fields into a timestamp. The value `0814` corresponds to 08:14 UTC.
- `instrument` identifies the sensor (`MODIS` or `VIIRS`). `satellite` identifies the platform that carries it.
- `version` identifies the collection, revision, or processing stream, depending on the product. Preserve the original value as **text**, including values such as `6.03` and `2`. The suffixes `URT`, `RT`, and `NRT` indicate ultra-real-time, real-time, and near-real-time processing. Confirm the collection, revision, and standard processing (SP) status in the source or product metadata.
- `frp` is the fire radiative power associated with the detection, in **megawatts (MW)**.
- `daynight` uses `D` for daytime detections and `N` for night-time detections.
- `type` is the **inferred** category of the thermal source. It may be absent for either sensor, particularly in NRT exports.

| `type` | Category |
| --- | --- |
| `0` | Presumed vegetation fire |
| `1` | Active volcano |
| `2` | Other static land-based thermal source |
| `3` | Offshore detection (over water) |

To attribute ignition to human or natural causes, use an incident record with an established cause.

## MODIS columns

- `brightness` is the brightness temperature of channel 21/22, in kelvin. `bright_t31` is the brightness temperature of channel 31, in kelvin.
- `satellite` may contain `Aqua` or `Terra`, as in the project CSV files, or the codes `A` or `T`.
- `confidence` is a score from 0 to 100. The documented MODIS C6/C6.1 classes are low (`0–29`), nominal (`30–79`), and high (`80–100`). Record the threshold used when filtering by confidence.
- `type` is present in the project's annual CSV files. The historical standard MODIS fire location series is derived from the monthly MCD14ML product.

## VIIRS 375 m columns

- `bright_ti4` and `bright_ti5` are the brightness temperatures of channels I-4 and I-5, in kelvin. Some web services show them as `brightness` and `brightness_2`. Check `instrument` and confirm the product before normalising these names.
- `satellite` uses `N` for Suomi NPP, `N20` for NOAA-20 (JPSS-1), and `N21` for NOAA-21 (JPSS-2).
- `confidence` uses `l` (low), `n` (nominal), and `h` (high) in the project CSV files. Normalise the full labels when the source uses them. Low confidence in daytime detections can be associated with sun glint and weaker thermal anomalies. High confidence can indicate saturated pixels. NASA documents spurious low-confidence night-time detections in the South Atlantic Magnetic Anomaly region and their removal from FIRMS NRT data.
- `frp` combines measurements at 375 m and 750 m to account for I-4 channel saturation. The algorithm can divide the estimated power of a 750 m pixel among the corresponding 375 m fire pixels. In some cases, a valid detection can have a null or zero FRP value.
- `type` is present in both annual VIIRS CSV files in the project. In May 2025, NASA corrected an error in revisions 1 and 2 of the monthly `Vxx14IMGML` product that could classify static sources as presumed vegetation fires. The affected products were reprocessed as revision 3. Confirm the revision at the source before relying on this field as a filter. A CSV value of `2` alone is insufficient to identify the monthly product revision.

## Field mappings for harmonising MODIS and VIIRS

| Concept | MODIS | VIIRS |
| --- | --- | --- |
| Primary brightness temperature | `brightness` | `bright_ti4` |
| Auxiliary brightness temperature | `bright_t31` | `bright_ti5` |
| Original confidence | Numeric value from 0 to 100 | `l`, `n`, `h` |
| Thermal source category | `type`, when present | `type`, when present |

Group brightness temperatures by function only when it supports the analysis. Preserve the original field names or channel provenance, as MODIS and VIIRS use bands with different characteristics. You can map confidence to common classes for filtering. Each class reflects criteria specific to the sensor's algorithm.

### Examples from the project CSV files

The three annual Afghanistan CSV files for 2018 each have 15 columns, with 13 column names in common. The filename identifies the country, and `acq_date` gives the date of each detection.

| File | `instrument` | `satellite` | `version` | Observed `type` |
| --- | --- | --- | --- | --- |
| `modis_2018_Afghanistan.csv` | `MODIS` | `Aqua`, `Terra` | `6.03` | `0`, `2` |
| `viirs-snpp_2018_Afghanistan.csv` | `VIIRS` | `N` | `2` | `0`, `2`, `3` |
| `viirs-jpss1_2018_Afghanistan.csv` | `VIIRS` | `N20` | `2` | `0`, `2`, `3` |

## Analysis considerations

1. Spatial resolution and overpass times affect detection counts. Compare satellites in the same region, over the same dates, and on a common grid. Keep the source satellite in the data.
2. Use UTC to define the calendar day unless the analysis requires local dates. In that case, convert the timestamp to the time zone of the detection location before aggregating.
3. Apply `type == 0` to select presumed vegetation fires once you have verified the provenance of the field. Store missing types as unknown. Apply an equivalent rule when comparing sensors.
4. Specify the counting unit when combining multiple overpasses or satellites. For example, count each satellite, grid cell, and day combination once when comparing the series. State how overlapping detections are handled in a combined series. Retain individual detections for mapping and export.
5. Distinguish standard processing (SP) records from provisional NRT, RT, or URT records. Check coverage dates and known outages before interpreting a day with no records. Clouds and overpass timing can also prevent a fire from being detected.
6. Use overlapping years to calibrate the historical series and test the result on years outside the calibration period. Document the grid, filters, dates, and error metric.

## Import workflow

- Read the header of each CSV file. Identify the sensor using `instrument` and validate `satellite`. If `instrument` is absent, confirm the product from the source or metadata and use any sensor-specific brightness temperature fields.
- Preserve the relevant original fields and record the country, source file or product, and processing stream for each detection when known. For annual country CSV files, derive the country identifier from the filename or archive. For API extracts, use geographic boundaries if the analysis requires a country assignment.
- Document the column mappings, handling of missing values, spatial and temporal rules, and filters alongside the dataset.

## Sources

- [NASA FIRMS, MODIS attributes](https://firms.modaps.eosdis.nasa.gov/content/descriptions/FIRMS_MODIS_Firehotspots.html)
- [NASA FIRMS, VIIRS attributes](https://firms.modaps.eosdis.nasa.gov/content/descriptions/FIRMS_VIIRS_Firehotspots.html)
- [NASA, MODIS C6/C6.1 user guide, sections 5.5 and 8.3](https://modis-land.gsfc.nasa.gov/pdf/MODIS_C6_C6.1_Fire_User_Guide_1.0.pdf)
- [NASA, VIIRS 375 m Collection 2 user guide, sections 3.1.3, 3.2, and 6.1](https://ladsweb.modaps.eosdis.nasa.gov/archive/Document%20Archive/Science%20Data%20Product%20Documentation/VIIRS_C2_AF-375m_User_Guide_1.2.pdf)
- [NASA ARSET, FIRMS data formats and units](https://appliedsciences.nasa.gov/sites/default/files/2020-11/WildlandFire_NRTa.pdf)
- [NASA FIRMS, data sources and detection notes](https://firms.modaps.eosdis.nasa.gov/alerts/notes.php) and [Suomi NPP transition](https://firms.modaps.eosdis.nasa.gov/content/notifications/firms/news.html)

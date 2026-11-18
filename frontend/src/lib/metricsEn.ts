// English text for the metrics catalogue.
// The catalogue (spec/metricas_modis_viirs.csv) is written in Portuguese by the data team;
// this file only translates it for the English UI. Keyed by the CSV id.
// A metric missing here falls back to the Portuguese text.

export interface MetricText {
  name: string
  description: string
  unit: string
  calculation: string
}

export const METRICS_EN: Record<string, MetricText> = {
  'CAL-01': {
    name: 'Cell-days with detections',
    description: 'Measures the activity observed in the chosen period and region. Each cell with at least one valid detection counts once per UTC day.',
    unit: 'cell-days',
    calculation: 'Count distinct pairs of cell and UTC day, following the sensor combination rule.',
  },
  'CAL-02': {
    name: 'Daily activity',
    description: 'Shows the activity observed on each UTC day of the selected period.',
    unit: 'cell-days per day',
    calculation: 'Add up the active cells of each day. Flag days with missing or unknown coverage separately.',
  },
  'CAL-03': {
    name: 'Monthly activity',
    description: 'Fills each month × year position of the calendar for the selected region.',
    unit: 'cell-days per month',
    calculation: 'Add up the consolidated daily series per month. If there is a historical adjustment, use the adjusted series and flag estimated values. Flag partial months.',
  },
  'CAL-04': {
    name: 'Annual activity',
    description: 'Shows the calendar total for each year in the selection.',
    unit: 'cell-days per year',
    calculation: 'Add up the months of the year with the same counting rule. Flag partial years or years with insufficient coverage.',
  },
  'CAL-05': {
    name: 'Total activity in the period',
    description: 'Number shown on the summary card for the selected period and region.',
    unit: 'cell-days',
    calculation: 'Add up the canonical series over the period, with the same filters and version used by the calendar and the aggregated CSV.',
  },
  'CAL-06': {
    name: 'Peak month',
    description: 'Identifies the month and year with the highest monthly total in the selection.',
    unit: 'month-year and cell-days',
    calculation: 'Find the maximum among comparable months with valid coverage. Apply a documented rule for ties.',
  },
  'CAL-07': {
    name: 'Peak year',
    description: 'Identifies the year with the highest observed activity in the region.',
    unit: 'year and cell-days',
    calculation: 'Find the maximum among complete, comparable years. For partial periods, compare equivalent windows across years.',
  },
  'CAL-08': {
    name: 'Annual average activity',
    description: 'Summarises the average activity level of the comparable years in the analysis.',
    unit: 'cell-days per year',
    calculation: 'Divide the sum of annual totals by the number of complete, eligible years. Report which years are included.',
  },
  'CAL-09': {
    name: 'Historical mean of the same month',
    description: 'Gives the January–December historical reference for the selected region.',
    unit: 'cell-days per month',
    calculation: 'Average each calendar month over the reference years with valid coverage. Leave the evaluated period out of the reference when measuring an anomaly.',
  },
  'CAL-10': {
    name: 'Days with detections',
    description: 'How many days had at least one active cell in the region.',
    unit: 'days',
    calculation: 'Count distinct UTC dates with one or more eligible detections.',
  },
  'CAL-11': {
    name: 'Highest daily activity',
    description: 'Date and size of the daily peak in the period.',
    unit: 'date and cell-days',
    calculation: 'Find the largest daily total among the eligible dates.',
  },
  'CAL-12': {
    name: 'Monthly seasonal profile',
    description: 'Shows which months of the year tend to concentrate the most activity in the region.',
    unit: 'cell-days per month',
    calculation: 'Build a 12-month profile from the mean of each month across comparable years. Report the number of years per month.',
  },
  'HIS-01': {
    name: 'Historical monthly median',
    description: 'The typical value of the month, less influenced by extreme years.',
    unit: 'cell-days per month',
    calculation: 'Take the median of the same calendar month over the eligible reference years.',
  },
  'HIS-02': {
    name: 'Historical monthly range',
    description: 'The range where the usual activity of that month lies.',
    unit: 'cell-days per month',
    calculation: 'Estimate the 10th and 90th percentiles of the same month over eligible years. Report the sample size and the quantile rule.',
  },
  'HIS-03': {
    name: 'Absolute monthly anomaly',
    description: 'How far the observed month is from the historical mean of the same month.',
    unit: 'cell-days',
    calculation: 'Subtract the historical monthly mean from the observed monthly value. A positive value means activity above the reference.',
  },
  'HIS-04': {
    name: 'Percentage monthly anomaly',
    description: 'The deviation from the reference as a percentage, useful to compare months with different usual levels.',
    unit: '%',
    calculation: 'Divide the absolute anomaly by the historical mean of the same month and multiply by 100. Not available if the mean is zero.',
  },
  'HIS-05': {
    name: 'Standardised monthly deviation (z-score)',
    description: 'Distance from the mean in historical standard deviations of the same month.',
    unit: 'standard deviations',
    calculation: 'Divide the absolute anomaly by the standard deviation of the historical values of the same month. Not available if the sample is too small or the standard deviation is zero.',
  },
  'HIS-06': {
    name: 'Historical percentile of activity',
    description: 'Where the selected month sits in the historical distribution of the same month in the region.',
    unit: 'percentile (0 to 100)',
    calculation: 'Percentage of historical years below the observed value, counting half of the ties. Show how many years were used.',
  },
  'HIS-07': {
    name: 'Comparable year-to-date total',
    description: 'Compares the selected year up to the cut-off date with the same window in previous years.',
    unit: 'cell-days',
    calculation: 'Add up activity from 1 January to the same cut-off date in each year, using only windows with comparable coverage.',
  },
  'HIS-08': {
    name: 'Year-on-year monthly change',
    description: 'The difference from the same month of the previous year.',
    unit: '%',
    calculation: 'Divide the difference between the two months by the previous year’s value and multiply by 100. If that value is zero, show the absolute difference.',
  },
  'HIS-09': {
    name: 'Months above the historical range',
    description: 'How many months in the period exceeded the upper limit of the usual range.',
    unit: 'months',
    calculation: 'Count eligible months with activity above the historical 90th percentile of that month. The reference is fixed before comparing.',
  },
  'HIS-10': {
    name: 'Trend of annual totals',
    description: 'Estimates the direction and size of the change in activity over several years.',
    unit: 'cell-days per year of trend',
    calculation: 'Theil-Sen slope over complete annual totals of the harmonised series. Report the period and the uncertainty.',
  },
  'ESP-01': {
    name: 'Activity density',
    description: 'Lets you compare the activity of regions of different sizes over the same time window.',
    unit: 'cell-days per 1,000 km²',
    calculation: 'Divide total cell-days by the region’s area in km² and multiply by 1,000. Use the same area definition, period and coverage when comparing.',
  },
  'ESP-02': {
    name: 'Distinct cells with detections',
    description: 'How many grid locations had activity during the period.',
    unit: 'cells',
    calculation: 'Count distinct spatial ids with at least one eligible detection in the period.',
  },
  'ESP-03': {
    name: 'Recurrence per cell',
    description: 'Shows the places where valid detections repeated over several days.',
    unit: 'days per cell',
    calculation: 'Count distinct UTC dates with detections in each cell.',
  },
  'ESP-04': {
    name: 'Share of the grid with detections',
    description: 'Percentage of the region’s eligible cells that had activity in the period.',
    unit: '% of cells',
    calculation: 'Divide distinct cells with detections by the total eligible cells in the region. Fix the rule for border and sea cells.',
  },
  'ESP-05': {
    name: 'Detection frequency per cell',
    description: 'Separates often-observed regions from areas with few observation opportunities.',
    unit: '% of observed days',
    calculation: 'Divide days with detections by the cell’s days with valid observation and multiply by 100. Needs coverage per cell and day.',
  },
  'ESP-06': {
    name: 'Year-to-year recurrence per cell',
    description: 'Identifies places with detections in more than one comparable year.',
    unit: 'years per cell',
    calculation: 'Count eligible years with at least one detection in the cell. Report the number of years analysed.',
  },
  'OBS-01': {
    name: 'Raw detections by sensor and satellite',
    description: 'Counts the original points received for each platform, before cleaning and aggregation.',
    unit: 'detections',
    calculation: 'Count rows by instrument, satellite, region and period.',
  },
  'OBS-02': {
    name: 'Distribution by confidence class',
    description: 'How many records were classed as low, nominal or high confidence for each sensor.',
    unit: 'detections and %',
    calculation: 'Normalise classes per sensor: MODIS C6/C6.1 uses 0–29, 30–79 and 80–100; VIIRS uses l, n and h. Compute count and percentage per class.',
  },
  'OBS-03': {
    name: 'Detections after the quality filter',
    description: 'Number of points accepted into the series for the region and window analysed.',
    unit: 'detections',
    calculation: 'Count the valid rows that pass the confidence filter and, when adopted and verifiable, the type filter.',
  },
  'OBS-04': {
    name: 'Share of night-time detections',
    description: 'How valid records split between daytime and night-time passes of a sensor.',
    unit: '% of detections',
    calculation: 'Divide N detections by the total with daynight D or N. Report per sensor or satellite to keep the differences in overpass times.',
  },
  'OBS-05': {
    name: 'Median FRP',
    description: 'The typical radiative power of detections with a usable value in the period.',
    unit: 'MW',
    calculation: 'Median FRP per sensor and region, applying the product’s quality rule for missing and zero values.',
  },
  'OBS-06': {
    name: '90th percentile of FRP',
    description: 'The threshold above which lie roughly the 10% of detections with the highest radiative power.',
    unit: 'MW',
    calculation: '90th percentile of usable FRP values within the same sensor, period and region. Report the number of observations.',
  },
  'OBS-07': {
    name: 'Peak FRP',
    description: 'Locates the record with the highest radiative power in the selection.',
    unit: 'MW, timestamp and location',
    calculation: 'Find the highest valid FRP and return its coordinates and time. Compare peaks within the same product.',
  },
  'OBS-08': {
    name: 'FRP availability',
    description: 'Percentage of eligible detections with a usable radiative power.',
    unit: '% of detections',
    calculation: 'Divide records with usable FRP by the eligible total. Handle missing and zero values according to the available quality information.',
  },
  'OBS-09': {
    name: 'Distribution by thermal source type',
    description: 'Summarises the categories inferred by FIRMS, including presumed vegetation fire and static sources.',
    unit: 'detections and %',
    calculation: 'Count detections by type and keep missing values as unknown. Check the VIIRS product version before reading the classification.',
  },
  'OBS-10': {
    name: 'Median detection pixel area',
    description: 'How much the observed pixel size varies by sensor and platform.',
    unit: 'km² per pixel',
    calculation: 'Approximate each pixel’s area as scan × track and take the median per sensor. It describes the observed resolution.',
  },
  'QA-01': {
    name: 'Schema validation rate',
    description: 'Share of records that follow the contract for fields, formats and values.',
    unit: '% of rows',
    calculation: 'Divide rows that pass validation by the total read. Check coordinates, date, time, sensor, satellite and required fields.',
  },
  'QA-02': {
    name: 'Filter retention rate',
    description: 'Percentage of records still eligible after the configured filters.',
    unit: '% of rows',
    calculation: 'Divide detections after the filters by the records that entered the filtering step. Report per sensor and period.',
  },
  'QA-03': {
    name: 'Records grouped per cell-day on the same satellite',
    description: 'How many points repeat a cell and date already seen by the same satellite.',
    unit: 'grouped detections',
    calculation: 'Per satellite, subtract the distinct cell-day pairs from the number of eligible points. Publish the total per satellite.',
  },
  'QA-04': {
    name: 'Redundancy between satellites of the same sensor',
    description: 'How often cell-days repeat across MODIS platforms or across VIIRS platforms.',
    unit: 'repeated cell-day observations',
    calculation: 'Per sensor, subtract the size of the union of cell-days from the sum of each satellite’s unique counts.',
  },
  'QA-05': {
    name: 'Days with confirmed coverage',
    description: 'How many days of the period could be classed as validly covered for the region and sensor.',
    unit: 'days and %',
    calculation: 'Count days with valid observation and divide by the expected days. Use coverage metadata per region and date, or observation masks.',
  },
  'QA-06': {
    name: 'Share of provisional activity',
    description: 'Fraction of the published activity backed only by recent, provisional processing.',
    unit: '% of cell-days',
    calculation: 'Divide cell-days with only NRT, RT or URT detections by the active cell-days in the query. Mark the origin from the metadata.',
  },
  'QA-07': {
    name: 'Delay of the latest available observation',
    description: 'Time between the query and the latest observation available from the source.',
    unit: 'hours or days',
    calculation: 'Subtract the latest date or time available in the source from the query’s UTC time. Record the last ingestion date separately.',
  },
  'HAR-01': {
    name: 'Cell-days shared by MODIS and VIIRS',
    description: 'How many cells were flagged by both instruments on the same UTC day.',
    unit: 'cell-days',
    calculation: 'Count the intersection of the two sets over the same area and observation window, with the same grid and equivalent filters.',
  },
  'HAR-02': {
    name: 'Jaccard overlap index',
    description: 'Measures the relative spatial and temporal agreement between MODIS and VIIRS detections.',
    unit: 'index from 0 to 1',
    calculation: 'Divide the size of the intersection by the size of the union of the cell-day sets. Not available if the union is empty.',
  },
  'HAR-03': {
    name: 'Comparable months used in validation',
    description: 'How many pairs of monthly observations support the calibration or the test.',
    unit: 'months',
    calculation: 'Count months in which both sensors give comparable data; publish the number per region and per evaluation set.',
  },
  'HAR-04': {
    name: 'Monthly Pearson correlation',
    description: 'How closely the two sensors’ series move together over their shared months.',
    unit: 'coefficient from -1 to 1',
    calculation: 'Pearson correlation over comparable monthly pairs. Report the number of months; not available if a series is constant.',
  },
  'HAR-05': {
    name: 'Monthly Spearman correlation',
    description: 'Whether the sensors rank the months in a similar way, including the most active periods.',
    unit: 'coefficient from -1 to 1',
    calculation: 'Correlation between the ranks of the months in the two series, with tie handling.',
  },
  'HAR-06': {
    name: 'MODIS to VIIRS adjustment factor',
    description: 'Estimates the change of scale needed to bring the MODIS record close to the VIIRS reference series.',
    unit: 'multiplier',
    calculation: 'Divide the VIIRS activity sum by the MODIS activity sum over the calibration period, or fit a documented regression. Compute per region or season when there are enough pairs.',
  },
  'HAR-07': {
    name: 'Uncertainty interval of the adjustment factor',
    description: 'How much the adjustment factor can vary across different samples of the observed record.',
    unit: 'lower and upper bounds of the multiplier',
    calculation: 'Resample years in blocks, or another documented method that respects time dependence. Show the interval (e.g. 95%) and the number of years.',
  },
  'HAR-08': {
    name: 'Monthly mean absolute error (MAE)',
    description: 'The average difference, in calendar units, from the VIIRS reference series.',
    unit: 'cell-days per month',
    calculation: 'Mean of the absolute monthly differences. Compare raw and adjusted MODIS over the same test months, outside the calibration.',
  },
  'HAR-09': {
    name: 'Weighted absolute percentage error (WAPE)',
    description: 'Total monthly absolute error as a percentage of the reference activity in the test period.',
    unit: '%',
    calculation: 'Add up the monthly absolute errors, divide by the sum of comparable VIIRS values and multiply by 100. Not available if the reference sum is zero.',
  },
  'HAR-10': {
    name: 'Mean monthly bias',
    description: 'Whether the adjusted series tends to sit above or below the VIIRS reference.',
    unit: 'cell-days per month',
    calculation: 'Mean of the signed differences between adjusted MODIS and VIIRS over comparable test months.',
  },
  'HAR-11': {
    name: 'Error reduction after adjustment',
    description: 'The gain over unadjusted MODIS counts under the same conditions.',
    unit: '%',
    calculation: 'Subtract the MAE after adjustment from the MAE before, divide by the MAE before and multiply by 100. Only when the initial MAE is positive.',
  },
  'HAR-12': {
    name: 'Residual step at the sensor transition',
    description: 'Estimates the level change at the transition date, after accounting for seasonality and trend.',
    unit: 'cell-days per month',
    calculation: 'Fit a segmented regression with monthly effects and a level-shift term. Compare the step and its uncertainty before and after harmonising. Use S-NPP to test the 2012 transition.',
  },
  'HAR-13': {
    name: 'Sensitivity to grid size',
    description: 'How much counts or errors change when the spatial resolution changes.',
    unit: 'cell-days or %',
    calculation: 'Repeat the analysis on grids of different sizes, keeping region, dates, filters and reference. Compare counts, matches and errors.',
  },
  'HAR-14': {
    name: 'Sensitivity to the confidence filter',
    description: 'How the confidence threshold affects the calendar and the agreement between sensors.',
    unit: 'cell-days or %',
    calculation: 'Repeat the counts and the validation with documented filters. Compare retention and the change in error over an identical window.',
  },
}

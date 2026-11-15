// UI text in English and Portuguese. The language switch (top right) changes
// it instantly, without reloading. To add a text: add the key to BOTH
// languages, then use t('key') in a component (const t = useT()).
import { useApp } from './store'

export type Lang = 'en' | 'pt'

const en = {
  // brand / general
  'brand.sub': 'MODIS + VIIRS',
  'mock': 'mock data',
  'hero.title': 'Two decades of fire, one consistent record.',
  'hero.sub': 'Search any place to see when and how much it burns.',
  'hotspots': 'hotspots',
  'close': 'Close',

  // search
  'search.placeholder': 'Search a place or type lat, lon',
  'search.label': 'Search a place',
  'search.clear': 'Clear search',
  'search.searching': 'Searching…',
  'search.none': 'No places found.',
  'search.coords': 'Coordinates',
  'search.unavailable': 'Place search is unavailable right now',

  // area panel
  'panel.radius': 'Radius',
  'panel.radiusAria': 'Radius in km',
  'panel.period': 'Period',
  'panel.from': 'From',
  'panel.to': 'To',
  'range.12m': '12 months',
  'range.5y': '5 years',
  'range.all': 'Full record',
  'panel.analyze': 'Analyze area',
  'panel.update': 'Update analysis',
  'panel.analyzing': 'Analyzing…',
  'panel.badDates': 'The start date is after the end date.',
  'panel.info': 'MODIS (2000→) and VIIRS (2012→) hotspots, harmonized to VIIRS-equivalent counts so the sensor does not matter.',
  'kpi.total': 'Total',
  'kpi.totalSub': 'hotspots in the period',
  'kpi.peakMonth': 'Peak month',
  'kpi.avg': 'Annual average',
  'kpi.avgSub': 'hotspots per year',
  'kpi.vsMean': 'vs mean',
  'kpi.vsMeanToDate': 'vs mean to date',
  'kpi.soFar': 'so far',
  'kpi.mean': 'mean',
  'kpi.peakYear': 'Peak year: {year} ({count} hotspots)',
  'kpi.peakYearLabel': 'Peak year',

  // date picker
  'date.prev': 'Previous month',
  'date.next': 'Next month',
  'date.month': 'Month',
  'date.year': 'Year',
  'date.earliest': 'Earliest',
  'date.latest': 'Latest',

  // empty state
  'empty.title': 'No hotspots detected',
  'empty.body': 'Nothing within {radius} km between {from} and {to}.',
  'empty.try': 'Try a wider search:',
  'empty.tryRadius': 'Try {radius} km',
  'empty.fullRecord': 'Use full record',
  'empty.toastTitle': 'No hotspots to show',
  'empty.toastBody': 'Nothing was detected in this area and period. Try a larger radius or a longer period.',

  // analyses menu
  'menu.aria': 'Analyses',
  'menu.title': 'Analyze this area',
  'menu.searchFirst': 'Search a place first',
  'menu.calendar': 'Burning calendar',
  'menu.trend': 'Trend & anomalies',
  'menu.seasonal': 'Seasonal profile',
  'menu.ranking': 'Year ranking',
  'menu.hotspots': 'Hotspots on map',
  'menu.hideHotspots': 'Hide hotspots',
  'menu.replay': 'Replay fires',
  'menu.export': 'Export & info',
  'menu.hotspotsCsv': 'Hotspots CSV',
  'menu.calendarCsv': 'Calendar CSV',
  'menu.report': 'PDF report',
  'menu.about': 'About the data',
  'toast.csvPreparing': 'Preparing CSV…',
  'toast.csvDone': 'CSV with {count} hotspots downloaded',
  'toast.csvCapped': 'Capped at the backend limit of {max}.',
  'toast.csvFailed': 'Export failed',
  'toast.calendarCsv': 'Monthly calendar downloaded',
  'toast.analyzeFailed': 'Could not analyze this area',
  'toast.hotspotsFailed': 'Could not load hotspots',
  'toast.hotspotsShown': '{count} hotspots on the map',
  'toast.hotspotsSample': 'Showing a sample of {max} points.',
  'toast.monthShown': 'Showing hotspots of {month}',

  // results panel
  'view.calendar': 'Burning calendar',
  'view.trend': 'Trend & anomalies',
  'view.seasonal': 'Seasonal profile',
  'view.ranking': 'Year ranking',
  'view.about': 'About the data',
  'view.loading': 'Loading data…',
  'export.png': 'PNG',
  'export.svg': 'SVG',
  'export.saveAs': 'Download this chart',

  // calendar
  'cal.latest': 'latest',
  'cal.vsMean': 'vs mean {month}',
  'cal.toDate': 'to date',
  'cal.scale': 'Scale',
  'cal.scale.absolute': 'Count',
  'cal.scale.relative': 'Relative',
  'cal.scale.anomaly': 'Anomaly',
  'cal.scaleNote.absolute': 'Hotspots per month, logarithmic classes so quiet months stay visible.',
  'cal.scaleNote.relative': 'Share of this area’s busiest month (100% = peak month).',
  'cal.scaleNote.anomaly': 'Difference from the mean of the same month over all years in the period.',
  'cal.total': 'Total',
  'cal.mean': 'Mean',
  'cal.noData': 'No data',
  'cal.peak': 'Peak month',
  'cal.current': 'Current month (incomplete)',
  'cal.below': 'Below mean',
  'cal.above': 'Above mean',
  'cal.clickHint': 'Click a month to show its hotspots on the map.',
  'cal.footnote': 'Years before 2012 come from MODIS only, converted to VIIRS-equivalent counts. Hatched cells: before the start of the satellite record (Nov 2000).',

  // trend
  'trend.annual': 'Annual',
  'trend.monthly': 'Monthly',
  'trend.intro': 'Hotspots over time. The dashed line is the historical mean for the period.',
  'trend.mean': 'Historical mean',
  'trend.yAnnual': 'Hotspots per year',
  'trend.yMonthly': 'Hotspots per month',
  'trend.anomTitle': 'Yearly anomaly',
  'trend.anomIntro': 'Each bar is the year’s total minus the mean of all years. Above means more burning than usual, below means less.',
  'trend.vsMean': 'vs mean',
  'trend.partial': 'Faded bars are incomplete years, so their totals are still growing.',

  // seasonal
  'season.intro': 'Typical fire season for this area. The band covers 80% of past years (P10 to P90), the grey line is the mean.',
  'season.year': 'Compare year',
  'season.mean': 'Mean',
  'season.band': 'P10–P90',
  'season.above': 'Above the usual range in {year}: {months}.',
  'season.none': '{year} stayed within the usual range.',

  // ranking
  'rank.years': 'Most active years',
  'rank.months': 'Worst single months',

  // about
  'about.why': 'Why harmonize?',
  'about.whyText': 'MODIS (Terra and Aqua, since 2000) sees the ground in 1 km pixels. VIIRS (since 2012) uses 375 m pixels and detects much smaller fires. Counting their hotspots side by side would make recent years look worse just because the sensor is better.',
  'about.what': 'What we do.',
  'about.whatText': 'Both records are put on the same grid, and the overlap period (2012 to today, when both sensors fly) is used to learn how MODIS counts relate to VIIRS counts. The MODIS-only years are then converted into VIIRS-equivalent counts, so the whole series reads as one sensor.',
  'about.limits': 'Limits.',
  'about.limitsText': 'Hotspots are thermal anomalies, not fires: one fire can produce many hotspots and clouds can hide others. Terra and Aqua orbits have drifted in recent years, which changes their overpass time.',
  'about.updated': 'Data last updated',
  'about.unknown': 'not provided by the server yet',
  'about.source': 'Data: NASA FIRMS (MODIS C6.1, VIIRS S-NPP / NOAA-20 / NOAA-21). Built for the NASA Space Apps Challenge 2026.',

  // map
  'map.dark': 'Map',
  'map.satellite': 'Satellite',
  'map.3d': '3D',
  'map.darkTitle': 'Dark map',
  'map.satTitle': 'Satellite imagery (Sentinel-2)',
  'map.3dTitle': '3D terrain and buildings',
  'filter.showing': 'Hotspots of {month}',
  'filter.clear': 'Show all',

  // replay
  'replay.play': 'Play replay',
  'replay.pause': 'Pause replay',
  'replay.stop': 'Stop replay and show all hotspots',
  'replay.date': 'Replay date',

  // export / report
  'report.title': 'Fire activity report',
  'report.generated': 'Generated',
  'report.source': 'Source: NASA FIRMS (MODIS C6.1, VIIRS), harmonized to VIIRS-equivalent counts · FireCal',
  'report.area': 'Area',
  'report.period': 'Period',
  'report.monthlyMeans': 'Mean hotspots per month',
  'report.popup': 'Allow pop-ups to open the report',
} as const

export type TKey = keyof typeof en

const pt: Record<TKey, string> = {
  'brand.sub': 'MODIS + VIIRS',
  'mock': 'dados de teste',
  'hero.title': 'Duas décadas de fogo, um registo consistente.',
  'hero.sub': 'Pesquise qualquer local para ver quando e quanto arde.',
  'hotspots': 'focos',
  'close': 'Fechar',

  'search.placeholder': 'Pesquisar um local ou escrever lat, lon',
  'search.label': 'Pesquisar um local',
  'search.clear': 'Limpar pesquisa',
  'search.searching': 'A pesquisar…',
  'search.none': 'Nenhum local encontrado.',
  'search.coords': 'Coordenadas',
  'search.unavailable': 'A pesquisa de locais não está disponível agora',

  'panel.radius': 'Raio',
  'panel.radiusAria': 'Raio em km',
  'panel.period': 'Período',
  'panel.from': 'De',
  'panel.to': 'Até',
  'range.12m': '12 meses',
  'range.5y': '5 anos',
  'range.all': 'Registo completo',
  'panel.analyze': 'Analisar área',
  'panel.update': 'Atualizar análise',
  'panel.analyzing': 'A analisar…',
  'panel.badDates': 'A data de início é posterior à data de fim.',
  'panel.info': 'Focos MODIS (2000→) e VIIRS (2012→), harmonizados para contagens equivalentes ao VIIRS, para que o sensor não importe.',
  'kpi.total': 'Total',
  'kpi.totalSub': 'focos no período',
  'kpi.peakMonth': 'Mês de pico',
  'kpi.avg': 'Média anual',
  'kpi.avgSub': 'focos por ano',
  'kpi.vsMean': 'vs média',
  'kpi.vsMeanToDate': 'vs média até à data',
  'kpi.soFar': 'até agora',
  'kpi.mean': 'média',
  'kpi.peakYear': 'Ano de pico: {year} ({count} focos)',
  'kpi.peakYearLabel': 'Ano de pico',

  'date.prev': 'Mês anterior',
  'date.next': 'Mês seguinte',
  'date.month': 'Mês',
  'date.year': 'Ano',
  'date.earliest': 'Mais antigo',
  'date.latest': 'Mais recente',

  'empty.title': 'Nenhum foco detetado',
  'empty.body': 'Nada num raio de {radius} km entre {from} e {to}.',
  'empty.try': 'Experimente alargar a pesquisa:',
  'empty.tryRadius': 'Experimentar {radius} km',
  'empty.fullRecord': 'Usar registo completo',
  'empty.toastTitle': 'Sem focos para mostrar',
  'empty.toastBody': 'Nada foi detetado nesta área e período. Experimente um raio maior ou um período mais longo.',

  'menu.aria': 'Análises',
  'menu.title': 'Analisar esta área',
  'menu.searchFirst': 'Pesquise primeiro um local',
  'menu.calendar': 'Calendário de queimadas',
  'menu.trend': 'Tendência e anomalias',
  'menu.seasonal': 'Perfil sazonal',
  'menu.ranking': 'Ranking anual',
  'menu.hotspots': 'Focos no mapa',
  'menu.hideHotspots': 'Esconder focos',
  'menu.replay': 'Replay dos fogos',
  'menu.export': 'Exportar e info',
  'menu.hotspotsCsv': 'CSV dos focos',
  'menu.calendarCsv': 'CSV do calendário',
  'menu.report': 'Relatório PDF',
  'menu.about': 'Sobre os dados',
  'toast.csvPreparing': 'A preparar o CSV…',
  'toast.csvDone': 'CSV com {count} focos descarregado',
  'toast.csvCapped': 'Limitado ao máximo do servidor ({max}).',
  'toast.csvFailed': 'A exportação falhou',
  'toast.calendarCsv': 'Calendário mensal descarregado',
  'toast.analyzeFailed': 'Não foi possível analisar esta área',
  'toast.hotspotsFailed': 'Não foi possível carregar os focos',
  'toast.hotspotsShown': '{count} focos no mapa',
  'toast.hotspotsSample': 'A mostrar uma amostra de {max} pontos.',
  'toast.monthShown': 'A mostrar os focos de {month}',

  'view.calendar': 'Calendário de queimadas',
  'view.trend': 'Tendência e anomalias',
  'view.seasonal': 'Perfil sazonal',
  'view.ranking': 'Ranking anual',
  'view.about': 'Sobre os dados',
  'view.loading': 'A carregar dados…',
  'export.png': 'PNG',
  'export.svg': 'SVG',
  'export.saveAs': 'Descarregar este gráfico',

  'cal.latest': 'mais recente',
  'cal.vsMean': 'vs média de {month}',
  'cal.toDate': 'até à data',
  'cal.scale': 'Escala',
  'cal.scale.absolute': 'Contagem',
  'cal.scale.relative': 'Relativa',
  'cal.scale.anomaly': 'Anomalia',
  'cal.scaleNote.absolute': 'Focos por mês, em classes logarítmicas para os meses calmos continuarem visíveis.',
  'cal.scaleNote.relative': 'Percentagem do mês mais ativo desta área (100% = mês de pico).',
  'cal.scaleNote.anomaly': 'Diferença face à média do mesmo mês em todos os anos do período.',
  'cal.total': 'Total',
  'cal.mean': 'Média',
  'cal.noData': 'Sem dados',
  'cal.peak': 'Mês de pico',
  'cal.current': 'Mês atual (incompleto)',
  'cal.below': 'Abaixo da média',
  'cal.above': 'Acima da média',
  'cal.clickHint': 'Clique num mês para ver os seus focos no mapa.',
  'cal.footnote': 'Os anos antes de 2012 vêm só do MODIS, convertidos para contagens equivalentes ao VIIRS. Células tracejadas: antes do início do registo de satélite (nov 2000).',

  'trend.annual': 'Anual',
  'trend.monthly': 'Mensal',
  'trend.intro': 'Focos ao longo do tempo. A linha tracejada é a média histórica do período.',
  'trend.mean': 'Média histórica',
  'trend.yAnnual': 'Focos por ano',
  'trend.yMonthly': 'Focos por mês',
  'trend.anomTitle': 'Anomalia anual',
  'trend.anomIntro': 'Cada barra é o total do ano menos a média de todos os anos. Acima significa mais queimadas do que o habitual, abaixo significa menos.',
  'trend.vsMean': 'vs média',
  'trend.partial': 'As barras esbatidas são anos incompletos, cujos totais ainda estão a crescer.',

  'season.intro': 'Época de fogos típica desta área. A faixa cobre 80% dos anos anteriores (P10 a P90) e a linha cinzenta é a média.',
  'season.year': 'Comparar ano',
  'season.mean': 'Média',
  'season.band': 'P10–P90',
  'season.above': 'Acima do habitual em {year}: {months}.',
  'season.none': '{year} ficou dentro do habitual.',

  'rank.years': 'Anos mais ativos',
  'rank.months': 'Piores meses',

  'about.why': 'Porquê harmonizar?',
  'about.whyText': 'O MODIS (Terra e Aqua, desde 2000) vê o terreno em píxeis de 1 km. O VIIRS (desde 2012) usa píxeis de 375 m e deteta fogos muito mais pequenos. Contar os focos dos dois lado a lado faria os anos recentes parecerem piores só porque o sensor é melhor.',
  'about.what': 'O que fazemos.',
  'about.whatText': 'Os dois registos são colocados na mesma grelha, e o período em que os dois sensores coexistem (de 2012 até hoje) serve para aprender como as contagens MODIS se relacionam com as VIIRS. Os anos só com MODIS são depois convertidos em contagens equivalentes ao VIIRS, para que a série inteira se leia como um único sensor.',
  'about.limits': 'Limitações.',
  'about.limitsText': 'Os focos são anomalias térmicas, não incêndios: um incêndio pode gerar muitos focos e as nuvens podem esconder outros. As órbitas do Terra e do Aqua derivaram nos últimos anos, o que muda a hora de passagem.',
  'about.updated': 'Última atualização dos dados',
  'about.unknown': 'o servidor ainda não indica',
  'about.source': 'Dados: NASA FIRMS (MODIS C6.1, VIIRS S-NPP / NOAA-20 / NOAA-21). Feito para o NASA Space Apps Challenge 2026.',

  'map.dark': 'Mapa',
  'map.satellite': 'Satélite',
  'map.3d': '3D',
  'map.darkTitle': 'Mapa escuro',
  'map.satTitle': 'Imagem de satélite (Sentinel-2)',
  'map.3dTitle': 'Relevo e edifícios em 3D',
  'filter.showing': 'Focos de {month}',
  'filter.clear': 'Mostrar todos',

  'replay.play': 'Reproduzir',
  'replay.pause': 'Pausar',
  'replay.stop': 'Parar o replay e mostrar todos os focos',
  'replay.date': 'Data do replay',

  'report.title': 'Relatório de atividade de fogo',
  'report.generated': 'Gerado em',
  'report.source': 'Fonte: NASA FIRMS (MODIS C6.1, VIIRS), harmonizado para contagens equivalentes ao VIIRS · FireCal',
  'report.area': 'Área',
  'report.period': 'Período',
  'report.monthlyMeans': 'Média de focos por mês',
  'report.popup': 'Permita pop-ups para abrir o relatório',
}

const DICTS: Record<Lang, Record<TKey, string>> = { en, pt }

export function translate(lang: Lang, key: TKey, vars?: Record<string, string | number>) {
  let s: string = DICTS[lang][key] ?? en[key]
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v))
  return s
}

/** Hook: const t = useT(); t('panel.radius') */
export function useT() {
  const lang = useApp((s) => s.lang)
  return (key: TKey, vars?: Record<string, string | number>) => translate(lang, key, vars)
}

export const locale = (lang: Lang) => (lang === 'pt' ? 'pt-PT' : 'en-GB')

function cap(s: string) {
  s = s.replace('.', '')
  return s.charAt(0).toUpperCase() + s.slice(1)
}
/** Month name, i = 1..12 */
export function monthName(i: number, lang: Lang, style: 'short' | 'long' = 'short') {
  return cap(new Intl.DateTimeFormat(lang === 'pt' ? 'pt-PT' : 'en-US', { month: style, timeZone: 'UTC' }).format(new Date(Date.UTC(2020, i - 1, 15))))
}

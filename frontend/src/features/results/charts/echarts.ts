/** ECharts com só o que usamos (tree-shaking): barras, linhas, candles, dispersão e os componentes de eixo. */
import { BarChart, CandlestickChart, LineChart, ScatterChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart, CandlestickChart, LineChart, ScatterChart,
  AxisPointerComponent, DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent,
  CanvasRenderer,
])

export { echarts }
export type { EChartsCoreOption as Option } from 'echarts/core'

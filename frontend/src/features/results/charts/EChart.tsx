import { useEffect, useRef } from 'react'
import { echarts, type Option } from './echarts'

interface Props {
  option: Option
  height: number
  ariaLabel: string
}

/** Casca fina do ECharts: cria uma vez, redimensiona com o contêiner, descarta ao sair. */
export function EChart({ option, height, ariaLabel }: Props) {
  const el = useRef<HTMLDivElement>(null)
  const chart = useRef<ReturnType<typeof echarts.init> | null>(null)

  useEffect(() => {
    const node = el.current
    if (!node) return
    const c = echarts.init(node, undefined, { renderer: 'canvas' })
    chart.current = c
    const ro = new ResizeObserver(() => c.resize())
    ro.observe(node)
    return () => {
      ro.disconnect()
      c.dispose()
      chart.current = null
    }
  }, [])

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true })
  }, [option])

  return <div ref={el} role="img" aria-label={ariaLabel} style={{ width: '100%', height }} />
}

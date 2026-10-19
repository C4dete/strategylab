import { useEffect, useRef, useState } from 'react'

export function prefereMenosMovimento(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/** Anima o número do valor anterior até o novo (ease-out). Sem animação com `prefers-reduced-motion`. */
export function useCountUp(alvo: number, duracaoMs = 700): number {
  const [valor, setValor] = useState(alvo)
  const de = useRef(alvo)

  useEffect(() => {
    if (prefereMenosMovimento() || de.current === alvo) {
      de.current = alvo
      setValor(alvo)
      return
    }
    const inicio = performance.now()
    const origem = de.current
    let raf = 0
    const passo = (agora: number) => {
      const t = Math.min(1, (agora - inicio) / duracaoMs)
      const e = 1 - Math.pow(1 - t, 3)
      const v = origem + (alvo - origem) * e
      de.current = v
      setValor(v)
      if (t < 1) raf = requestAnimationFrame(passo)
    }
    raf = requestAnimationFrame(passo)
    return () => cancelAnimationFrame(raf)
  }, [alvo, duracaoMs])

  return valor
}

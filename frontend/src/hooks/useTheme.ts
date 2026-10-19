import { useCallback, useSyncExternalStore } from 'react'

export type Tema = 'dark' | 'light'
const CHAVE = 'strategylab:tema'

function atual(): Tema {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark'
}

function assinar(cb: () => void): () => void {
  const obs = new MutationObserver(cb)
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  return () => obs.disconnect()
}

/** Tema atual (o atributo `data-theme` do <html> é a fonte da verdade; o script do index.html o define antes da pintura). */
export function useTheme(): { tema: Tema; alternar: () => void } {
  const tema = useSyncExternalStore(assinar, atual, () => 'dark' as Tema)
  const alternar = useCallback(() => {
    const novo: Tema = atual() === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', novo)
    try {
      localStorage.setItem(CHAVE, novo)
    } catch {
      /* armazenamento indisponível: vale só para esta aba */
    }
  }, [])
  return { tema, alternar }
}

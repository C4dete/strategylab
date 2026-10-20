import type { CSSProperties } from 'react'
import { identidade } from './identidade'
import './correlacao.css'

/**
 * Selo da estratégia no conjunto: quadrado com a letra (A = principal) na cor dela. É o vocabulário único usado no seletor,
 * no painel de desempenho, nos gráficos e na tabela. A letra garante a leitura sem depender da cor.
 */
export function Selo({ i, titulo }: { i: number; titulo?: string }) {
  const id = identidade(i)
  return (
    <span
      className={`selo ${id.repetida ? 'selo--repetida' : ''}`}
      style={{ '--cor': id.cor } as CSSProperties}
      title={titulo}
      aria-hidden
    >
      {id.letra}
    </span>
  )
}

/** Nome da estratégia com o selo, para listas e tabelas. */
export function NomeComSelo({ i, nome, principal }: { i: number; nome: string; principal?: boolean }) {
  return (
    <span className="nome-selo">
      <Selo i={i} />
      <span className="nome-selo__nome">{nome}</span>
      {principal && <span className="nome-selo__tag">principal</span>}
      <span className="sr-only"> (estratégia {identidade(i).letra})</span>
    </span>
  )
}

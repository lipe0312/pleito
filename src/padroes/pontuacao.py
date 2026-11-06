from __future__ import annotations

from src.padroes.configuracao import ConfiguracaoPadroes


def violacoes_de_pontuacao(config: ConfiguracaoPadroes, texto: str) -> list[str]:
    violacoes = []
    if not texto.rstrip().endswith(config.pontuacao.terminador_bullet):
        violacoes.append("terminador")
    proibidos = config.pontuacao.proibidos
    violacoes += [f"proibido {caractere}" for caractere in proibidos if caractere in texto]
    return violacoes

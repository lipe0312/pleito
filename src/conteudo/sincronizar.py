from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from src.coletor.conformidade import Limitador
from src.config import ambiente
from src.conteudo.arquivo import ler_blocos, ler_inventario
from src.conteudo.calculo import ProjetoLido, calcular_sugestoes
from src.conteudo.configuracao import ConfiguracaoConteudo, configuracao_conteudo
from src.conteudo.leitor import Leitor, LeituraRecusada, LimiteDeRequisicoes
from src.conteudo.sincronizacao import (
    ConfiguracaoSincronizacao,
    FonteGithub,
    PaginaPortfolio,
    configuracao_sincronizacao,
)
from src.conteudo.sugestoes import (
    ProjetoSugerido,
    Sugestoes,
    caminho_sugestoes,
    carregar_sugestoes,
    gravar_sugestoes,
)
from src.conteudo.tecnologias import (
    descricao_sem_instrucao,
    extrair_tecnologias,
    texto_da_pagina,
)

NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


class ErroDeSincronizacao(Exception):
    pass


class RepositorioApi(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str | None = None
    topics: list[str] = []
    homepage: str | None = None
    pushed_at: str | None = None
    fork: bool = False
    archived: bool = False
    private: bool = False
    language: str | None = None


def _repositorio_valido(item: object, fonte: FonteGithub) -> RepositorioApi:
    repo = RepositorioApi.model_validate(item)
    if not re.fullmatch(fonte.nome_repositorio_padrao, repo.name) or not repo.name.strip("."):
        raise ValueError("nome de repositorio invalido")
    topics = [t for t in repo.topics if re.fullmatch(fonte.topic_padrao, t)]
    return repo.model_copy(update={"topics": topics[: fonte.topics_max]})


def _identificador(prefixo: str, nome: str) -> str:
    return f"{prefixo}_{NAO_ALFANUMERICO.sub('_', nome.lower()).strip('_')}"


def _url_publica(texto: str | None) -> str | None:
    return texto if texto and texto.startswith(("https://", "http://")) else None


def _listar_repositorios(
    leitor: Leitor, config: ConfiguracaoSincronizacao, avisos: list[str]
) -> tuple[list[RepositorioApi], bool]:
    fonte = config.github
    repositorios: list[RepositorioApi] = []
    for pagina in range(1, fonte.paginas_max + 1):
        url = (
            f"{fonte.api}/users/{fonte.usuario}/repos"
            f"?per_page={fonte.por_pagina}&page={pagina}&sort=pushed"
        )
        try:
            resposta = leitor.obter(
                url, fonte.dominios, fonte.respeitar_robots, fonte.cabecalho_json
            )
            itens = resposta.json() if resposta.status_code == 200 else None
        except (LeituraRecusada, httpx.HTTPError, ValueError) as erro:
            raise ErroDeSincronizacao(f"listagem do GitHub falhou: {erro}") from erro
        if not isinstance(itens, list):
            raise ErroDeSincronizacao(f"GitHub respondeu {resposta.status_code} na listagem")
        for item in itens:
            try:
                repositorios.append(_repositorio_valido(item, fonte))
            except (ValidationError, ValueError):
                avisos.append("repositorio com nome ou formato invalido ignorado")
        if len(itens) < fonte.por_pagina:
            return repositorios, True
    avisos.append(f"listagem cortada em {fonte.paginas_max} paginas")
    return repositorios, False


def _detalhes(
    leitor: Leitor, config: ConfiguracaoSincronizacao, nome: str
) -> tuple[list[str], str]:
    fonte = config.github
    base = f"{fonte.api}/repos/{fonte.usuario}/{nome}"
    resposta = leitor.obter(
        f"{base}/languages", fonte.dominios, fonte.respeitar_robots, fonte.cabecalho_json
    )
    bruto = resposta.json() if resposta.status_code == 200 else {}
    linguagens = [k for k in bruto if isinstance(k, str) and len(k) <= fonte.linguagem_max_chars]
    resposta = leitor.obter(
        f"{base}/readme", fonte.dominios, fonte.respeitar_robots, fonte.cabecalho_readme
    )
    readme = resposta.text[: fonte.readme_max_chars] if resposta.status_code == 200 else ""
    return linguagens, readme


def _ler_github(
    leitor: Leitor, config: ConfiguracaoSincronizacao, avisos: list[str]
) -> tuple[list[ProjetoLido], dict[str, bool], bool]:
    fonte = config.github
    repositorios, completo = _listar_repositorios(leitor, config, avisos)
    vistos = {r.name.lower(): r.archived for r in repositorios if not r.private}
    lidos: list[ProjetoLido] = []
    for repo in repositorios:
        if repo.private or (repo.fork and fonte.ignorar_fork):
            continue
        if repo.archived and fonte.ignorar_arquivado:
            continue
        try:
            linguagens, readme = _detalhes(leitor, config, repo.name)
        except LimiteDeRequisicoes as erro:
            avisos.append(str(erro))
            return lidos, vistos, False
        except (LeituraRecusada, httpx.HTTPError, ValueError) as erro:
            avisos.append(f"detalhes de {repo.name} nao lidos: {erro}")
            linguagens, readme = [], ""
        todas = sorted({*linguagens, *([repo.language] if repo.language else [])})
        projeto = ProjetoSugerido(
            id=_identificador(config.prefixo_id_projeto, repo.name),
            nome=repo.name,
            url=f"{fonte.url_publica}/{fonte.usuario}/{repo.name}",
            descricao=descricao_sem_instrucao(
                repo.description or "", config.padroes_instrucao, config.descricao_max_chars
            )
            or repo.name,
            topics=repo.topics,
            linguagens=todas,
            homepage=_url_publica(repo.homepage),
            pushed_at=repo.pushed_at,
        )
        evidencias = extrair_tecnologias(config, todas, repo.topics, readme, "github")
        lidos.append(ProjetoLido(projeto, "github", evidencias))
    return lidos, vistos, completo


def _ler_pagina(
    leitor: Leitor, config: ConfiguracaoSincronizacao, pagina: PaginaPortfolio
) -> ProjetoLido | None:
    fonte = config.portfolio
    resposta = leitor.obter(pagina.url, fonte.dominios, fonte.respeitar_robots)
    tipo = resposta.headers.get("content-type", "").split(";")[0].strip().lower()
    if resposta.status_code != 200 or tipo not in config.tipos_conteudo_aceitos:
        return None
    texto, descricao = texto_da_pagina(resposta.text, fonte.pagina_max_chars)
    projeto = ProjetoSugerido(
        id=_identificador(config.prefixo_id_projeto, pagina.nome),
        nome=pagina.nome,
        url=pagina.url,
        descricao=descricao_sem_instrucao(
            descricao, config.padroes_instrucao, config.descricao_max_chars
        )
        or pagina.nome,
    )
    return ProjetoLido(
        projeto, "portfolio", extrair_tecnologias(config, [], [], texto, "portfolio")
    )


def _ler_portfolio(
    leitor: Leitor, config: ConfiguracaoSincronizacao, avisos: list[str]
) -> tuple[list[ProjetoLido], bool]:
    lidos: list[ProjetoLido] = []
    for pagina in config.portfolio.paginas:
        try:
            lido = _ler_pagina(leitor, config, pagina)
        except LimiteDeRequisicoes as erro:
            avisos.append(str(erro))
            return lidos, False
        except (LeituraRecusada, httpx.HTTPError, ValueError) as erro:
            avisos.append(f"pagina {pagina.nome} nao lida: {erro}")
            continue
        if lido is None:
            avisos.append(f"pagina {pagina.nome} sem texto aceito")
        else:
            lidos.append(lido)
    return lidos, True


def sincronizar(
    config: ConfiguracaoSincronizacao,
    conteudo: ConfiguracaoConteudo,
    pasta_dados: Path,
    client: httpx.Client,
    limitador: Limitador,
    agora: datetime,
) -> Sugestoes:
    caminho_sugestoes(pasta_dados, conteudo, config)
    blocos = ler_blocos(pasta_dados, conteudo)
    inventario = ler_inventario(pasta_dados, conteudo)
    anteriores = carregar_sugestoes(pasta_dados, conteudo, config)
    leitor = Leitor(client, limitador, config.requisicoes_max, config.resposta_max_bytes)
    avisos: list[str] = []
    lidos, vistos, completo = _ler_github(leitor, config, avisos)
    paginas, portfolio_completo = _ler_portfolio(leitor, config, avisos)
    resultado = calcular_sugestoes(
        config,
        [*lidos, *paginas],
        vistos,
        blocos,
        inventario,
        anteriores,
        completo and portfolio_completo,
        avisos,
        agora,
    )
    gravar_sugestoes(resultado, pasta_dados, conteudo, config)
    return resultado


def main() -> None:
    env = ambiente()
    config = configuracao_sincronizacao()
    client = httpx.Client(
        timeout=env.timeout, headers={"User-Agent": env.user_agent}, follow_redirects=False
    )
    try:
        resultado = sincronizar(
            config,
            configuracao_conteudo(),
            env.dados,
            client,
            Limitador(env.rate_limit_rps),
            datetime.now(UTC),
        )
    except (ErroDeSincronizacao, ValueError) as erro:
        print(f"sincronizacao recusada: {erro}", file=sys.stderr)
        raise SystemExit(1) from erro
    finally:
        client.close()
    pendentes = [s for s in resultado.sugestoes if s.status == "pendente"]
    print(f"{len(pendentes)} sugestoes pendentes de {len(resultado.sugestoes)}")
    for aviso in resultado.avisos:
        print(f"aviso: {aviso}", file=sys.stderr)
    print(f"gravado em {env.dados / configuracao_conteudo().subpasta / config.arquivo_sugestoes}")
    print("revise com: make conteudo-aprovar ARGS=--listar")


if __name__ == "__main__":
    main()

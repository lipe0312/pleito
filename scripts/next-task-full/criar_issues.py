from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from backlog import carregar_backlog, ler_json, mapear_issues, ordem

ROTULOS = {
    "ready": ("0E8A16", "criterios fechados, pode entrar no fluxo next-task-full"),
    "in-progress": ("FBCA04", "frente aberta num worktree"),
    "blocked": ("B60205", "espera decisao ou credencial fora do backlog"),
    "manual": ("5319E7", "so o Filipe faz; o agente nunca executa"),
    "decisao": ("D93F0B", "tem decisao de produto antes de implementar"),
    "seguranca": ("B60205", "toca credencial ou regra de seguranca"),
}
COR_FASE = "C5DEF5"
COR_AREA = "BFD4F2"


def gh(*argumentos: str) -> str:
    resultado = subprocess.run(("gh", *argumentos), capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(resultado.stderr.strip())
    return resultado.stdout.strip()


def frase(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def numero_da_url(url: str) -> int:
    return int(re.search(r"/issues/(\d+)$", url).group(1))


def ordem_topologica(registros: dict[str, dict]) -> list[str]:
    visitados: list[str] = []
    marcados: set[str] = set()

    def visitar(chave: str) -> None:
        if chave in marcados or chave not in registros:
            return
        marcados.add(chave)
        for dependencia in sorted(registros[chave]["depende"], key=ordem):
            visitar(dependencia)
        visitados.append(chave)

    for chave in sorted(registros, key=lambda c: (registros[c].get("fase", 99), ordem(c))):
        visitar(chave)
    return visitados


def linha_dependencia(chave: str, registros: dict[str, dict], numeros: dict[str, int]) -> str:
    titulo = registros[chave]["titulo"]
    numero = numeros.get(chave)
    return f"- #{numero} {chave} {titulo}" if numero else f"- {chave} {titulo}"


def corpo_item(item: dict, fases: dict, registros: dict, numeros: dict[str, int]) -> str:
    fase = fases.get(item["fase"], fases.get(str(item["fase"]), {}))
    partes = [
        "## Por quê",
        f"Fase {item['fase']}: {fase.get('objetivo', '')}."
        + (f" {item['nota']}." if item.get("nota") else ""),
        "",
        "## O que o Filipe passa a ver",
        frase(item.get("ve") or fase.get("ve", "")) + ".",
        "",
        "## Critérios de aceite",
        *[f"- [ ] {criterio}" for criterio in item["criterios"]],
        "",
        "## Fora do escopo",
        frase(item.get("fora") or "nada além dos critérios") + ".",
        "",
    ]
    if item.get("decisao"):
        partes += [
            "## Decisão",
            f"{item['decisao']} Respondida na rodada da `next-task-full`;"
            " com `--rec` vale a recomendação.",
            "",
        ]
    dependencias = [linha_dependencia(d, registros, numeros) for d in item["depende"]]
    partes += [
        "## Depende de",
        *(dependencias or ["Nada: pode começar."]),
        "",
        "## Ficha",
        f"zona `{item['zona']}` · toca {', '.join(item['toca'])} · modelo `{item['modelo']}`"
        f" · migration {'sim' if item['schema'] else 'não'}",
        f"Rodar: `/next-task-full {item['id']}`",
        "",
        f"backlog: {item['id']}",
    ]
    return "\n".join(partes) + "\n"


def corpo_manual(manual: dict, registros: dict, numeros: dict[str, int]) -> str:
    dependencias = [linha_dependencia(d, registros, numeros) for d in manual["depende"]]
    partes = [
        "## Por quê",
        frase(manual["porque"]) + ".",
        "",
        "## Como fazer",
        *[f"{indice}. {frase(passo)}" for indice, passo in enumerate(manual["como"], start=1)],
        "",
        "## Pronto quando",
        frase(manual["pronto"]) + ".",
        "",
        "## Depende de",
        *(dependencias or ["Nada: pode fazer agora."]),
        "",
        "Item manual: o agente nunca executa. Feche a issue quando terminar;"
        " o painel do backlog passa a contá-lo como feito.",
        "",
        f"backlog: {manual['id']}",
    ]
    return "\n".join(partes) + "\n"


def rotulos_do_item(item: dict) -> list[str]:
    rotulos = ["ready", f"fase:{item['fase']}", f"area:{item['zona']}"]
    if item.get("decisao"):
        rotulos.append("decisao")
    if {"seguranca", "credencial"} & set(item["toca"]):
        rotulos.append("seguranca")
    return rotulos


def garantir_rotulos(nomes: set[str]) -> None:
    for nome in sorted(nomes):
        if nome in ROTULOS:
            cor, descricao = ROTULOS[nome]
        elif nome.startswith("fase:"):
            cor, descricao = COR_FASE, f"fase {nome.split(':', 1)[1]} do plano direcionado"
        else:
            cor, descricao = COR_AREA, f"zona {nome.split(':', 1)[1]} do backlog"
        gh("label", "create", nome, "--color", cor, "--description", descricao, "--force")


def escrever_corpo(corpo: str) -> str:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", prefix="pleito-issue-", delete=False, encoding="utf-8"
    ) as arquivo:
        arquivo.write(corpo)
        return arquivo.name


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    reescrever = sys.argv[sys.argv.index("--reescrever") + 1] if "--reescrever" in sys.argv else ""
    backlog = carregar_backlog()
    repo = backlog["repo"]
    fases = backlog.get("fases", {})
    itens = {i["id"]: i for i in backlog["itens"]}
    manuais = {m["id"]: m for m in backlog.get("manuais", [])}
    registros = {**itens, **manuais}

    issues = [
        i
        for i in ler_json(
            "gh", "api", "--paginate", f"repos/{repo}/issues?state=all&per_page=100", "--jq", ".[]"
        )
        if "pull_request" not in i
    ]
    por_id, _ = mapear_issues(issues, set(registros))
    numeros = {chave: issue["number"] for chave, issue in por_id.items()}

    def corpo(chave: str) -> str:
        if chave in itens:
            return corpo_item(itens[chave], fases, registros, numeros)
        return corpo_manual(manuais[chave], registros, numeros)

    def rotulos(chave: str) -> list[str]:
        return rotulos_do_item(itens[chave]) if chave in itens else ["manual"]

    if reescrever:
        numero = numeros.get(reescrever)
        if not numero:
            raise SystemExit(f"{reescrever} nao tem issue")
        if aplicar:
            garantir_rotulos(set(rotulos(reescrever)))
            caminho = escrever_corpo(corpo(reescrever))
            gh(
                "issue",
                "edit",
                str(numero),
                "-R",
                repo,
                "--title",
                registros[reescrever]["titulo"],
                "--body-file",
                caminho,
                "--add-label",
                ",".join(rotulos(reescrever)),
            )
            Path(caminho).unlink()
        print(f"{'reescrita' if aplicar else '(dry) reescreveria'}: #{numero} {reescrever}")
        return

    faltam = [c for c in ordem_topologica(itens) + ordem_topologica(manuais) if c not in numeros]
    if not faltam:
        print("nenhuma issue a criar")
        return
    if aplicar:
        garantir_rotulos({r for chave in faltam for r in rotulos(chave)})
    for chave in faltam:
        if not aplicar:
            print(
                f"(dry) criaria: {chave} [{','.join(rotulos(chave))}] {registros[chave]['titulo']}"
            )
            continue
        caminho = escrever_corpo(corpo(chave))
        url = gh(
            "issue",
            "create",
            "-R",
            repo,
            "--title",
            registros[chave]["titulo"],
            "--label",
            ",".join(rotulos(chave)),
            "--body-file",
            caminho,
        )
        Path(caminho).unlink()
        numeros[chave] = numero_da_url(url)
        print(f"criada: #{numeros[chave]} {chave} {registros[chave]['titulo']}")


if __name__ == "__main__":
    main()

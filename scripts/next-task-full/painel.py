from __future__ import annotations

import json
import re
import sys

from backlog import (
    Frente,
    calcular_ondas,
    carregar_backlog,
    concluida,
    ler_json,
    mapear_issues,
    ordem,
    rodar,
)

FRENTES_PADRAO = 3


def argumento(nome: str, padrao: int) -> int:
    if nome in sys.argv:
        return int(sys.argv[sys.argv.index(nome) + 1])
    return padrao


def main() -> None:
    backlog = carregar_backlog()
    itens = {item["id"]: item for item in backlog["itens"]}
    manuais = {m["id"]: m for m in backlog.get("manuais", [])}
    repo = backlog.get("repo") or rodar(
        "gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"
    )
    frentes = argumento("--frentes", FRENTES_PADRAO)

    issues = [
        i
        for i in ler_json(
            "gh", "api", "--paginate", f"repos/{repo}/issues?state=all&per_page=100", "--jq", ".[]"
        )
        if "pull_request" not in i
    ]
    issue_por_id, avulsas = mapear_issues(issues, set(itens) | set(manuais))
    concluidos = {chave for chave, issue in issue_por_id.items() if concluida(issue)}

    def rotulos(issue: dict) -> list[str]:
        return [r["name"] for r in issue.get("labels", [])]

    def zona_avulsa(issue: dict) -> str:
        return next((r.split(":", 1)[1] for r in rotulos(issue) if r.startswith("area:")), "outra")

    numero_para_chave = {issue["number"]: chave for chave, issue in issue_por_id.items()}
    numero_para_chave.update({issue["number"]: f"#{issue['number']}" for issue in avulsas})

    def frente(numero: int, origem: str, schema: bool) -> dict:
        chave = numero_para_chave.get(numero, f"#{numero}")
        item = itens.get(chave)
        zona = (
            item["zona"]
            if item
            else next((zona_avulsa(i) for i in avulsas if i["number"] == numero), "outra")
        )
        return {
            "chave": chave,
            "numero": numero,
            "origem": origem,
            "zona": zona,
            "schema": schema or bool(item and item["schema"]),
        }

    ocupadas: dict[int, dict] = {}
    for pr in ler_json("gh", "api", f"repos/{repo}/pulls?state=open&per_page=50"):
        alvo = re.search(r"Closes #(\d+)", pr.get("body") or "", re.IGNORECASE) or re.search(
            r"/(\d+)-", pr["head"]["ref"]
        )
        numero = int(alvo.group(1)) if alvo else 0
        arquivos = rodar(
            "gh",
            "api",
            f"repos/{repo}/pulls/{pr['number']}/files?per_page=100",
            "--jq",
            ".[].filename",
        ).splitlines()
        ocupadas[numero] = frente(
            numero, f"PR#{pr['number']}", any(a.startswith("db/") for a in arquivos)
        )
    for linha in rodar("git", "worktree", "list", "--porcelain").splitlines():
        achado = re.search(r"/\.claude/worktrees/feat-(\d+)$", linha)
        if achado and int(achado.group(1)) not in ocupadas:
            ocupadas[int(achado.group(1))] = frente(int(achado.group(1)), "worktree", False)
    for issue in issues:
        if (
            issue["state"] == "open"
            and "in-progress" in rotulos(issue)
            and issue["number"] not in ocupadas
        ):
            ocupadas[issue["number"]] = frente(issue["number"], "in-progress", False)

    chaves_ocupadas = {f["chave"] for f in ocupadas.values()}
    zonas_ocupadas = {f["zona"]: f["chave"] for f in ocupadas.values()}
    migracao_aberta = [f["chave"] for f in ocupadas.values() if f["schema"]]

    livres, bloqueadas = [], []
    for item_id in sorted(itens, key=ordem):
        item = itens[item_id]
        if item_id in concluidos or item_id in chaves_ocupadas:
            continue
        faltam = [d for d in item["depende"] if d not in concluidos]
        if faltam:
            bloqueadas.append({"id": item_id, "espera": faltam})
            continue
        conflitos = []
        if item["zona"] in zonas_ocupadas:
            conflitos.append(zonas_ocupadas[item["zona"]])
        if item["schema"] and migracao_aberta:
            conflitos.extend(migracao_aberta)
        issue = issue_por_id.get(item_id)
        livres.append(
            {
                "id": item_id,
                "issue": issue["number"] if issue else None,
                "fase": item["fase"],
                "zona": item["zona"],
                "schema": item["schema"],
                "modelo": item["modelo"],
                "decisao": item.get("decisao", ""),
                "nota": item.get("nota", ""),
                "paralelo": "ok" if not conflitos else "espera " + ",".join(sorted(set(conflitos))),
                "titulo": item["titulo"],
            }
        )
    for issue in avulsas:
        if (
            issue["number"] in ocupadas
            or "ready" not in rotulos(issue)
            or "blocked" in rotulos(issue)
            or "manual" in rotulos(issue)
        ):
            continue
        zona = zona_avulsa(issue)
        livres.append(
            {
                "id": f"#{issue['number']}",
                "issue": issue["number"],
                "fase": 99,
                "zona": zona,
                "schema": False,
                "modelo": "-",
                "decisao": "",
                "nota": "",
                "paralelo": "ok"
                if zona not in zonas_ocupadas
                else f"espera {zonas_ocupadas[zona]}",
                "titulo": issue["title"],
            }
        )
    livres.sort(key=lambda f: (f["paralelo"] != "ok", f["fase"], ordem(f["id"])))

    sugestao, zonas_usadas, schema_usado = [], set(zonas_ocupadas), bool(migracao_aberta)
    for livre in livres:
        if (
            len(sugestao) + len(ocupadas) >= frentes
            or livre["paralelo"] != "ok"
            or livre["decisao"]
        ):
            continue
        if livre["zona"] in zonas_usadas or (livre["schema"] and schema_usado):
            continue
        sugestao.append(livre["id"])
        zonas_usadas.add(livre["zona"])
        schema_usado = schema_usado or livre["schema"]

    manuais_prontos, manuais_esperando = [], []
    for manual_id in sorted(manuais, key=ordem):
        if manual_id in concluidos:
            continue
        manual = manuais[manual_id]
        issue = issue_por_id.get(manual_id)
        faltam = [d for d in manual["depende"] if d not in concluidos]
        registro = {
            "id": manual_id,
            "issue": issue["number"] if issue else None,
            "titulo": manual["titulo"],
            "espera": faltam,
        }
        (manuais_esperando if faltam else manuais_prontos).append(registro)

    plano = calcular_ondas(
        itens,
        concluidos,
        [
            Frente(f["chave"], f["zona"], f["schema"])
            for f in ocupadas.values()
            if f["chave"] in itens
        ],
        frentes,
    )

    if "--json" in sys.argv:
        print(
            json.dumps(
                {
                    "ocupadas": list(ocupadas.values()),
                    "migracao_aberta": migracao_aberta,
                    "livres": livres,
                    "bloqueadas": bloqueadas,
                    "sugestao": sugestao,
                    "manuais": manuais_prontos,
                    "manuais_esperando": manuais_esperando,
                    "concluidos": sorted(concluidos, key=ordem),
                    "ondas": plano.ondas,
                    "sem_onda": plano.sem_onda,
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return

    def com_issue(chave: str) -> str:
        issue = issue_por_id.get(chave)
        return f"{chave} #{issue['number']}" if issue else f"{chave} (sem issue)"

    if "--ondas" in sys.argv:
        em_curso = [f["chave"] for f in ocupadas.values()]
        print("EM ANDAMENTO:", " · ".join(em_curso) or "nada")
        for indice, onda in enumerate(plano.ondas, start=1):
            partes = []
            for item_id in onda:
                espera = [d for d in itens[item_id]["depende"] if d not in concluidos]
                marca = " ⛔decisao" if itens[item_id].get("decisao") else ""
                marca += " +migration" if itens[item_id]["schema"] else ""
                sufixo = f" (←{'+'.join(espera)})" if espera else ""
                partes.append(f"{com_issue(item_id)}{marca}{sufixo}")
            print(f"ONDA {indice}:", " · ".join(partes) or "(frentes ocupadas)")
        if plano.sem_onda:
            print(
                "SEM ONDA:",
                " · ".join(f"{i}←{'+'.join(d) or '?'}" for i, d in plano.sem_onda.items()),
            )
        print(
            "MANUAIS DO FILIPE:",
            " · ".join(f"{com_issue(m['id'])} {m['titulo']}" for m in manuais_prontos) or "nenhum",
        )
        return

    print(
        "EM ANDAMENTO:",
        " · ".join(
            f"{f['chave']} {f['origem']} [{f['zona']}]{' +migration' if f['schema'] else ''}"
            for f in ocupadas.values()
        )
        or "nada",
    )
    print("MIGRATION ABERTA:", ", ".join(migracao_aberta) or "nenhuma")
    print("CONCLUIDOS:", " ".join(sorted(concluidos, key=ordem)) or "nenhum")
    print("LIVRES (paralelo ok primeiro, depois fase):")
    for f in livres:
        marcas = " schema" if f["schema"] else ""
        marcas += " ⛔decisao" if f["decisao"] else ""
        numero = f"#{f['issue']}" if f["issue"] else "sem issue"
        paralelo = "∥ ok" if f["paralelo"] == "ok" else "⚠ " + f["paralelo"]
        colunas = (f["id"], numero, f"fase {f['fase']}", f["zona"], paralelo)
        print("\t".join((*colunas, f["modelo"] + marcas, f["titulo"])))
    if not livres:
        print("(nenhum: backlog vazio)")
    print(
        "BLOQUEADAS:",
        " · ".join(f"{b['id']}←{'+'.join(b['espera'])}" for b in bloqueadas) or "nenhuma",
    )
    print("SUGESTAO PARALELA:", ", ".join(sugestao) or "nenhuma")
    print(
        "MANUAIS DO FILIPE:",
        " · ".join(f"{com_issue(m['id'])} {m['titulo']}" for m in manuais_prontos) or "nenhum",
    )
    if manuais_esperando:
        print(
            "MANUAIS DEPOIS:",
            " · ".join(f"{m['id']}←{'+'.join(m['espera'])}" for m in manuais_esperando),
        )


if __name__ == "__main__":
    main()

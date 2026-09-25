from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from viabilidade.baseline import extrair_bases, validar_tex
from viabilidade.config import RAIZ, ambiente
from viabilidade.contratos import VagaBruta
from viabilidade.eda import perfilar, renderizar_markdown
from viabilidade.ingest import registro
from viabilidade.veredito import Consolidado

SAIDA = RAIZ / "dados" / "viabilidade"


def _serializar(vaga: VagaBruta) -> dict:
    return {
        "fonte": vaga.fonte,
        "id_externo": vaga.id_externo,
        "url": vaga.url,
        "titulo": vaga.titulo,
        "empresa": vaga.empresa,
        "local": vaga.local,
        "pais": vaga.pais,
        "senioridade": vaga.senioridade.value,
        "modelo": vaga.modelo.value,
        "publicada_em": vaga.publicada_em.isoformat() if vaga.publicada_em else None,
        "coletada_em": vaga.coletada_em.isoformat(),
        "hash_conteudo": vaga.hash_conteudo,
        "completude": round(vaga.completude, 3),
        "campos_ausentes": list(vaga.campos_ausentes),
        "descricao": vaga.descricao,
    }


def cmd_ingest(args: argparse.Namespace) -> int:
    fontes = registro()
    alvos = args.fontes or sorted(fontes)
    consolidado = Consolidado()
    SAIDA.mkdir(parents=True, exist_ok=True)
    todas: list[VagaBruta] = []

    for slug in alvos:
        if slug not in fontes:
            print(f"fonte desconhecida: {slug}", file=sys.stderr)
            return 2
        coletor = fontes[slug]()
        resultado = coletor.coletar(args.limite)
        coletor.fechar()
        consolidado.registrar_coleta(resultado)
        todas.extend(resultado.vagas)
        print(f"{slug:14s} {resultado.veredito().value:16s} vagas={len(resultado.vagas):3d} "
              f"completude={resultado.completude_media:.0%} "
              f"erro={resultado.erro or chr(45)}")

    bruto = SAIDA / "vagas.jsonl"
    with bruto.open("w", encoding="utf-8") as fh:
        for vaga in todas:
            fh.write(json.dumps(_serializar(vaga), ensure_ascii=False) + "\n")

    consolidado.salvar_json(SAIDA / "ingest.json")
    print(f"\n{len(todas)} vagas em {bruto}")
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    destino = RAIZ / "templates"
    bases = extrair_bases(destino=destino if args.escrever else None)
    consolidado = Consolidado()
    for idioma, registro_base in bases.items():
        resultado = validar_tex(idioma, registro_base["tex"], guardar_em=SAIDA / "baseline")
        consolidado.baseline[idioma] = resultado.veredito()
        consolidado.detalhes[f"baseline.{idioma}"] = {
            "compilou": resultado.compilou,
            "paginas": resultado.paginas,
            "overfull": resultado.overfull_relevantes,
            "latex_perigoso": resultado.latex_perigoso,
            "log_erro": resultado.log_erro,
            "correcoes_aplicadas": registro_base["correcoes"],
            "pdf": resultado.pdf,
        }
        print(
            f"{idioma} {resultado.veredito().value:16s} paginas={resultado.paginas} "
            f"overfull={len(resultado.overfull_relevantes)} "
            f"correcoes={len(registro_base['correcoes'])}"
        )
    consolidado.salvar_json(SAIDA / "baseline.json")
    return 0


def cmd_egress(args: argparse.Namespace) -> int:
    from viabilidade.egress import executar_fluxo

    env = ambiente()
    if env.egress_modo != "dry_run" and not env.submit_real_autorizado:
        print("modo submit_real sem token de autorizacao, abortado", file=sys.stderr)
        return 3
    resultado = executar_fluxo(args.url, Path(args.pdf), respostas={})
    destino = resultado.salvar(SAIDA / "egress" / f"{args.plataforma}.json")
    print(f"modo={resultado.modo} veredito={resultado.veredito().value}")
    for etapa, ok in resultado.etapas.items():
        print(f"  {etapa:24s} {'ok' if ok else 'nao'}")
    print(f"campos detectados: {len(resultado.campos_detectados)}")
    print(f"evidencia em {destino}")
    return 0


def cmd_eda(args: argparse.Namespace) -> int:
    from viabilidade.contratos import ModeloTrabalho, Senioridade

    bruto = SAIDA / "vagas.jsonl"
    if not bruto.exists():
        print(f"rode 'viabilidade ingest' primeiro, {bruto} nao existe", file=sys.stderr)
        return 2
    vagas = []
    with bruto.open(encoding="utf-8") as fh:
        for linha in fh:
            d = json.loads(linha)
            vagas.append(
                VagaBruta(
                    fonte=d["fonte"],
                    id_externo=d["id_externo"],
                    url=d["url"],
                    titulo=d["titulo"],
                    empresa=d["empresa"],
                    descricao=d.get("descricao", ""),
                    local=d.get("local", ""),
                    pais=d.get("pais", ""),
                    senioridade=Senioridade(d["senioridade"]),
                    modelo=ModeloTrabalho(d["modelo"]),
                )
            )
    perfil = perfilar(vagas)
    markdown = renderizar_markdown(perfil)
    destino = RAIZ / "docs" / "eda.md"
    destino.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"gravado em {destino}")
    return 0


def cmd_veredito(args: argparse.Namespace) -> int:
    consolidado = Consolidado()
    for nome, chave in (("ingest", "ingest"), ("baseline", "baseline"), ("egress", "egress")):
        caminho = SAIDA / f"{nome}.json"
        if not caminho.exists():
            continue
        payload = json.loads(caminho.read_text(encoding="utf-8"))
        from viabilidade.contratos import Veredito

        getattr(consolidado, chave).update(
            {k: Veredito(v) for k, v in payload.get(chave, {}).items()}
        )
        consolidado.detalhes.update(payload.get("detalhes", {}))

    destino = RAIZ / "docs" / "viabilidade.md"
    destino.write_text(consolidado.markdown(), encoding="utf-8")
    consolidado.salvar_json(SAIDA / "veredito.json")
    print(consolidado.markdown())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="viabilidade")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("ingest")
    p.add_argument("fontes", nargs="*")
    p.add_argument("--limite", type=int, default=40)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("baseline")
    p.add_argument("--escrever", action="store_true")
    p.set_defaults(func=cmd_baseline)

    p = sub.add_parser("egress")
    p.add_argument("url")
    p.add_argument("--pdf", required=True)
    p.add_argument("--plataforma", default="gupy")
    p.set_defaults(func=cmd_egress)

    p = sub.add_parser("eda")
    p.set_defaults(func=cmd_eda)

    p = sub.add_parser("veredito")
    p.set_defaults(func=cmd_veredito)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

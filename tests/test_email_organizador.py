from __future__ import annotations

import base64
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from src.config import RAIZ, carregar
from src.email.cursor import Cursor, gravar_cursor, ler_cursor
from src.email.modelo import Etapa
from src.email.organizador import configuracao_organizacao, rodada
from src.email.rotulos import RotuloAusente, resolver_rotulos

AGORA = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
CAIXA = carregar("emails")["gmail"]["rotulo_caixa_entrada"]
NOMES = carregar("rotulos")


NOMES_DA_CONTA = [*NOMES["etapas"].values(), *NOMES["outros"].values(), "Pessoal"]


def _id_ficticio(nome: str) -> str:
    return f"Label_{NOMES_DA_CONTA.index(nome) + 100}"


def _rotulos_da_conta() -> list[dict]:
    return [{"id": _id_ficticio(nome), "name": nome} for nome in NOMES_DA_CONTA]


def _id_da_etapa(etapa: Etapa) -> str:
    return _id_ficticio(NOMES["etapas"][etapa.value])


def _b64(texto: str) -> str:
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def mensagem(
    identificador: str,
    remetente: str,
    assunto: str,
    corpo: str = "",
    autenticacao: str | list[str] = "mx.exemplo; dmarc=pass",
    reply_to: str | None = None,
    rotulos: list[str] | None = None,
) -> dict:
    cabecalhos = [{"name": "From", "value": remetente}, {"name": "Subject", "value": assunto}]
    for valor in [autenticacao] if isinstance(autenticacao, str) else autenticacao:
        cabecalhos.append({"name": "Authentication-Results", "value": valor})
    if reply_to:
        cabecalhos.append({"name": "Reply-To", "value": reply_to})
    return {
        "id": identificador,
        "threadId": f"t-{identificador}",
        "labelIds": rotulos if rotulos is not None else [CAIXA, "UNREAD"],
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": cabecalhos,
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>ignorado</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64(corpo)}},
            ],
        },
    }


class GmailFalso:
    def __init__(self, mensagens: list[dict], historico: list[list[str]] | None = None) -> None:
        self.mensagens = {m["id"]: m for m in mensagens}
        self.paginas = historico
        self.history_atual = "900"
        self.perfil_history = "500"
        self.contas_rotulos = _rotulos_da_conta()
        self.chamadas: list[tuple] = []
        self.historico_expirado = False

    def rotulos(self) -> list[dict]:
        self.chamadas.append(("rotulos",))
        return self.contas_rotulos

    def perfil(self) -> dict:
        self.chamadas.append(("perfil",))
        return {"historyId": self.perfil_history}

    def listar(self, consulta: str, maximo: int) -> list[dict]:
        self.chamadas.append(("listar", consulta, maximo))
        return [{"id": i} for i in self.mensagens]

    def historico(self, inicio: str, rotulo: str, pagina: str | None = None) -> dict:
        self.chamadas.append(("historico", inicio, rotulo, pagina))
        if self.historico_expirado:
            raise httpx.HTTPStatusError(
                "expirado",
                request=httpx.Request("GET", "https://gmail.falso/history"),
                response=httpx.Response(404),
            )
        indice = int(pagina or 0)
        ids = self.paginas[indice]
        resposta = {
            "historyId": self.history_atual,
            "history": [{"messagesAdded": [{"message": {"id": i}} for i in ids]}],
        }
        if indice + 1 < len(self.paginas):
            resposta["nextPageToken"] = str(indice + 1)
        return resposta

    def ler(self, identificador: str) -> dict:
        self.chamadas.append(("ler", identificador))
        return self.mensagens[identificador]

    def rotular(self, identificador: str, adicionar: list[str], remover: list[str]) -> dict:
        self.chamadas.append(("rotular", identificador, tuple(adicionar), tuple(remover)))
        return {}

    def arquivar(self, identificador: str) -> dict:
        self.chamadas.append(("arquivar", identificador))
        return {}

    def rotuladas(self) -> dict[str, tuple[str, ...]]:
        return {c[1]: c[2] for c in self.chamadas if c[0] == "rotular"}

    def arquivadas(self) -> list[str]:
        return [c[1] for c in self.chamadas if c[0] == "arquivar"]


@pytest.fixture
def cfg(tmp_path: Path):
    return configuracao_organizacao(caminho_cursor=tmp_path / "estado" / "cursor.json")


GUPY = "Gupy <no-reply@gupy.com.br>"


def test_resolve_rotulos_pelo_nome_do_config():
    resolvidos = resolver_rotulos(GmailFalso([]))
    for etapa in Etapa:
        assert resolvidos[etapa] == _id_da_etapa(etapa)


def test_rotulo_ausente_na_conta_interrompe_antes_de_mexer(cfg):
    gmail = GmailFalso([mensagem("m1", GUPY, "Convite para entrevista")])
    gmail.contas_rotulos = [r for r in gmail.contas_rotulos if "Suspeitos" not in r["name"]]
    with pytest.raises(RotuloAusente):
        rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {} and gmail.arquivadas() == []


def test_config_de_rotulos_so_tem_nomes_e_src_nao_fixa_id():
    texto = (RAIZ / "config" / "rotulos.yaml").read_text(encoding="utf-8")
    assert not re.search(r"Label_[0-9]", texto)
    fixos = [
        caminho
        for caminho in (RAIZ / "src").rglob("*.py")
        if re.search(r"[\"']Label_[0-9]", caminho.read_text(encoding="utf-8"))
    ]
    assert fixos == []


def test_email_reconhecido_vai_para_a_pasta_da_etapa_e_sai_da_caixa(cfg):
    gmail = GmailFalso([mensagem("m1", GUPY, "Convite para entrevista")])
    resumo = rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.ENTREVISTA),)}
    assert gmail.arquivadas() == ["m1"]
    assert resumo.por_etapa == {Etapa.ENTREVISTA: 1}


def test_remetente_forjado_com_dominio_real_e_dmarc_falho_vai_para_suspeitos(cfg):
    gmail = GmailFalso(
        [mensagem("m1", GUPY, "Proposta de emprego", autenticacao="mx.exemplo; dmarc=fail")]
    )
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.SUSPEITO),)}
    assert gmail.arquivadas() == ["m1"]


def test_dominio_que_imita_plataforma_vai_para_suspeitos(cfg):
    gmail = GmailFalso([mensagem("m1", "Vagas <rh@gupy-vagas.com>", "Ola")])
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.SUSPEITO),)}


def test_nome_de_exibicao_de_plataforma_com_dominio_alheio_vai_para_suspeitos(cfg):
    gmail = GmailFalso([mensagem("m1", "Gupy <atendimento@exemplo.net>", "Atualizacao")])
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.SUSPEITO),)}


def test_reply_to_desviado_vai_para_suspeitos(cfg):
    gmail = GmailFalso(
        [mensagem("m1", GUPY, "Convite para entrevista", reply_to="rh@exemplo.net")]
    )
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.SUSPEITO),)}


def test_cabecalho_de_autenticacao_plantado_abaixo_do_do_provedor_nao_salva_o_forjado(cfg):
    gmail = GmailFalso(
        [
            mensagem(
                "m1",
                GUPY,
                "Proposta de emprego",
                autenticacao=["mx.exemplo; dmarc=fail", "mx.exemplo; dmarc=pass"],
            )
        ]
    )
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.SUSPEITO),)}


def test_email_pessoal_sem_padrao_fica_intocado_na_caixa(cfg):
    gmail = GmailFalso(
        [mensagem("m1", "Amiga <amiga@exemplo.org>", "Almoco sabado?", autenticacao="")]
    )
    resumo = rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {} and gmail.arquivadas() == []
    assert resumo.ignoradas == 1


def test_alerta_de_vaga_da_plataforma_de_alertas_fica_para_o_coletor(cfg):
    gmail = GmailFalso(
        [mensagem("m1", "LinkedIn <jobalerts-noreply@linkedin.com>", "Novas vagas para voce")]
    )
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {} and gmail.arquivadas() == []


def test_padrao_de_etapa_de_remetente_desconhecido_vai_para_classificar(cfg):
    gmail = GmailFalso([mensagem("m1", "RH <rh@empresa.exemplo>", "Convite para entrevista")])
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.CLASSIFICAR),)}


def test_mudanca_de_etapa_remove_o_rotulo_anterior(cfg):
    anterior = _id_da_etapa(Etapa.APLICADA)
    gmail = GmailFalso(
        [mensagem("m1", GUPY, "Convite para entrevista", rotulos=[CAIXA, anterior, "Label_9"])]
    )
    rodada(gmail, cfg, AGORA)
    chamada = next(c for c in gmail.chamadas if c[0] == "rotular")
    assert chamada == ("rotular", "m1", (_id_da_etapa(Etapa.ENTREVISTA),), (anterior,))


def test_mensagem_que_ja_saiu_da_caixa_nao_e_mexida(cfg):
    gmail = GmailFalso([mensagem("m1", GUPY, "Convite para entrevista", rotulos=["UNREAD"])])
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {} and gmail.arquivadas() == []


def test_etapa_configurada_para_ficar_na_caixa_e_rotulada_sem_arquivar(tmp_path):
    cfg = configuracao_organizacao(
        caminho_cursor=tmp_path / "c.json", manter_na_caixa=["entrevista"]
    )
    gmail = GmailFalso([mensagem("m1", GUPY, "Convite para entrevista")])
    rodada(gmail, cfg, AGORA)
    assert gmail.rotuladas() == {"m1": (_id_da_etapa(Etapa.ENTREVISTA),)}
    assert gmail.arquivadas() == []


def test_primeira_rodada_lista_pela_consulta_e_guarda_o_history_do_perfil(cfg):
    gmail = GmailFalso([mensagem("m1", GUPY, "Convite para entrevista")])
    rodada(gmail, cfg, AGORA)
    nomes = [c[0] for c in gmail.chamadas]
    assert nomes.index("perfil") < nomes.index("listar")
    assert ("listar", cfg.consulta_inicial, cfg.lote_inicial) in gmail.chamadas
    assert ler_cursor(cfg.caminho_cursor) == Cursor("500", AGORA)


def test_rodada_seguinte_le_so_o_historico_desde_o_cursor(cfg):
    gravar_cursor(cfg.caminho_cursor, Cursor("700", AGORA - cfg.intervalo))
    gmail = GmailFalso(
        [
            mensagem("m1", GUPY, "Convite para entrevista"),
            mensagem("m2", GUPY, "Proposta de emprego"),
        ],
        historico=[["m1"], ["m2", "m1"]],
    )
    resumo = rodada(gmail, cfg, AGORA)
    historicos = [c for c in gmail.chamadas if c[0] == "historico"]
    assert historicos == [("historico", "700", CAIXA, None), ("historico", "700", CAIXA, "1")]
    assert not [c for c in gmail.chamadas if c[0] in {"listar", "perfil"}]
    assert [c[1] for c in gmail.chamadas if c[0] == "ler"] == ["m1", "m2"]
    assert resumo.por_etapa == {Etapa.ENTREVISTA: 1, Etapa.OFERTA: 1}
    assert ler_cursor(cfg.caminho_cursor) == Cursor("900", AGORA)


def test_rodada_antes_do_intervalo_nao_chama_o_gmail(cfg):
    gravar_cursor(
        cfg.caminho_cursor, Cursor("700", AGORA - cfg.intervalo + timedelta(minutes=1))
    )
    gmail = GmailFalso([], historico=[[]])
    resumo = rodada(gmail, cfg, AGORA)
    assert resumo.adiada and gmail.chamadas == []


def test_forcar_ignora_o_intervalo(cfg):
    gravar_cursor(cfg.caminho_cursor, Cursor("700", AGORA))
    gmail = GmailFalso([], historico=[[]])
    resumo = rodada(gmail, cfg, AGORA, forcar=True)
    assert not resumo.adiada and ("historico", "700", CAIXA, None) in gmail.chamadas


def test_intervalo_vem_do_config_de_limites(cfg):
    minutos = carregar("limites")["horarios"]["email_intervalo_min"]
    assert cfg.intervalo == timedelta(minutes=minutos)


def test_historico_expirado_recomeca_pela_consulta_inicial(cfg):
    gravar_cursor(cfg.caminho_cursor, Cursor("1", AGORA - cfg.intervalo))
    gmail = GmailFalso([mensagem("m1", GUPY, "Convite para entrevista")], historico=[[]])
    gmail.historico_expirado = True
    rodada(gmail, cfg, AGORA)
    assert ("listar", cfg.consulta_inicial, cfg.lote_inicial) in gmail.chamadas
    assert ler_cursor(cfg.caminho_cursor) == Cursor("500", AGORA)


def test_falha_no_meio_nao_avanca_o_cursor(cfg):
    gravar_cursor(cfg.caminho_cursor, Cursor("700", AGORA - cfg.intervalo))
    gmail = GmailFalso([mensagem("m1", GUPY, "Convite para entrevista")], historico=[["m1"]])

    def quebrar(*_argumentos):
        raise httpx.ConnectError("sem rede")

    gmail.arquivar = quebrar
    with pytest.raises(httpx.ConnectError):
        rodada(gmail, cfg, AGORA)
    assert ler_cursor(cfg.caminho_cursor) == Cursor("700", AGORA - cfg.intervalo)


def test_rodada_so_rotula_e_arquiva_nunca_outra_escrita(cfg):
    gmail = GmailFalso(
        [
            mensagem("m1", GUPY, "Convite para entrevista"),
            mensagem("m2", "Vagas <rh@gupy-vagas.com>", "Ola"),
            mensagem("m3", "Amiga <amiga@exemplo.org>", "Almoco", autenticacao=""),
        ]
    )
    rodada(gmail, cfg, AGORA)
    usadas = {c[0] for c in gmail.chamadas}
    assert usadas <= {"rotulos", "perfil", "listar", "historico", "ler", "rotular", "arquivar"}

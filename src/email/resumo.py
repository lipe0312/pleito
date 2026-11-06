from __future__ import annotations

import argparse
import base64
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses

import httpx

from src.config import carregar
from src.email.configuracao import ConfiguracaoGmail, configuracao_gmail
from src.email.gmail import ClienteGmail
from src.email.keychain import Keychain
from src.email.oauth import ClienteOAuth
from src.email.rotulos import RotuloAusente

PADRAO_DESTINO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
QUEBRAS = ("\r", "\n")
CABECALHOS_DE_DESTINATARIO = ("Cc", "Bcc", "Resent-To", "Resent-Cc", "Resent-Bcc")


class DestinoRecusado(ValueError):
    pass


class CabecalhoRecusado(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ConfiguracaoResumo:
    variavel_destino: str
    rotulo: str
    assunto: str
    corpo_nenhuma: str
    corpo_uma: str
    corpo_varias: str


def _exigir_cabecalho(valor: str) -> str:
    if not valor.strip() or any(quebra in valor for quebra in QUEBRAS):
        raise CabecalhoRecusado("assunto vazio ou com quebra de linha")
    return valor


def configuracao_resumo(dados: dict | None = None) -> ConfiguracaoResumo:
    bruto = dados if dados is not None else carregar("resumo")
    corpo = bruto["corpo"]
    return ConfiguracaoResumo(
        variavel_destino=bruto["variavel_destino"],
        rotulo=carregar("rotulos")["outros"][bruto["rotulo"]],
        assunto=_exigir_cabecalho(bruto["assunto"]),
        corpo_nenhuma=corpo["nenhuma"],
        corpo_uma=corpo["uma"],
        corpo_varias=corpo["varias"],
    )


def destino_do_ambiente(variaveis: Mapping[str, str], variavel: str) -> str:
    destino = variaveis.get(variavel, "")
    if not PADRAO_DESTINO.fullmatch(destino):
        raise DestinoRecusado(
            f"{variavel} ausente ou invalido: defina um so endereco no .env, sem nome nem virgula"
        )
    return destino


def corpo_do_dia(prontas: int, cfg: ConfiguracaoResumo) -> str:
    if prontas < 0:
        raise ValueError("contagem de vagas prontas negativa")
    if prontas == 0:
        return cfg.corpo_nenhuma
    if prontas == 1:
        return cfg.corpo_uma
    return cfg.corpo_varias.format(total=prontas)


def exigir_so_o_destino(mensagem: EmailMessage, destino: str) -> None:
    if any(mensagem.get_all(nome) for nome in CABECALHOS_DE_DESTINATARIO):
        raise DestinoRecusado("mensagem com destinatario alem do destino")
    valores = mensagem.get_all("To") or []
    enderecos = getaddresses([str(valor) for valor in valores])
    if len(valores) != 1 or len(enderecos) != 1:
        raise DestinoRecusado("mensagem precisa de um unico destinatario")
    if enderecos[0][1].lower() != destino.lower():
        raise DestinoRecusado("destinatario diferente do destino configurado")


def montar(variaveis: Mapping[str, str], cfg: ConfiguracaoResumo, prontas: int) -> EmailMessage:
    destino = destino_do_ambiente(variaveis, cfg.variavel_destino)
    mensagem = EmailMessage(policy=policy.SMTP)
    mensagem["To"] = destino
    mensagem["Subject"] = cfg.assunto
    mensagem.set_content(corpo_do_dia(prontas, cfg))
    exigir_so_o_destino(mensagem, destino)
    return mensagem


def _serializar_conferido(mensagem: EmailMessage, destino: str) -> str:
    exigir_so_o_destino(mensagem, destino)
    bruto = mensagem.as_bytes(policy=policy.SMTP)
    exigir_so_o_destino(BytesParser(policy=policy.default).parsebytes(bruto), destino)
    return base64.urlsafe_b64encode(bruto).decode("ascii")


class ClienteResumo(ClienteGmail):
    def __init__(
        self,
        cfg: ConfiguracaoGmail,
        chave,
        http: httpx.Client,
        variaveis: Mapping[str, str],
        resumo: ConfiguracaoResumo,
        cliente_oauth: ClienteOAuth | None = None,
    ) -> None:
        super().__init__(cfg, chave, http, cliente_oauth)
        self._variaveis = variaveis
        self._resumo = resumo

    def enviar_resumo(self, mensagem: EmailMessage) -> str:
        destino = destino_do_ambiente(self._variaveis, self._resumo.variavel_destino)
        bruto = _serializar_conferido(mensagem, destino)
        rotulo = self._id_do_rotulo(self._resumo.rotulo)
        enviada = self._requisitar("POST", "messages/send", json={"raw": bruto})
        self.rotular(enviada["id"], [rotulo], [])
        return enviada["id"]

    def _id_do_rotulo(self, nome: str) -> str:
        for rotulo in self.rotulos():
            if rotulo["name"] == nome:
                return rotulo["id"]
        raise RotuloAusente(f"rotulo {nome!r} nao existe na conta")


def _cliente_real(variaveis: Mapping[str, str], http: httpx.Client) -> ClienteResumo:
    cfg = configuracao_gmail()
    chave = Keychain(cfg.keychain_binario, cfg.keychain_servico, cfg.keychain_conta)
    return ClienteResumo(cfg, chave, http, variaveis, configuracao_resumo())


def _contagem(valor: str) -> int:
    total = int(valor)
    if total < 0:
        raise argparse.ArgumentTypeError("contagem negativa")
    return total


def executar(
    argumentos: list[str],
    variaveis: Mapping[str, str],
    criar_cliente: Callable[[Mapping[str, str], httpx.Client], ClienteResumo] = _cliente_real,
) -> int:
    leitor = argparse.ArgumentParser(description="Monta e envia o resumo diario")
    leitor.add_argument("--prontas", type=_contagem, default=0)
    leitor.add_argument("--enviar", action="store_true")
    opcoes = leitor.parse_args(argumentos)
    cfg = configuracao_resumo()
    try:
        mensagem = montar(variaveis, cfg, opcoes.prontas)
    except (DestinoRecusado, CabecalhoRecusado) as erro:
        print(f"resumo recusado: {erro}", file=sys.stderr)
        return 2
    if not opcoes.enviar:
        print(f"dry_run para {cfg.variavel_destino} com rotulo {cfg.rotulo}")
        print(f"assunto: {cfg.assunto}")
        print(mensagem.get_content().strip())
        return 0
    with httpx.Client() as http:
        identificador = criar_cliente(variaveis, http).enviar_resumo(mensagem)
    print(f"resumo enviado com rotulo {cfg.rotulo}: {identificador}")
    return 0


def main() -> None:
    raise SystemExit(executar(sys.argv[1:], os.environ))


if __name__ == "__main__":
    main()

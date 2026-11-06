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


class RotuloNaoAplicado(RuntimeError):
    def __init__(self, mensagem: str, identificador: str) -> None:
        super().__init__(mensagem)
        self.identificador = identificador


@dataclass(frozen=True, slots=True)
class ConfiguracaoResumo:
    variavel_destino: str
    rotulo: str
    assunto: str
    corpo_nenhuma: str
    corpo_uma: str
    corpo_varias: str
    comando: Mapping[str, str]
    erros: Mapping[str, str]


def _exigir_cabecalho(valor: str, erro: str) -> str:
    if not valor.strip() or any(quebra in valor for quebra in QUEBRAS):
        raise CabecalhoRecusado(erro)
    return valor


def _rotulo_configurado(chave: str, erro: str) -> str:
    outros = carregar("rotulos").get("outros", {})
    if chave not in outros:
        raise RotuloAusente(erro.format(chave=chave))
    return outros[chave]


def configuracao_resumo(dados: dict | None = None) -> ConfiguracaoResumo:
    bruto = dados if dados is not None else carregar("resumo")
    corpo = bruto["corpo"]
    erros = dict(bruto["erros"])
    return ConfiguracaoResumo(
        variavel_destino=bruto["variavel_destino"],
        rotulo=_rotulo_configurado(bruto["rotulo"], erros["rotulo_sem_chave"]),
        assunto=_exigir_cabecalho(bruto["assunto"], erros["assunto"]),
        corpo_nenhuma=corpo["nenhuma"],
        corpo_uma=corpo["uma"],
        corpo_varias=corpo["varias"],
        comando=dict(bruto["comando"]),
        erros=erros,
    )


def destino_do_ambiente(variaveis: Mapping[str, str], cfg: ConfiguracaoResumo) -> str:
    destino = variaveis.get(cfg.variavel_destino, "")
    if not PADRAO_DESTINO.fullmatch(destino):
        raise DestinoRecusado(cfg.erros["destino_invalido"].format(variavel=cfg.variavel_destino))
    return destino


def corpo_do_dia(prontas: int, cfg: ConfiguracaoResumo) -> str:
    if prontas < 0:
        raise ValueError(cfg.erros["contagem"])
    if prontas == 0:
        return cfg.corpo_nenhuma
    if prontas == 1:
        return cfg.corpo_uma
    return cfg.corpo_varias.format(total=prontas)


def exigir_so_o_destino(mensagem: EmailMessage, destino: str, cfg: ConfiguracaoResumo) -> None:
    variavel = cfg.variavel_destino
    if any(mensagem.get_all(nome) for nome in CABECALHOS_DE_DESTINATARIO):
        raise DestinoRecusado(cfg.erros["destino_extra"].format(variavel=variavel))
    valores = mensagem.get_all("To") or []
    enderecos = getaddresses([str(valor) for valor in valores])
    if len(valores) != 1 or len(enderecos) != 1:
        raise DestinoRecusado(cfg.erros["destino_unico"])
    if enderecos[0][1].lower() != destino.lower():
        raise DestinoRecusado(cfg.erros["destino_diferente"].format(variavel=variavel))


def montar(variaveis: Mapping[str, str], cfg: ConfiguracaoResumo, prontas: int) -> EmailMessage:
    destino = destino_do_ambiente(variaveis, cfg)
    mensagem = EmailMessage(policy=policy.SMTP)
    mensagem["To"] = destino
    mensagem["Subject"] = cfg.assunto
    mensagem.set_content(corpo_do_dia(prontas, cfg))
    exigir_so_o_destino(mensagem, destino, cfg)
    return mensagem


def _serializar_conferido(mensagem: EmailMessage, destino: str, cfg: ConfiguracaoResumo) -> str:
    exigir_so_o_destino(mensagem, destino, cfg)
    bruto = mensagem.as_bytes(policy=policy.SMTP)
    exigir_so_o_destino(BytesParser(policy=policy.default).parsebytes(bruto), destino, cfg)
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
        destino = destino_do_ambiente(self._variaveis, self._resumo)
        bruto = _serializar_conferido(mensagem, destino, self._resumo)
        rotulo = self._id_do_rotulo(self._resumo.rotulo)
        identificador = self._requisitar("POST", "messages/send", json={"raw": bruto})["id"]
        try:
            self.rotular(identificador, [rotulo], [])
        except (httpx.HTTPError, ValueError) as erro:
            texto = self._resumo.erros["rotulo_nao_aplicado"].format(
                id=identificador, rotulo=self._resumo.rotulo
            )
            raise RotuloNaoAplicado(texto, identificador) from erro
        return identificador

    def _id_do_rotulo(self, nome: str) -> str:
        for rotulo in self.rotulos():
            if rotulo["name"] == nome:
                return rotulo["id"]
        raise RotuloAusente(self._resumo.erros["rotulo_ausente"].format(nome=nome))


def _cliente_real(variaveis: Mapping[str, str], http: httpx.Client) -> ClienteResumo:
    cfg = configuracao_gmail()
    chave = Keychain(cfg.keychain_binario, cfg.keychain_servico, cfg.keychain_conta)
    return ClienteResumo(cfg, chave, http, variaveis, configuracao_resumo())


def _leitor(cfg: ConfiguracaoResumo) -> argparse.ArgumentParser:
    def contagem(valor: str) -> int:
        total = int(valor)
        if total < 0:
            raise argparse.ArgumentTypeError(cfg.erros["contagem"])
        return total

    leitor = argparse.ArgumentParser(description=cfg.comando["descricao"])
    leitor.add_argument("--prontas", type=contagem, default=0)
    leitor.add_argument("--enviar", action="store_true")
    return leitor


def _recusar(cfg: ConfiguracaoResumo, erro: Exception, codigo: int) -> int:
    print(cfg.comando["recusado"].format(erro=erro), file=sys.stderr)
    return codigo


def executar(
    argumentos: list[str],
    variaveis: Mapping[str, str],
    criar_cliente: Callable[[Mapping[str, str], httpx.Client], ClienteResumo] = _cliente_real,
) -> int:
    cfg = configuracao_resumo()
    opcoes = _leitor(cfg).parse_args(argumentos)
    try:
        mensagem = montar(variaveis, cfg, opcoes.prontas)
    except (DestinoRecusado, CabecalhoRecusado) as erro:
        return _recusar(cfg, erro, 2)
    if not opcoes.enviar:
        print(cfg.comando["simulacao"].format(variavel=cfg.variavel_destino, rotulo=cfg.rotulo))
        print(cfg.comando["assunto"].format(assunto=cfg.assunto))
        print(mensagem.get_content().strip())
        return 0
    try:
        with httpx.Client() as http:
            identificador = criar_cliente(variaveis, http).enviar_resumo(mensagem)
    except (DestinoRecusado, RotuloAusente) as erro:
        return _recusar(cfg, erro, 2)
    except RotuloNaoAplicado as erro:
        print(erro, file=sys.stderr)
        return 3
    print(cfg.comando["enviado"].format(rotulo=cfg.rotulo, id=identificador))
    return 0


def main() -> None:
    raise SystemExit(executar(sys.argv[1:], os.environ))


if __name__ == "__main__":
    main()

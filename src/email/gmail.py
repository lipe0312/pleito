from __future__ import annotations

import re

import httpx

from src.email.configuracao import ConfiguracaoGmail
from src.email.oauth import ClienteOAuth, ler_cliente, renovar

PADRAO_IDENTIFICADOR = re.compile(r"[A-Za-z0-9_-]+")


class IdentificadorInvalido(ValueError):
    pass


def _exigir_identificador(identificador: str) -> str:
    if not PADRAO_IDENTIFICADOR.fullmatch(identificador):
        raise IdentificadorInvalido("identificador de mensagem invalido")
    return identificador


class ClienteGmail:
    def __init__(
        self,
        cfg: ConfiguracaoGmail,
        chave,
        http: httpx.Client,
        cliente_oauth: ClienteOAuth | None = None,
    ) -> None:
        self._cfg = cfg
        self._chave = chave
        self._http = http
        self._cliente_oauth = cliente_oauth
        self._acesso: str | None = None

    def listar(self, consulta: str, maximo: int) -> list[dict]:
        resposta = self._requisitar(
            "GET", "messages", params={"q": consulta, "maxResults": maximo}
        )
        return resposta.get("messages", [])

    def ler(self, identificador: str) -> dict:
        return self._requisitar("GET", f"messages/{_exigir_identificador(identificador)}")

    def rotular(self, identificador: str, adicionar: list[str], remover: list[str]) -> dict:
        caminho = f"messages/{_exigir_identificador(identificador)}/modify"
        corpo = {"addLabelIds": list(adicionar), "removeLabelIds": list(remover)}
        return self._requisitar("POST", caminho, json=corpo)

    def arquivar(self, identificador: str) -> dict:
        return self.rotular(identificador, [], [self._cfg.rotulo_caixa_entrada])

    def _renovar_acesso(self) -> str:
        if self._cliente_oauth is None:
            self._cliente_oauth = ler_cliente(self._cfg.caminho_cliente)
        refresh_token = self._chave.ler()
        tokens = renovar(self._cfg, self._cliente_oauth, refresh_token, self._http)
        novo_refresh = tokens.get("refresh_token")
        if novo_refresh and novo_refresh != refresh_token:
            self._chave.gravar(novo_refresh)
        self._acesso = tokens["access_token"]
        return self._acesso

    def _requisitar(self, metodo: str, caminho: str, **opcoes) -> dict:
        acesso = self._acesso or self._renovar_acesso()
        resposta = self._pedir(metodo, caminho, acesso, opcoes)
        if resposta.status_code == httpx.codes.UNAUTHORIZED:
            resposta = self._pedir(metodo, caminho, self._renovar_acesso(), opcoes)
        resposta.raise_for_status()
        return resposta.json()

    def _pedir(
        self, metodo: str, caminho: str, acesso: str, opcoes: dict
    ) -> httpx.Response:
        return self._http.request(
            metodo,
            f"{self._cfg.url_api}/{caminho}",
            headers={"Authorization": f"Bearer {acesso}"},
            timeout=self._cfg.timeout_s,
            **opcoes,
        )

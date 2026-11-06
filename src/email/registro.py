from __future__ import annotations

from src.email.eventos import Politica
from src.email.modelo import Classificacao
from src.email.regras import Regras
from src.email.repositorio import EmailRecebido, ResultadoEvento, gravar_evento
from src.email.vinculo import RegraVinculo, vaga_do_email


class RegistroNoBanco:
    def __init__(
        self,
        conexao,
        politica: Politica | None = None,
        regra: RegraVinculo | None = None,
        configuradas: Regras | None = None,
    ) -> None:
        self.conexao = conexao
        self.politica = politica
        self.regra = regra
        self.configuradas = configuradas

    def gravar(self, recebido: EmailRecebido, classificacao: Classificacao) -> ResultadoEvento:
        with self.conexao.cursor() as cursor:
            vaga_id = vaga_do_email(
                cursor, recebido.email, classificacao, self.regra, self.configuradas
            )
        return gravar_evento(self.conexao, recebido, classificacao, vaga_id, self.politica)

    def confirmar(self) -> None:
        self.conexao.commit()

    def desfazer(self) -> None:
        self.conexao.rollback()

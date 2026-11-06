from __future__ import annotations


class SlotInvalido(ValueError):
    pass


class SlotNaoDeclarado(SlotInvalido):
    pass


class SlotAusente(SlotInvalido):
    pass


class TechForaDoInventario(SlotInvalido):
    pass


class TravadoInvalido(ValueError):
    pass


class TemplateInvalido(ValueError):
    pass


class IdiomaNaoSuportado(ValueError):
    pass


class RespostaDescartada(ValueError):
    pass

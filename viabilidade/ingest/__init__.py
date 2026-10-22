from src.coletor.agregadores import (
    FonteArbeitnow,
    FonteHimalayas,
    FonteJobicy,
    FonteRemoteok,
    FonteRemotive,
    FonteWorkingNomads,
)
from src.coletor.ashby import FonteAshby
from src.coletor.base import Fonte, registrar, registro
from src.coletor.email_alertas import coletar_de_emails, extrair_alerta_linkedin
from src.coletor.greenhouse import FonteGreenhouse
from src.coletor.gupy import FonteGupy
from src.coletor.hackernews import FonteHackerNews
from src.coletor.lever import FonteLever
from src.coletor.rss import FonteJobspresso, FonteWeWorkRemotely
from src.coletor.solides import FonteSolides

__all__ = [
    "Fonte",
    "FonteArbeitnow",
    "FonteAshby",
    "FonteGreenhouse",
    "FonteGupy",
    "FonteHackerNews",
    "FonteHimalayas",
    "FonteJobicy",
    "FonteLever",
    "FonteRemoteok",
    "FonteRemotive",
    "FonteJobspresso",
    "FonteSolides",
    "FonteWeWorkRemotely",
    "FonteWorkingNomads",
    "coletar_de_emails",
    "extrair_alerta_linkedin",
    "registrar",
    "registro",
]

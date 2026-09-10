"""Spider modules for all TAPI-listed sources.

Cada módulo exporta uma factory `build()` que retorna o spider correspondente
(`AggregatorSpider`, `NewsSpider` ou subclasse específica do site). Spiders de
agregadores de alta prioridade (cubo, open100, ace, abstartups, anjos, darwin)
têm selectors próprios; os demais usam os parsers genéricos da base.
"""

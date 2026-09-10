"""Testes dos spiders de alta prioridade com HTML de exemplo offline.

Valida que os selectors específicos de cada fonte são capazes de extrair
startups de listas/cards sem depender de rede (Playwright/HTTP).
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scraper.spiders import (
    cubo,
    open100,
    ace,
    abstartups,
    anjos,
    darwin,
)


def _run(coro):
    return asyncio.run(coro)


class TestCuboSpider:
    def setup_method(self):
        self.spider = cubo.build()

    def test_parse_list_page_extrai_cards_startup(self):
        html = """
        <html><body>
        <div class="startup-card">
          <a href="/startups/fintech-x/"><h3>Fintech X</h3></a>
          <p class="description">Plataforma de crédito para PMEs.</p>
        </div>
        <div class="startup-card">
          <a href="/startup/healthtech-y/"><h3>Healthtech Y</h3></a>
          <p class="description">IA para triagem médica.</p>
        </div>
        </body></html>
        """
        items = _run(self.spider.parse_list_page(html, "https://cubo.itau/startups"))
        names = [i["nome"] for i in items]
        assert "Fintech X" in names
        assert "Healthtech Y" in names
        assert all(i["site"].startswith("https://cubo.itau/") for i in items)


class TestOpen100Spider:
    def setup_method(self):
        self.spider = open100.build()

    def test_parse_list_page_extrai_linhas_da_tabela(self):
        html = """
        <html><body>
        <table><tbody>
        <tr>
          <td><a href="/companies/agro-drones">AgroDrones</a></td>
          <td>Agtech</td>
          <td>Seed</td>
        </tr>
        <tr>
          <td><a href="https://www.openstartups.net/companies/paytech-co">PayTech Co</a></td>
          <td>Fintech</td>
          <td>Série A</td>
        </tr>
        </tbody></table>
        </body></html>
        """
        items = _run(self.spider.parse_list_page(html, "https://www.openstartups.net/ranking"))
        names = [i["nome"] for i in items]
        assert "AgroDrones" in names
        assert "PayTech Co" in names
        assert items[0]["setor"] == "Agtech"


class TestACESpider:
    def setup_method(self):
        self.spider = ace.build()

    def test_parse_list_page_extrai_cards_portfolio(self):
        html = """
        <html><body>
        <div class="portfolio-card">
          <a href="https://acestartups.com.br/portfolio/agroplus/"><h2>AgroPlus</h2></a>
          <p class="description">Soluções de crédito para agronegócio.</p>
        </div>
        <div class="portfolio-card">
          <a href="https://acestartups.com.br/portfolio/edtech/"><h2>EduTech</h2></a>
          <p class="description">Plataforma de ensino adaptativo.</p>
        </div>
        </body></html>
        """
        items = _run(self.spider.parse_list_page(html, "https://acestartups.com.br/portfolio/"))
        names = [i["nome"] for i in items]
        assert "AgroPlus" in names
        assert "EduTech" in names


class TestAbstartupsSpider:
    def setup_method(self):
        self.spider = abstartups.build()

    def test_parse_list_page_extrai_associadas(self):
        html = """
        <html><body>
        <div class="associada-card">
          <a href="https://abstartups.com.br/associadas/inova-pesquisa/"><h3>Inova Pesquisa</h3></a>
          <span class="setor">Healthtech</span>
        </div>
        <div class="associada-card">
          <a href="https://abstartups.com.br/associadas/logbay/"><h3>LogBay</h3></a>
          <span class="setor">Logtech</span>
        </div>
        </body></html>
        """
        items = _run(self.spider.parse_list_page(html, "https://abstartups.com.br/associadas/"))
        names = [i["nome"] for i in items]
        assert "Inova Pesquisa" in names
        assert "LogBay" in names


class TestAnjosSpider:
    def setup_method(self):
        self.spider = anjos.build()

    def test_parse_list_page_extrai_investidas(self):
        html = """
        <html><body>
        <div class="investida-card">
          <a href="https://www.anjosdobrasil.net/investidas/agtech-br/"><h3>AgTech BR</h3></a>
          <span class="setor">Agtech</span>
        </div>
        <div class="investida-card">
          <a href="https://www.anjosdobrasil.net/investidas/healthcare-ai/"><h3>Healthcare AI</h3></a>
          <span class="setor">Healthtech</span>
        </div>
        </body></html>
        """
        items = _run(self.spider.parse_list_page(html, "https://www.anjosdobrasil.net/investidas/"))
        names = [i["nome"] for i in items]
        assert "AgTech BR" in names
        assert "Healthcare AI" in names


class TestDarwinSpider:
    def setup_method(self):
        self.spider = darwin.build()

    def test_parse_list_page_extrai_portfolio(self):
        html = """
        <html><body>
        <div class="portfolio-card">
          <a href="https://www.darwinstartups.com/startup/blue-fintech/"><h3>Blue Fintech</h3></a>
          <p class="description">Pagamentos e banking as a service.</p>
        </div>
        <div class="portfolio-card">
          <a href="https://www.darwinstartups.com/startup/green-agro/"><h3>Green Agro</h3></a>
          <p class="description">Sensores IoT para agricultura.</p>
        </div>
        </body></html>
        """
        items = _run(self.spider.parse_list_page(html, "https://www.darwinstartups.com/portfolio/"))
        names = [i["nome"] for i in items]
        assert "Blue Fintech" in names
        assert "Green Agro" in names
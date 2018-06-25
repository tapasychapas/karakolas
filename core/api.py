#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import re
import sys
import tempfile
from datetime import datetime, timedelta
from urllib.parse import urlencode, urljoin

import bs4
import requests

from .pedido import Pedido
from .productos import ProductorCSV, ProductorHTML

requests.packages.urllib3.disable_warnings()

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)


def next_weekday(weekday):
    d = datetime.now()
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days_ahead)


def cfg(f):
    with open(f) as f:
        l = f.read().strip()
        return l.split(" ")


class Session():

    def __init__(self, root=None):
        self.s = requests.Session()
        self.s.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:54.0) Gecko/20100101 Firefox/54.0',
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Expires": "Thu, 01 Jan 1970 00:00:00 GMT",
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            "X-Requested-With": "XMLHttpRequest"
        }
        self.cookies = None
        self.root = root
        if root:
            self.get(root)

    def get_soup(self):
        self.soup = bs4.BeautifulSoup(self.response.content, "lxml")
        return self.soup

    def get(self, url, **kwargs):
        if self.cookies:
            kwargs["cookies"] = self.cookies
        if self.root:
            url = urljoin(self.root, url)
        self.response = self.s.get(url, verify=False, **kwargs)
        return self.response

    def post(self, url, **kwargs):
        if self.cookies:
            kwargs["cookies"] = self.cookies
        if self.root:
            url = urljoin(self.root, url)
        self.response = self.s.post(url, verify=False, **kwargs)
        return self.response

    def get_link(self, reg):
        l = self.get_soup().find("a", attrs={"href": reg})
        return urljoin(self.response.url, l.attrs["href"])


class Karakolas(Session):

    def __init__(self, user, password, grupo):
        super().__init__("https://karakolas.net")
        self.grupo = grupo
        self.get("https://karakolas.net/user.load/login",
                 cookies=self.s.cookies.get_dict())
        url, data = self.get_form(user=user, password=password)
        self.s.post("https://karakolas.net/user.load/login",
                    files={'name': ('', 'content')}, data=data)

    def get_form(self, user=None, password=None):
        form = self.get_soup().find("form")
        data = {}
        for h in form.select("input"):
            if h.attrs.get("name", None) != None:
                name = h.attrs["name"]
                if user and "username" == name:
                    data[name] = user
                elif password and "password" == name:
                    data[name] = password
                elif "value" in h.attrs:
                    data[name] = h.attrs["value"]
        return form.attrs["action"], data

    def reparto(self, *fechas):
        self.get(
            "https://karakolas.net/gestion_pedidos/gestion_pedidos.load?grupo=" + self.grupo)
        ficheros = []
        for fecha in fechas:
            self.get("https://karakolas.net/gestion_pedidos/exportar_tabla_reparto_fecha.ods?fecha_reparto=" +
                     fecha + "&grupo=" + self.grupo)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ods") as f:
                f.write(self.response.content)
                ficheros.append(f.name)
                print (f.name)
        if len(ficheros) > 0:
            p = Pedido(*ficheros)
            p.fecha = sorted(fechas)[-1]
            return p

    def productores(self):
        self.get("https://karakolas.net/productores/vista_productores.load?grupo=" + self.grupo)
        trs = self.get_soup().findAll("tr")
        self.get("https://karakolas.net/productores/productores_coordinados.load?grupo=" + self.grupo)
        trs = trs + self.get_soup().findAll("tr")
        productores = []
        for tr in trs:
            if "desactivado" in tr.attrs.get("class", []) or tr.find("a") is None:
                continue
            pro = sp.sub(" ",tr.find("td").get_text()).strip()
            if pro.upper() in ("TAPAS&CHAPAS", "ASAMBLEA DE DELEGADAS"):
                continue
            lista = tr.findAll("a")[-1].attrs["href"].replace(".html?", ".load?")
            self.get(lista)
            if "exportar_productos.csv" in lista:
                p = ProductorCSV(pro, self.response)
            else:
                p = ProductorHTML(pro, self.response)
            p.load()
            if len(p.productos)>0:
                print(pro)
                productores.append(p)
        return sorted(productores, key=lambda x: (x.orden, len(x.productos), x.nombre))

    def fechas(self):
        self.get("https://karakolas.net/gestion_pedidos/gestion_pedidos.load?grupo=" + self.grupo)
        h3s = self.get_soup().findAll("h3", text=re.compile("^\s*\d\d?-\d\d?-\d\d\d\d\s*$"))
        h3s = set([h3.get_text().strip() for h3 in h3s])
        fechas = ["-".join(reversed(h3.split("-"))) for h3 in h3s]
        return fechas
        

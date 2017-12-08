#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import re
import sys
import tempfile
from datetime import datetime, timedelta
from fractions import gcd
from functools import reduce
from urllib.parse import urlencode, urljoin

import bs4
import requests
from jinja2 import Environment, FileSystemLoader
from pyexcel_ods import get_data

requests.packages.urllib3.disable_warnings()

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
trim = re.compile(r"\s*\.\s*", re.MULTILINE | re.UNICODE)
peso = re.compile(r"^(.*?)(\d+gr)$", re.MULTILINE | re.UNICODE)


order1 = ["patata", "cebolla", "zanahoria",
          "ajo (", "puerro", "brócoli", "lombarda", "alcachofa", "calabaza"]
order2 = ["tarros", "huevos", "güevos"]


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


def get_cestas(row):
    indices = []
    cestas = []
    for x in range(len(row)):
        c = get_text(row[x])
        if c.startswith("Ud:"):
            cestas.append(int(c[3:]))
            indices.append(x)
    return cestas, indices


def get_text(s):
    return sp.sub(" ", s.replace("_", " ")).strip()

_id_reparto = 0
_id_producto = 0
_id_productor = 0


class Reparto:

    def __init__(self, pedido, cesta, cantidad, unidad_singular="unidad", unidad_plural="unidades"):
        global _id_reparto
        _id_reparto += 1
        self.id_reparto = _id_reparto

        self.pedido = pedido
        self.cesta = cesta
        self.cantidad = cantidad
        self.unidad_singular = unidad_singular
        self.unidad_plural = unidad_plural
        self.tipo = 0
        self.muletilla = None

    def get_str(self):
        if self.mas1 is None:
            s = self.patron % (self.cesta, self.cantidad)
            d = self.cantidad % 1
            if d > 0:
                s += str(d)[1:]
            if self.muletilla:
                s += " " + self.muletilla
            return s
        if self.mas1:
            r = self.patron % (self.cantidad, self.nombre_producto)
            if self.cantidad % 1 != 0:
                r = re.sub(r"^(\s+)\d+", r"\1\b" + str(self.cantidad), r)
            return r
        else:
            return "  " + self.nombre_producto


class Producto:

    def __init__(self, pedido, nombre):
        global _id_producto
        _id_producto += 1
        self.id_producto = _id_producto

        self.pedido = pedido
        self.tipo = 0

        if nombre.startswith("*") and nombre.endswith("*"):
            self.tipo = 1
            nombre = nombre[1:-1].strip()
        nombre = sp.sub(" ", nombre)
        #nombre = trim.sub("",nombre)
        self.nombre = nombre.capitalize()
        self.key = nombre.lower()

        self.cortar = self.key == "calabaza"

        if self.nombre == u"Cuarto de queso de oveja semicurado (600-700 g.)":
            self.nombre = "Queso de oveja semicurado (piezas de 600-700g)"
        elif self.nombre == "Ajo":
            self.nombre = "Ajo (250 grs)"
        elif self.nombre == "Espinaca":
            self.nombre = "Espinaca (manojos de ½ kg)"
        elif self.nombre == "Puerro":
            self.nombre = "Puerro (grupos de 700g)"
            self.tipo = 1
        elif self.nombre == "Tomate frito":
            self.nombre = "Tomate frito (tarros de 300g)"
        elif self.nombre == "Huevos":
            self.nombre = "Media docena de huevos (6)"
        elif self.nombre == "Alubias":
            self.nombre = "Alubias (bolsa 1kg)"
        elif self.nombre == "Queso de pasta blanda":
            self.nombre = "Queso de pasta blanda (pieza de 300g)"
        elif self.tipo == 1:
            self.nombre += " (kg)"

        self.nombre = peso.sub(r"\1 \2", self.nombre)
        self.nombre = sp.sub(" ", self.nombre).strip()

    def order(self):
        n = self.nombre.lower()
        for i in range(len(order1)):
            if order1[i] in n:
                return i
        for i in range(len(order2)):
            if order2[i] in n:
                return i + 1000
        return 999

    def get_count(self):
        repartos = [
            r for r in self.pedido.repartos if r.id_producto == self.id_producto]
        return len(repartos)

    def get_repartos(self):
        repartos = [
            r for r in self.pedido.repartos if r.id_producto == self.id_producto]
        repartos = sorted(repartos, key=lambda r: r.cesta)

        max1 = 0
        max2 = 0
        for r in repartos:
            max1 = max(max1, len(str(r.cesta)))
            max2 = max(max2, len(str(int(r.cantidad))))
        max1 = 2
        patron = "  Cesta %" + str(max1) + "d: %" + str(max2) + "d"

        for r in repartos:
            r.patron = patron
            r.mas1 = None

        return repartos


class Productor:

    def __init__(self, pedido, nombre):
        global _id_productor
        _id_productor += 1
        self.id_productor = _id_productor

        self.pedido = pedido
        self.nombre = nombre.upper()
        if self.nombre.startswith("VEGAN MAIDEN"):
            self.nombre = "VEGAN MAIDEN"
        if self.nombre.startswith("SILVANO "):
            self.nombre = "SILVANO"

    def get_count(self, tipo):
        productos = [p for p in self.pedido.productos if p.id_productor ==
                     self.id_productor and p.tipo == tipo]
        return len(productos)

    def order(self, tipo=None):
        if tipo is None:
            productos = [
                p for p in self.pedido.productos if p.id_productor == self.id_productor]
            return -len(productos)

        cestas = set([r.cesta for r in self.pedido.repartos if r.id_productor ==
                      self.id_productor and r.tipo == tipo])
        repartos = [r for r in self.pedido.repartos if r.id_productor ==
                    self.id_productor and r.tipo == tipo]
        return -len(repartos) - len(cestas)

    def get_productos(self, tipo=None):
        productos = [
            p for p in self.pedido.productos if p.id_productor == self.id_productor]
        if tipo is not None:
            productos = [p for p in productos if p.tipo == tipo]
            productos = sorted(productos, key=lambda p: (
                p.order(), -p.get_count(), p.nombre))
            return productos
        for p in productos:
            total = sum(
                [r.cantidad for r in self.pedido.repartos if r.id_producto == p.id_producto])
            p.total = total
            n = p.nombre.replace(" (*)", "")
            p.albaran = (("%4.1f %s" % (total, n)).replace(".0", " -"))
        productos = sorted(productos, key=lambda p: p.nombre)
        return productos

    def get_cestas(self, tipo):
        repartos = [r for r in self.pedido.repartos if r.id_productor ==
                    self.id_productor and r.tipo == tipo]
        ids_cestas = set([r.cesta for r in repartos])
        width_id = len(str(max(ids_cestas)))
        cestas = [c for c in self.pedido.cestas if c.id_cesta in ids_cestas]
        for c in cestas:
            c.patron = "Cesta %" + str(width_id) + "d"
        return cestas


class Cesta:

    def __init__(self, pedido, id_cesta):
        self.pedido = pedido
        self.id_cesta = id_cesta

    def get_nombre(self):
        return self.patron % self.id_cesta

    def get_repartos(self, id_productor, tipo):
        repartos = [r for r in self.pedido.repartos if r.tipo ==
                    tipo and id_productor == r.id_productor]
        repartos = sorted(repartos, key=lambda r: r.nombre_producto)

        mas1 = False
        max2 = 3
        for r in repartos:
            max2 = max(max2, len(str(int(r.cantidad))))
            if int(r.cantidad) > 1:
                mas1 = True

        patron = "%" + str(max2) + "d %s"

        for r in repartos:
            r.mas1 = mas1
            r.patron = patron

        repartos = [r for r in repartos if r.cesta == self.id_cesta]

        return repartos

    def get_catidades(self):
        repartos = [r for r in self.pedido.repartos if r.cesta == self.id_cesta]
        productos = len(repartos)
        peso = sum([r.cantidad for r in repartos if r.tipo == 1])
        if peso == 0:
            return "Cesta %2d: %2d productos (nada para pesar)" % (self.id_cesta, productos)
        return "Cesta %2d: %2d productos (~ %2d kg)" % (self.id_cesta, productos, peso)


sp = re.compile(r"\s+", re.UNICODE | re.MULTILINE)


class Pedido:

    def __init__(self, *ficheros):
        self.productores = []
        self.productos = []
        self.repartos = []
        self.cestas = []
        self.load(*ficheros)

    def get_productores(self, tipo=None):
        if tipo is None:
            productores = self.productores
        else:
            productores = []
            for p in self.productores:
                if p.get_count(tipo=tipo) > 0:
                    productores.append(p)
        productores = sorted(productores, key=lambda p: (
            p.order(tipo=tipo), p.nombre))
        return productores

    def get_cortes(self):
        cortes = []
        productos = [p for p in self.productos if p.cortar]
        for p in self.productos:
            if p.cortar:
                corte = {}
                corte["producto"] = p
                repartos = [
                    r for r in self.repartos if r.id_producto == p.id_producto]
                cantidades = [r.cantidad for r in repartos]
                corte["total"] = sum(cantidades)
                corte["gcd"] = reduce(gcd, cantidades)
                corte["piezas"] = int(corte["total"] / corte["gcd"])
                corte["trozos"] = []
                for r in repartos:
                    corte["trozos"].append({
                        "cantidad": str(r.cantidad).replace(".0", ""),
                        "pieza": int(r.cantidad / corte["gcd"]),
                        "cesta": r.cesta,
                        "parte": 0
                    })
                corte["total"] = str(corte["total"]).replace(".0", "")
                cortes.append(corte)
        return cortes

    def add_producto(self, producto):
        p = Producto(self, producto)
        p.id_productor = self.productores[-1].id_productor
        n_productor = self.productores[-1].nombre
        if n_productor == "VEGAN MAIDEN":
            p.nombre = p.nombre.split(":")[0]
            p.nombre = re.sub(
                r"\.?( 2x\d+| \d+ unid\.| \(paté de tomates secos\)).*", "", p.nombre)
        elif "SILVANO" in n_productor or n_productor == "EVA - COSMETICA":
            p.nombre = re.sub(r"\(.*", "", p.nombre)
            p.nombre = p.nombre.replace(" muy suave ", " ")
        elif n_productor == "QUESOS ZAMORA":
            p.nombre = re.sub(r"^Queso de ", "", p.nombre).capitalize()
            p.nombre = p.nombre.replace(" (piezas de ", " (p. ")
        p.nombre = re.sub(r"\- (\d+) litros", r"(\1l)", p.nombre)
        if p.nombre == "Media docena de huevos (6)":
            p.nombre = "Media docena de huevos"
        if p.nombre == "Mermelada de cereza ecológica certificada":
            p.nombre = "Mermelada de cereza ecológica"
        self.productos.append(p)

    def add_reparto(self, cesta, cantidad):
        if cantidad and cantidad != "0" and cantidad != "0.0":
            cesta = Reparto(self, cesta, float(cantidad))
            cesta.id_productor = self.productores[-1].id_productor
            cesta.id_producto = self.productos[-1].id_producto
            cesta.tipo = self.productos[-1].tipo
            cesta.nombre_producto = self.productos[-1].nombre
            self.repartos.append(cesta)
            n_productor = self.productores[-1].nombre
            if n_productor == "NARANJAS":
                cajas = int(cesta.cantidad / 10)
                pico = int(cesta.cantidad % 10)
                plural = ""
                if cajas > 1:
                    plural = "s"
                if pico == 0:
                    cesta.muletilla = "(= %s caja%s)" % (cajas, plural)

    def ajustar(self):
        for p in self.productos:
            repartos = p.get_repartos()
            tipo1 = [r for r in repartos if r.tipo == 1]
            if len(tipo1) == 1:
                p.nombre = p.nombre + " (*)"
                p.tipo = 0
                tipo1[0].tipo = 0
            for r in repartos:
                r.nombre_producto = p.nombre
        productores = set([r.id_productor for r in self.repartos])
        productos = set([r.id_producto for r in self.repartos])

        self.productores = [
            p for p in self.productores if p.id_productor in productores]
        self.productos = [
            p for p in self.productos if p.id_producto in productos]
        ids_cestas = sorted(set([r.cesta for r in self.repartos]))
        self.cestas = [Cesta(self, c) for c in ids_cestas]

    def load(self, *ficheros):
        for f in ficheros:
            data = get_data(f)
            for hoja in data.items():
                hoja = hoja[1]
                cestas = None
                indices = None
                productor = None
                for row in hoja:
                    if len(row) == 0:
                        continue
                    c1 = get_text(row[0])
                    if c1 == "COSTE PEDIDO RED":
                        continue
                    if c1 == "TOTAL UNIDAD":
                        productor = None
                        continue
                    if len(row) == 1:
                        productor = Productor(self, c1)
                        self.productores.append(productor)
                        continue
                    if c1 == "PRODUCTO":
                        cestas, indices = get_cestas(row)
                        continue
                    if productor == None or productor.nombre == "CULTIMAR PESCADO":
                        continue
                    if not cestas:
                        continue
                    self.add_producto(c1)
                    for i in range(len(cestas)):
                        r = indices[i]
                        p = get_text(str(row[r]))
                        self.add_reparto(cestas[i], p)
        self.ajustar()


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
        self.get(
            "https://karakolas.net/gestion_pedidos/gestion_pedidos.load?grupo=" + self.grupo)

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
        ficheros = []
        for fecha in fechas:
            self.get("https://karakolas.net/gestion_pedidos/exportar_tabla_reparto_fecha.ods?fecha_reparto=" +
                     fecha + "&grupo=" + self.grupo)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ods") as f:
                f.write(self.response.content)
                ficheros.append(f.name)
        if len(ficheros) > 0:
            p = Pedido(*ficheros)
            p.fecha = sorted(fechas)[-1]
            return p

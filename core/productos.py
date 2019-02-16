#!/usr/bin/python
# -*- coding: utf-8 -*-

import csv
import re
import tempfile

import bs4
import requests
from pyexcel_ods import get_data

from .clean import clean_producto, clean_productor

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
trim = re.compile(r"\s*\.\s*", re.MULTILINE | re.UNICODE)
peso = re.compile(r"^(.*?)(\d+gr)$", re.MULTILINE | re.UNICODE)
ceros = re.compile(r"\.0+$")


class Producto:

    def __init__(self, nombre, precio, descripcion, categoria, productor):
        self.nombre = clean_producto(nombre.strip(), productor)
        precio = ceros.sub("", precio.strip())
        self.precio = int(precio) if precio.isdigit() else float(precio)
        self.descripcion = descripcion.strip()
        self.categoria = categoria.strip()

    def __hash__(self):
        return hash((self.nombre, self.precio))

    def __eq__(self, other):
        return self.nombre == other.nombre and self.precio == self.precio


class Familia:

    def __init__(self, nombre):
        self.nombre = nombre


class Productor:

    def __init__(self, nombre, response):
        self.nombre = clean_productor(nombre)
        self.response = response
        self.productos = set()
        self.orden = 999
        if self.nombre == "SENDA VERDE":
            self.orden = 1
        elif self.nombre == "ECOOPAN":
            self.orden = 2
        elif self.nombre == "DOS CASTAÑOS":
            self.orden = 3
        elif self.nombre == "VEGAN MAIDEN":
            self.orden = 4

    def load(self):
        pass

    def get_productos(self):
        return sorted(self.productos, key=lambda x: (x.nombre, x.descripcion))


class ProductorCSV(Productor):

    def load(self):
        name = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ods") as f:
            f.write(self.response.content)
            name = f.name
        with open(name, 'r') as csvfile:
            spamreader = csv.reader(csvfile, delimiter=',', quotechar='"')
            flag = False
            for row in spamreader:
                if len(row) == 0:
                    continue
                if row[0] == "productoXpedido.nombre":
                    flag = True
                    continue
                if flag:
                    p = Producto(row[0], row[1], row[4], row[8], self.nombre)
                    self.productos.add(p)


class ProductorHTML(Productor):

    def load(self):
        self.soup = bs4.BeautifulSoup(self.response.content, "lxml")
        for tr in self.soup.findAll("tr"):
            tds = tr.findAll("td")
            if len(tds) == 0:
                continue
            row = [td.get_text() for td in tds]
            p = Producto(row[0], row[3], row[1], row[2], self.nombre)
            self.productos.add(p)

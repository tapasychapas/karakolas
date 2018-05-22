#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import re
import tempfile
from datetime import datetime, timedelta
from fractions import gcd
from functools import reduce
from urllib.parse import urlencode, urljoin

import bs4
import requests
from pyexcel_ods import get_data

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
trim = re.compile(r"\s*\.\s*", re.MULTILINE | re.UNICODE)
peso = re.compile(r"^(.*?)(\d+gr)$", re.MULTILINE | re.UNICODE)

def clean_producto(nombre, productor=None):

        nombre = sp.sub(" ", nombre.replace("_", " ")).strip()
        #nombre = trim.sub("",nombre)
        nombre = nombre.capitalize()

        if nombre == u"Cuarto de queso de oveja semicurado (600-700 g.)":
            nombre = "Queso de oveja semicurado (piezas de 600-700g)"
        elif nombre == "Ajo":
            nombre = "Ajo (250 grs)"
        elif nombre == "Espinaca":
            nombre = "Espinaca (manojos de ½ kg)"
        elif nombre == "Tomate frito":
            nombre = "Tomate frito (tarros de 300g)"
        elif nombre == "Huevos":
            nombre = "Media docena de huevos (6)"
        elif nombre == "Alubias":
            nombre = "Alubias (bolsa 1kg)"
        elif nombre == "Queso de pasta blanda":
            nombre = "Queso de pasta blanda (pieza de 300g)"

        nombre = peso.sub(r"\1 \2", nombre)
        nombre = sp.sub(" ", nombre).strip()

        if productor:
            if productor == "VEGAN MAIDEN":
                nombre = nombre.split(":")[0]
                nombre = re.sub(
                    r"\.?( 2x\d+| \d+ unid\.| \(paté de tomates secos\)).*", "", nombre)
            elif "SILVANO" in productor or productor == "EVA - COSMETICA":
                nombre = re.sub(r"\(.*", "", nombre)
                nombre = nombre.replace(" muy suave ", " ")
            elif productor == "QUESOS ZAMORA":
                nombre = re.sub(r"^Queso de ", "", nombre).capitalize()
                nombre = nombre.replace(" (piezas de ", " (p. ")
            nombre = re.sub(r"\- (\d+) litros", r"(\1l)", nombre)
            if nombre == "Media docena de huevos (6)":
                nombre = "Media docena de huevos"
            if nombre == "Mermelada de cereza ecológica certificada":
                nombre = "Mermelada de cereza ecológica"

        return nombre

def clean_productor(nombre):
        nombre = sp.sub(" ", nombre.replace("_", " ")).strip().upper()
        if nombre.startswith("VEGAN MAIDEN"):
            nombre = "VEGAN MAIDEN"
        if nombre.startswith("SILVANO "):
            nombre = "SILVANO"
        return nombre


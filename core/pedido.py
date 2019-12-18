#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from fractions import gcd
from functools import reduce

import bs4
import requests
from pyexcel_ods import get_data

from .clean import clean_producto, clean_productor

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
trim = re.compile(r"\s*\.\s*", re.MULTILINE | re.UNICODE)
peso = re.compile(r"^(.*?)(\d+gr)$", re.MULTILINE | re.UNICODE)

order1 = ["patata", "cebolla", "zanahoria",
          "ajo (", "puerro", "brócoli", "lombarda", "alcachofa", "calabaza"]
order2 = ["tarros", "huevos", "güevos"]


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

    def __init__(self, pedido, nombre, n_productor=None):
        global _id_producto
        _id_producto += 1
        self.id_producto = _id_producto

        self.pedido = pedido
        self.tipo = 0

        if nombre.startswith("*") and nombre.endswith("*"):
            nombre = nombre[1:-1].strip()
            self.tipo = 1

        self.nombre = clean_producto(nombre, productor=n_productor)
        self.key = nombre.lower()
        self.cortar = self.key == "calabaza"

        if self.tipo == 1:
            self.nombre += " (kg)"

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
        self.nombre = clean_productor(nombre)

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
        repartos = [
            r for r in self.pedido.repartos if r.cesta == self.id_cesta]
        productos = len(repartos)
        peso = sum([r.cantidad for r in repartos if r.tipo == 1])
        if peso == 0:
            return "Cesta %2d: %2d productos (nada para pesar)" % (self.id_cesta, productos)
        return "Cesta %2d: %2d productos (~ %2d kg)" % (self.id_cesta, productos, peso)


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
        n_productor = self.productores[-1].nombre
        p = Producto(self, producto, n_productor=n_productor)
        p.id_productor = self.productores[-1].id_productor
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

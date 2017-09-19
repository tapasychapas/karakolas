#!/usr/bin/python
# -*- coding: utf-8 -*-

from pyexcel_ods import get_data
import re
import sys
import requests
import argparse

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
trim = re.compile(r"\s*\.\s*", re.MULTILINE | re.UNICODE)
peso = re.compile(r"^(.*?)(\d+gr)$", re.MULTILINE | re.UNICODE)

parser = argparse.ArgumentParser(description='Pedido del grupo de consumo')
parser.add_argument('--pesar', action='store_true')
parser.add_argument("fichero", nargs='*', help="Fichero de reparto")
args = parser.parse_args()

order1 = ["patata", "cebolla", "zanahoria",
          "ajo (", "puerro", "brócoli", "lombarda", "alcachofa", "calabaza"]
order2 = ["tarros", "huevos", "güevos"]


class Reparto:

    def __init__(self, cesta, cantidad, unidad_singular="unidad", unidad_plural="unidades"):
        self.cesta = cesta
        self.cantidad = cantidad
        self.unidad_singular = unidad_singular
        self.unidad_plural = unidad_plural
        self.tipo = 0
        self.muletilla = None

    def get_srt(self, patron):
        s = patron % (self.cesta, self.cantidad)
        d = self.cantidad % 1
        if d > 0:
            s += str(d)[1:]
        '''
		if self.unidad_singular and self.unidad_plural:
			if self.cantidad==1:
				s+=" "+ self.unidad_singular
			else:
				s+=" "+ self.unidad_plural
		'''
        if self.muletilla:
            s += " " + self.muletilla
        return s


class Producto:

    def __init__(self, nombre, productor):
        self.tipo = 0
        self.productor = productor
        if nombre.startswith("*") and nombre.endswith("*"):
            self.tipo = 1
            nombre = nombre[1:-1].strip()
        nombre = sp.sub(" ", nombre)
        #nombre = trim.sub("",nombre)
        self.nombre = nombre.capitalize()
        self.key = nombre.lower()
        self.repartos = []
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

        self.nombre = peso.sub(r"\1 \2",self.nombre)
        self.nombre = sp.sub(" ",self.nombre).strip()

    def order(self):
        n = self.nombre.lower()
        for i in range(len(order1)):
            if order1[i] in n:
                return i
        for i in range(len(order2)):
            if order2[i] in n:
                return i + 1000
        return 999

    def add(self, cesta, cantidad):
        if cantidad and cantidad != "0" and cantidad != "0.0":
            cesta = Reparto(cesta, float(cantidad))
            cesta.tipo = self.tipo
            self.repartos.append(cesta)
            if self.productor == "NARANJAS":
                cajas = int(cesta.cantidad / 10)
                pico = int(cesta.cantidad % 10)
                plural = ""
                if cajas > 1:
                    plural = "s"
                if pico == 0:
                    cesta.muletilla = "(= " + str(cajas) + \
                        " caja" + plural + ")"
                '''
				elif cajas>0 and pico == 5:
					cesta.muletilla="(= "+str(cajas)+"."+str(pico)+" caja"+plural+")"
				'''

    def vacio(self):
        return len(self.repartos) == 0

    def get_tipo(self, tipo):
        return [p for p in self.repartos if p.tipo == tipo]


class Productor:

    def __init__(self, nombre):
        self.nombre = nombre.upper()
        if self.nombre.startswith("VEGAN MAIDEN"):
            self.nombre = "VEGAN MAIDEN"
        self.productos = []

    def add(self, p):
        p = Producto(p, self.nombre)
        if len(self.productos) == 0 or not self.productos[-1].vacio():
            self.productos.append(p)
        else:
            self.productos[-1] = p

    def get_tipo(self, tipo):
        ptipo = [p for p in self.productos if len(p.get_tipo(tipo)) > 0]
        return sorted(ptipo, key=lambda p: (p.order(), -len(p.get_tipo(tipo)), p.nombre))

    def __str__(self):
        _len = 21
        long = _len - (len(self.nombre) + 2)
        delta = long % 2
        long = int(long / 2)
        txt = self.nombre

        prefix = ('-' * _len)
        r = prefix + '\n'

        if long < 0:
            r += txt
        else:
            r += ('-' * long)
            r += ' ' + txt + ' '
            r += ('-' * (long + delta))
        r += '\n' + prefix
        return r

sp = re.compile(r"\s+", re.UNICODE | re.MULTILINE)


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

productores = []


for f in args.fichero:
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
                productor = Productor(c1)
                productores.append(productor)
                continue
            if c1 == "PRODUCTO":
                cestas, indices = get_cestas(row)
                continue
            if productor == None or productor.nombre == "CULTIMAR PESCADO":
                continue
            if not cestas:
                continue
            productor.add(c1)
            for i in range(len(cestas)):
                r = indices[i]
                p = get_text(str(row[r]))
                productor.productos[-1].add(cestas[i], p)


def show_tipo(tipo):
    for p in productores:
        productos = p.get_tipo(tipo)
        if len(productos) == 0:
            continue
        print (p)
        for d in productos:
            max1 = 0
            max2 = 0
            for c in d.get_tipo(tipo):
                max1 = max(max1,len(str(c.cesta)))
                max2 = max(max2,len(str(int(c.cantidad))))
            max1 = 2
            patron = "  Cesta %" + str(max1) + "d: %" + str(max2) + "d"

            print ("")
            print (d.nombre)
            for c in d.get_tipo(tipo):
                print (c.get_srt(patron))
        print ("")

def show_tipo_por_cesta(tipo):
    for p in productores:
        productos = p.get_tipo(tipo)
        if len(productos) == 0:
            continue
        print (p)

        mas1 = False
        cestas = set()
        max1 = 0
        max2 = 0
        for d in productos:
            for c in d.get_tipo(tipo):
                cestas.add(c.cesta)
                max1 = max(max1,len(str(c.cesta)))
                max2 = max(max2,len(str(int(c.cantidad))))
                if int(c.cantidad)>1:
                    mas1 = True

        patron1 = "Cesta %" + str(max1)+"d"
        patron2 = "  %"+ str(max2)+"d %s"

        for ct in sorted(list(cestas)):
            print ("")
            print (patron1 % ct)
            for d in sorted(productos, key=lambda d: d.nombre):
                for c in d.get_tipo(tipo):
                    if c.cesta == ct:
                        if mas1:
                            print (patron2 % (c.cantidad, d.nombre))
                        else:
                            print ("  "+d.nombre)
        print ("")

def show_cestas():
    cestas = {}
    for p in productores:
        for d in p.productos:
            for c in d.repartos:
                if c.cesta in cestas:
                    cestas[c.cesta]["productos"] = (
                        cestas[c.cesta]["productos"] + 1)
                else:
                    cestas[c.cesta] = {"productos": 1, "peso": 0}
                if c.tipo == 1:
                    cestas[c.cesta]["peso"] = (
                        cestas[c.cesta]["peso"] + c.cantidad)

    minmax = sorted(cestas.keys(), key=lambda i: cestas[i]["productos"])
    for c in sorted(cestas.keys()):  # ,key=lambda i: cestas[i]):
        if cestas[c]["peso"] == 0:
            print ("Cesta %2d: %2d productos (nada para pesar)" % (c, cestas[c]["productos"]))
        else:
            print ("Cesta %2d: %2d productos (~ %2d kg)" % (c, cestas[c]["productos"], cestas[c]["peso"]))

def show_albaran():
    for p in productores:
        if len(p.productos) == 0:
            continue
        print (p.nombre + "\n")
        productos = sorted(p.productos, key=lambda p: p.nombre)
        for d in productos:
            sum = 0.0
            for c in d.repartos:
                sum = sum + c.cantidad
            n = d.nombre.replace(" (*)", "")
            print (("%6.1f %s" % (sum, n)).replace(".0", " -"))
        print ("")

for p in productores:
    productos = p.get_tipo(1)
    if len(productos) == 0:
        continue
    for d in productos:
        rps = d.get_tipo(1)
        if len(rps) == 1:
            d.nombre = d.nombre + " (*)"
            d.tipo = 0
            rps[0].tipo = 0

show_tipo(1)
print ("")
print ("---------------")
print ("")
show_cestas()
print ("")
print ("---------------")
print ("")
#show_tipo(0)
show_tipo_por_cesta(0)
print ("")
print ("---------------")
print ("")
show_albaran()

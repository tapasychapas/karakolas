#!/usr/bin/env python3

import os
import re
from datetime import datetime

import bs4
from jinja2 import Environment, FileSystemLoader

from core.api import Karakolas, Pedido, cfg
import argparse

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

default_out = "../tapasychapas.github.io/productos/index.md"
parser = argparse.ArgumentParser(description='Productos del grupo de consumo')
if os.path.isfile(default_out):
    parser.add_argument("salida", nargs='?', help="Fichero de salida", default=default_out)
else:
    parser.add_argument("salida", help="Fichero de salida")
args = parser.parse_args()

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
trim = re.compile(r"\s*\.\s*", re.MULTILINE | re.UNICODE)
peso = re.compile(r"^(.*?)(\d+gr)$", re.MULTILINE | re.UNICODE)

if False:
    import http.client as http_client
    import logging
    http_client.HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def price_str(s):
    if s == 0:
        return "<span title='Por determinar'>?</span><span class='ceros'>.00</span>"
    s = "{0:.2f}".format(s)
    s = s.replace(".00", "<span class='ceros'>.00</span>")
    return s


print("Consultando productos disponibles")
user, password, grupo = cfg(".ig_karakolas")
k = Karakolas(user, password, grupo)
productores = k.productores()


j2_env = Environment(loader=FileSystemLoader("templates"), trim_blocks=True)
j2_env.filters['price_str'] = price_str

out = j2_env.get_template('productos.html')
html = out.render(data={"now": datetime.now(), "productores": productores})
with open(args.salida, "wb") as fh:
    fh.write(bytes(html, 'UTF-8'))

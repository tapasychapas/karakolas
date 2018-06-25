#!/usr/bin/python3

import argparse
import json
import os
import re
import sys
from ftplib import FTP

import bs4
from jinja2 import Environment, FileSystemLoader

from core.api import Karakolas, Pedido, cfg, next_weekday

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

sp = re.compile(r"\s+", re.MULTILINE | re.UNICODE)
trim = re.compile(r"\s*\.\s*", re.MULTILINE | re.UNICODE)
peso = re.compile(r"^(.*?)(\d+gr)$", re.MULTILINE | re.UNICODE)

lunes = next_weekday(0).strftime("%Y-%m-%d")
martes = next_weekday(1).strftime("%Y-%m-%d")

parser = argparse.ArgumentParser(description='Pedido del grupo de consumo')
parser.add_argument('--noftp', action='store_true')
parser.add_argument('--pesar', action='store_true')
parser.add_argument("--fecha", nargs='*', help="Fecha del reparto en formato yyyy-mm-dd")
parser.add_argument("fichero", nargs='*', help="Fichero de reparto")
args = parser.parse_args()

if args.fichero:
    pedido = Pedido(*args.fichero)
else:
    user, password, grupo = cfg(".ig_karakolas")
    k = Karakolas(user, password, grupo)
    if not args.fecha:
        args.fecha = k.fechas()
    print ("Consultando reparto del día " + ", ".join(args.fecha))
    pedido = k.reparto(*args.fecha)

if len(pedido.repartos) == 0:
    sys.exit("No hay nada que repartir")

j2_env = Environment(loader=FileSystemLoader("templates"), trim_blocks=True)
out = j2_env.get_template('index.html')
html = out.render(pedido=pedido)
with open("out/simple.html", "wb") as fh:
    fh.write(bytes(html, 'UTF-8'))


def get_table(cls, h1):
    table = bs4.BeautifulSoup('''
		<div>
		<table class="%s">
			<tr>
				<td class="col1"></td>
				<td class="col2"></td>
				<td class="col3"></td>
			</tr>
		</table>
		</div>
	''' % cls, "html.parser").select("*")[0]
    if h1:
        table.insert(0, h1)
    return table


def get_items(div, s):
    size = 0
    items = []
    if s == "albaran":
        items = div.select("div.productor")  # findAll(["h2", "ul"])
        size = len(div.findAll(["h2", "li"]))
    else:
        for i in div.findAll(["h2", "li"]):
            if i.name == "h2":
                size += 1
                items.append(i)
            elif "ul" in i.attrs.get("class", []):
                size += 1 + len(i.findAll("li"))
                items.append(i)
    return items, size

soup = bs4.BeautifulSoup(html, "lxml")
soup.body.attrs["class"] = "tabla"

for s in ("pesar", "nopesar", "albaran"):
    div = soup.select("div." + s)[0]
    table = get_table(s, div.find("h1"))
    tds = table.findAll("td")

    items, size = get_items(div, s)
    slice = int(size / 3)
    count = 0

    for i in items:
        td = min(int(count / slice), 2)
        td = tds[td]
        td.append(i)
        if i.name == "h2":
            count += 1
        elif s == "albaran":
            count += 1 + len(i.findAll("li"))
        elif "ul" in i.attrs.get("class", []):
            count += 1 + len(i.findAll("li"))
    for li in table.select("li.ul"):
        li.name = "div"

    for i in range(0, len(tds) - 1):
        children = tds[i].select(" > *")
        if len(children) > 0 and children[-1].name == "h2":
            tds[i + 1].insert(0, children[-1])

    div.replace_with(table)


with open("out/index.html", "w", encoding='utf-8') as f:
    f.write(str(soup))


def upload(*arg):
    host, user, passwd, path = cfg(".ig_ftp")
    ftp = FTP(host)
    ftp.login(user=user, passwd=passwd)
    ftp.cwd(path)
    for f in arg:
        with open(f, 'rb') as fh:
            ftp.storbinary('STOR ' + os.path.basename(f), fh)
    ftp.quit()

if not args.noftp:
    upload("out/index.html", "out/simple.html")

print ("OK!")

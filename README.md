# Instalación

```console
$ sudo install python3 python3-pip git
$ git clone https://github.com/tapasychapas/karakolas.git
$ cd karakolas
$ sudo -H pip3 install -r requirements.txt
$ echo "usuario password idgrupo" > .ig_karakolas
```

El `idgrupo` es el número que sale en las `url` de
`karakolas` cuando estas visitando dicho grupo en la web.

Por ejemplo, si entras en `Gestión de pedidos` y la `url` es
`https://karakolas.net/gestion_pedidos/gestion_pedidos.html?grupo=84`
eso significa que el `idgrupo` es `84`.

# Uso

## Reparto

```console
$ ./reparto.py --help
usage: reparto.py [-h] [--fecha [FECHA [FECHA ...]]] [fichero [fichero ...]]

Pedido del grupo de consumo

positional arguments:
  fichero               Fichero de reparto

optional arguments:
  -h, --help            show this help message and exit
  --fecha [FECHA [FECHA ...]]
                        Fecha del reparto en formato yyyy-mm-dd
```

Cuando se ejecuta `./reparto.py` (sin parámetros) el script
se conecta a `karakolas`, busca los pedidos abiertos y:

* si no hay ninguno falla
* si hay varios se queda con el último, lo descarga y genera una
web con la tabla de reparto en el directorio `out`

El parámetro `--fecha` es para evitar buscar los repartos en `karakolas`
e ir directamente a la fecha (o fechas) pasadas por párametro.
Y el parámetro `fichero` es para evitar conectarse a `karakolas` y generar
la tabla de reparto directamente de un fichero previamente descargado
de `karakolas`

En cualquier caso, el paso final es entrar en `out/index.html` y seguir
las intrucciones hay detalladas para obtener el producto final.

## Productos

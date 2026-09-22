# lab_colector - Telegraf oficial, version fijada (O-D10).
#
# Solo se le anaden dos cosas, y las dos son para poder mirar un Linux SIN
# instalarle nada: el cliente de SSH y el Python que traduce lo que responde.
FROM telegraf:1.29-alpine

RUN apk add --no-cache openssh-client python3

COPY linux_sin_agente.py /opt/kinetix/linux_sin_agente.py

# El estado de la CPU entre intervalos (se mide por diferencia) y la copia
# privada de la llave SSH.
#
# OJO con el usuario: el `entrypoint` de la imagen oficial hace
# `exec su-exec telegraf "$@"`, asi que Telegraf corre SIEMPRE como `telegraf`
# aunque el contenedor arranque como root. Poner `user: root` en el compose no
# cambia nada. Por eso el directorio se le entrega a ese usuario aqui: sin esto
# el lector moria al copiar la llave y no llegaba ni una metrica de Linux.
RUN mkdir -p /var/lib/kinetix && chown telegraf:telegraf /var/lib/kinetix

# O-D16 - y leelo despacio, porque es el permiso caro de esta etapa.
#
# Leer el socket de Docker exige pertenecer al grupo que lo posee. Aqui ese
# grupo es `root`; en un servidor Linux normal seria el grupo `docker`. Da
# igual como se llame: **quien puede leer ese socket puede tomar la maquina
# anfitriona entera**. En el laboratorio se hace; a un cliente no se le pide
# sin ensenarle docs/observabilidad/requisitos-sin-agente.md, seccion 4.
RUN addgroup telegraf root

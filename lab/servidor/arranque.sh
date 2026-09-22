#!/bin/bash
# Arranque del servidor de laboratorio: sshd para el recolector y la tienda.
set -e

# Llaves de maquina, la primera vez.
ssh-keygen -A >/dev/null 2>&1 || true

# La llave PUBLICA del lector llega por montaje (la privada no entra aqui nunca).
if [ -f /llaves/kinetix_lector.pub ]; then
    install -o kinetix_lector -g kinetix_lector -m 600 \
        /llaves/kinetix_lector.pub /home/kinetix_lector/.ssh/authorized_keys
    echo "arranque: authorized_keys instalada" >&2
else
    echo "arranque: AVISO - no hay /llaves/kinetix_lector.pub; el recolector no entrara" >&2
fi

/usr/sbin/sshd -D -e &
exec python3 /opt/tienda/app.py

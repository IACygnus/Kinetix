# lab_servidor - el "servidor Linux" del laboratorio (O-D9).
#
# Ubuntu con SSH y una aplicacion pequena. `psycopg2` sale del paquete de
# Ubuntu, no de pip: el laboratorio no anade ni una dependencia a Kinetix.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        openssh-server \
        python3 \
        python3-psycopg2 \
        procps \
        iproute2 \
        curl \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd

# O-D11: sin contrasena, sin sudo, shell normal para que `ssh host comando`
# funcione. No pertenece a ningun grupo privilegiado.
RUN useradd --create-home --shell /bin/bash kinetix_lector \
 && passwd --lock kinetix_lector \
 && mkdir -p /home/kinetix_lector/.ssh \
 && chown kinetix_lector:kinetix_lector /home/kinetix_lector/.ssh \
 && chmod 700 /home/kinetix_lector/.ssh

COPY sshd_kinetix.conf /etc/ssh/sshd_config.d/kinetix.conf
COPY app.py /opt/tienda/app.py
COPY arranque.sh /opt/arranque.sh
RUN chmod +x /opt/arranque.sh

EXPOSE 22 8080
CMD ["/opt/arranque.sh"]

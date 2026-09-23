# Datos de prueba del laboratorio

**Para pegar en la pantalla de Servidores.** Todo lo de aquí es del laboratorio
local: no hay nada de ningún cliente.

---

## Por qué las credenciales no están escritas aquí

Los dos primeros campos de cada servidor son públicos y están abajo tal cual.
**Las credenciales no**: este documento va al repositorio, y el repositorio va a
GitHub. Una llave privada SSH commiteada sigue siendo una llave privada
commiteada aunque sea de un laboratorio.

En su lugar hay, para cada una, **un comando que la deja en el portapapeles**.
Un paso, copiar, pegar.

Y si el laboratorio no existe todavía o quieres rehacerlo:

```powershell
cd C:\proyectos\Kinetix
bash scripts/lab_preparar.sh
docker compose -p kinetix_lab --env-file lab/lab.env -f docker-compose.lab.yml up -d --build
```

---

## Servidor 1 — `lab_servidor` (Linux)

| Campo de la pantalla | Qué poner |
|---|---|
| **Cliente** | el que quieras; para probar, crea uno llamado `ZZTEST-Laboratorio` |
| **Nombre** | `lab_servidor` |
| **Tipo** | Linux |
| **Modo** | Sin agente |
| **Dirección** | `lab_servidor` |
| **Puerto** | `22` |
| **Usuario** | `kinetix_lector` |
| **Notas** | *(vacío)* |

**La credencial** es la llave privada SSH. Al portapapeles:

```powershell
Get-Content C:\proyectos\Kinetix\lab\llaves\kinetix_lector -Raw | Set-Clipboard
```

Y pégala en el campo «Llave privada SSH del usuario de solo lectura». Empieza
por `-----BEGIN OPENSSH PRIVATE KEY-----`.

---

## Servidor 2 — `lab_db` (PostgreSQL)

| Campo de la pantalla | Qué poner |
|---|---|
| **Cliente** | el mismo de arriba |
| **Nombre** | `lab_db` |
| **Tipo** | PostgreSQL |
| **Modo** | Sin agente |
| **Dirección** | `lab_db` |
| **Puerto** | `5432` |
| **Usuario** | `kinetix_lector` |
| **Base de datos** | `tienda` |

**La credencial** es la contraseña del rol de solo lectura. Al portapapeles:

```powershell
(Select-String -Path C:\proyectos\Kinetix\lab\lab.env -Pattern '^LAB_PG_LECTOR_PASSWORD=(.+)$').Matches.Groups[1].Value | Set-Clipboard
```

Son 28 caracteres, letras y números.

---

## Por qué «lab_servidor» y no una dirección IP

Porque los dos son contenedores de Docker y Kinetix los alcanza **por su
nombre**, dentro de la red de contenedores. Comprobado desde el propio backend:

```
SI    lab_servidor:22    (SSH)
SI    lab_servidor:8080  (la tienda)
SI    lab_db:5432        (PostgreSQL)
```

Con un servidor de un cliente pondrías su IP o su nombre de dominio, y tendría
que haber ruta desde donde corre Kinetix hasta él. Es lo mismo, solo que aquí la
ruta ya existe.

---

## El token de lectura — hace falta una vez

Sin él, la pantalla **no puede dibujar ninguna gráfica**: el token de monitoreo
que ya había es de solo escritura a propósito (O-D2) y no puede leer nada. Este
otro lee los dos depósitos —el de la prueba y el de los servidores— y no puede
escribir en ninguno.

```powershell
# 1. Copiar el token de lectura al portapapeles
docker exec jmeter_influxdb influx auth list --host http://localhost:8086 `
  -t jmeter-token-2024-super-secret |
  Select-String 'kinetix-lectura' |
  ForEach-Object { ($_ -split '\s+')[2] } | Set-Clipboard
```

Y se pega en **Observabilidad → Sesiones de monitoreo**, en el aviso que sale
arriba cuando falta. Si no te sale ese aviso, es que ya está cargado.

> Si el token no existiera todavía, lo crea `bash scripts/lab_preparar.sh`.

---

## La aplicación del laboratorio, para dar carga

La tienda de mentira responde en `http://127.0.0.1:8090` desde tu equipo:

| Petición | Qué cuesta |
|---|---|
| `GET /salud` | 4 ms — no toca la base |
| `GET /productos?limite=50` | 8 ms — consulta por índice |
| `GET /buscar?q=a1b` | **550-750 ms** — recorre 1.500.000 filas sin índice |

La tercera es la que hace trabajar al servidor, y es la que usa el plan de
prueba `lab/prueba/zztest_lab.jmx`.

# Agente de vigilancia de constructoras — Huelva y Sevilla

Revisa cada día las webs de un grupo de promotoras, constructoras y gestoras de
cooperativas, detecta **promociones nuevas, cambios y retiradas**, se queda solo
con lo que cae en las provincias de **Huelva y Sevilla**, y te avisa por
**Telegram**. Además rastrea la prensa para descubrir promotoras que aún no
estás vigilando.

Se ejecuta en **GitHub Actions**, así que no necesitas tener el ordenador
encendido.

---

## 1. Puesta en marcha

### 1.1 Crear el bot de Telegram

Esto lo tienes que hacer tú, porque implica credenciales:

1. En Telegram, habla con **@BotFather** → `/newbot` → le pones nombre y usuario.
   Te devuelve un **token** con esta pinta: `8123456789:AAF...`
2. Escríbele algo a tu bot recién creado (un simple "hola"), para que exista una
   conversación.
3. Abre en el navegador, sustituyendo `<TOKEN>`:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   Busca `"chat":{"id":123456789` → ese número es tu **chat_id**.

### 1.2 Subir el proyecto a GitHub

El repositorio puede ser **privado**; Actions funciona igual.

```bash
git add -A
git commit -m "Agente de vigilancia de constructoras en Huelva y Sevilla"
git remote add origin https://github.com/TU_USUARIO/TU_REPO.git
git push -u origin main
```

### 1.3 Guardar las credenciales como secrets

En el repositorio: **Settings → Secrets and variables → Actions → New repository
secret**. Crea estos dos:

| Nombre | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | el token de @BotFather |
| `TELEGRAM_CHAT_ID` | el número del paso 1.1 |

Los secrets no se ven en los logs ni en el código. **No pongas el token en
ningún fichero del repositorio.**

### 1.4 Dar permiso de escritura al workflow

El agente guarda su memoria en `estado/estado.json` y necesita poder hacer
commit. En **Settings → Actions → General → Workflow permissions**, marca
**Read and write permissions**.

### 1.5 Probarlo

En la pestaña **Actions → Vigilancia de constructoras → Run workflow**. Déjalo
con las opciones por defecto. Debería terminar en verde y, si hay novedades,
llegarte el aviso a Telegram.

A partir de ahí se ejecuta **solo, todos los días a las 07:15 UTC** (09:15 en
horario de verano peninsular, 08:15 en invierno).

---

## 2. Uso

### Desde GitHub

**Actions → Vigilancia de constructoras → Run workflow**, con tres opciones:

| Opción | Para qué |
|---|---|
| *Solo informe, sin enviar Telegram* | probar sin que te llegue nada |
| *Reiniciar la memoria* | tras tocar `sources.yaml`: memoriza lo actual sin avisar |
| *Revisar solo esta fuente* | depurar una promotora concreta (`bekinsa`, `aedas`…) |

Cada ejecución deja el informe HTML como **artifact** de la propia ejecución
(30 días).

### En tu ordenador

Hay un entorno virtual ya montado en `.venv`:

```bash
.venv/Scripts/python.exe -m constructoras.cli --sin-aviso
```

O con el script auxiliar: `.\revisar.ps1 -SinAviso`.

Opciones: `--solo ID`, `--sin-aviso`, `--sin-prensa`, `--todo`,
`--max-fichas N`, `--init`, `--probar-telegram`, `--estado FICHERO`, `-v`.

- `--todo` incluye también los movimientos fuera de Huelva y Sevilla.
- `--max-fichas N` limita cuántas fichas abre **por fuente** para ubicar
  promociones sin provincia clara (30 por defecto, 150 con `--init`).
- `--estado` es lo que usa Actions: carga y reescribe la memoria en JSON.

> Ojo: si lanzas una revisión en local **con** `--estado estado/estado.json` y
> luego Actions hace la suya, ambas escriben el mismo fichero. Para trastear en
> local usa `--sin-aviso` y sin `--estado`, que trabaja contra `data/estado.db`.

---

## 3. Qué vigila

Las ocho que pediste, más otras promotoras y cooperativas con obra en las dos
provincias:

| Fuente | Ámbito relevante |
|---|---|
| Urbanz | Cooperativas en Huelva y Sevilla (Tres Velas, Alma del Odiel, William Martin Living) |
| Solvia | Municipios de Huelva y Sevilla donde tiene stock |
| Bekinsa | Huelva capital, Nuevo Portil, Dos Hermanas, Palomares del Río |
| Grupo ABU | Sevilla y Huelva (Residencial Plus Ultra) |
| Inmovista | Huelva capital |
| Intur | Huelva (Ensanche Sur, Plus Ultra) |
| LandCo | Promociones y **suelo finalista** en Aljaraque, Dos Hermanas, Almensilla… |
| AEDAS Homes | +25 promociones en la provincia de Sevilla |
| Iceberg Viviendas | Cooperativas en Sevilla |
| Grupo Insur | Sevilla capital, Aljarafe y Mazagón |
| Caralca, Serprocol, Sevilla 2000 | Comercializadoras locales |
| Metrovacesa | Páginas propias de Huelva y de Sevilla |
| Culmia | La Joya, La Joya II y Odelania (Huelva); Atalaya y Ciencias Park (Sevilla) |
| Vía Célere | 21 promociones en Sevilla (Nervión, Ciencias 17, San Juan…) |
| Neinor Homes | Páginas propias de Sevilla y de Huelva |
| Habitat Inmobiliaria | Provincia de Sevilla |
| Prensa (Bing News + Europa Press Andalucía) | Descubrimiento de promotoras y cooperativas nuevas |

> Google News sería lo natural para el descubrimiento, pero su `robots.txt`
> prohíbe el acceso automatizado a las búsquedas RSS. Bing sí lo permite y da
> resultados equivalentes.

### Cómo detecta los cambios

Cada fuente se vigila por uno o varios métodos, según cómo esté hecha la web:

- **`sitemap`** — recorre el sitemap y detecta URLs nuevas. Es lo más fiable en
  webs que pintan las fichas con JavaScript (Grupo ABU, AEDAS), donde los
  enlaces no están en el HTML.
- **`links`** — vigila los enlaces de un listado que encajen con un patrón.
- **`titulares`** — vigila los encabezados de una página. Sirve para secciones
  tipo "próximamente" que no tienen enlace propio.

### Cómo decide si es de Huelva o Sevilla

Compara contra el listado completo de municipios de ambas provincias, más
urbanizaciones y zonas que aparecen en los anuncios sin citar el municipio
(Nuevo Portil, Islantilla, Ensanche Sur, Entrenúcleos, Montequinto…).

Si por el título y la URL no lo tiene claro, **abre la ficha** y la analiza,
quitando antes menú, pie y bloques de "otras promociones" — sin eso, una
promoción de Mérida acabaría clasificada como sevillana solo porque el pie de
página lleva la dirección de la empresa. Después puntúa cada provincia por
cuántas veces se la nombra y se queda con la dominante.

Las promotoras que solo operan en una provincia (Inmovista, Serprocol,
Sevilla 2000) llevan `provincias_forzadas`: todo lo que publiquen cuenta.

`pruebas.py` comprueba todo esto con casos reales, incluidos los que engañan
(Mérida con pie de Sevilla, Mijas, municipios ambiguos como Cala o Herrera).
El workflow lo ejecuta antes de cada revisión.

---

## 4. Añadir o quitar constructoras

Todo está en [`sources.yaml`](sources.yaml), con comentarios. Una fuente mínima:

```yaml
  - id: mipromotora
    name: Mi Promotora
    homepage: https://mipromotora.es/
    provincias_forzadas: [Huelva]        # opcional
    watch:
      - kind: links
        url: "https://mipromotora.es/promociones/"
        include: "mipromotora\\.es/promociones/[^/]+/$"
        id: "mipromotora:promos"
      - kind: sitemap
        url: "https://mipromotora.es/sitemap_index.xml"
        id: "mipromotora:sitemap"
```

Ajustes por vigilancia:

| Ajuste | Efecto |
|---|---|
| `solo_titulo: true` | no abre la ficha; úsalo si el municipio ya va en la URL |
| `solo_relevantes: true` | descarta lo de fuera de las dos provincias sin guardarlo (listados enormes, como el suelo de LandCo) |
| `silencioso: true` | no avisa si la página falla (para vigilar páginas que aún no existen) |
| `aviso_alta: "..."` | texto del aviso cuando esa página aparece por primera vez |

Tras añadir una fuente, lanza el workflow con **Reiniciar la memoria** marcado
para que memorice lo que ya existe sin mandarte 40 avisos de golpe.

---

## 5. Detalles de funcionamiento

- **Es educado con las webs**: un user-agent real, 1,5 s entre peticiones al
  mismo dominio, reintentos con espera y **respeta `robots.txt`**. Por eso no
  entra en Idealista ni Fotocasa, cuyas condiciones prohíben el rastreo: va a la
  web de cada promotora, que es la fuente original y suele ir por delante de los
  portales.
- **Primer aviso, no primer fallo**: si una web falla una vez no te dice nada;
  avisa al segundo fallo seguido y deja de insistir al cuarto.
- **No avisa de retiradas masivas**: si de golpe desaparece más de la mitad de un
  listado, casi nunca es que hayan vendido medio catálogo — es un cambio de
  plantilla o una petición bloqueada. Lo anota, pero no te molesta.
- **Si el propio agente falla**, el workflow te manda un aviso a Telegram con el
  enlace al error. El silencio nunca significa "todo bien" por accidente.
- **Urbanz está caída**: su WordPress devuelve error 500 en todo el dominio, no
  es cosa del agente. Está configurada y en cuanto vuelva recibirás un aviso.
- **AEDAS no construye hoy en Huelva.** Se vigila igualmente la URL de su página
  de Huelva: el día que exista, salta un aviso.
- **Inmovista** publica su cartera a través de Idealista, no en su propia web.
  Se vigila lo que sí publica (sitemap y titulares), pero no su listado completo.
- Si Telegram falla, los eventos **quedan pendientes** y se reenvían en la
  siguiente ejecución. No se pierde nada.
- Una misma promoción aparece a la vez en el listado y en el sitemap: se avisa
  **una sola vez**.

## 6. Estructura

```
.github/workflows/vigilancia.yml   ejecucion diaria en GitHub Actions
constructoras/
  geo.py       municipios y zonas de Huelva y Sevilla; puntuacion de relevancia
  fetch.py     descargas con ritmo, reintentos y robots.txt
  extract.py   sitemaps, enlaces, titulares y texto util de una ficha
  store.py     estado en SQLite + exportacion a JSON versionable
  monitor.py   comparacion con la pasada anterior y generacion de eventos
  discover.py  rastreo de prensa para encontrar promotoras nuevas
  notify.py    envio por Telegram
  report.py    informe HTML
  cli.py       linea de comandos
sources.yaml   QUE se vigila  <- es el fichero que tocaras
pruebas.py     comprobaciones de la deteccion Huelva/Sevilla
estado/        la memoria del agente (esto SI va al repositorio)
data/          base de trabajo y logs locales (ignorados por git)
reports/       informes locales (ignorados por git)
```

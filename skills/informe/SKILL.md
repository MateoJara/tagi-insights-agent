---
name: informe
description: "Genera el tablero de insights de un negocio a partir de sus reseñas de Google, sea cual sea el negocio y el formato en que estén las reseñas: qué cambió, qué dicen los clientes, de qué se quejan, qué valoran y un plan de acción priorizado para el dueño. Usar cuando pidan un informe, reporte, tablero, dashboard o análisis de las reseñas de un negocio, o cuando digan dónde están guardadas sus reseñas."
argument-hint: "[carpeta con las reseñas]"
---

# Tablero de insights

El resultado es un **tablero** (un HTML interactivo de un solo archivo) para el
dueño del negocio. Ocupado y no técnico, lo abre en el celular. Vale por el plan de
acción, no por la cantidad de cifras.

Sirve para cualquier negocio con reseñas en Google. Los temas salen de lo que
escriben sus clientes, no de una lista fija por sector.

Quien pide el tablero puede no saber nada de programación. Háblale de usted, en
español, sin términos técnicos, y cuéntale en una línea qué estás haciendo en cada
paso.

## Entradas

La carpeta con las reseñas: $ARGUMENTS

Si arriba no hay una carpeta, pregunta dónde están guardadas las reseñas. Pueden
venir en CSV, Excel, JSON o texto copiado de Google Maps, con cualquier nombre de
columna.

Todo lo que se genere va en una carpeta `tagi` dentro de la carpeta de las reseñas
(`<carpeta>/tagi/`). Los datos del negocio no salen de su computador: no los copies
a otro lugar ni los subas a ningún servicio.

## Pasos

0. **Preparar Python.** Busca un Python 3:
   - En Windows, `python` y luego `py -3`. No uses `python3`: en Windows suele ser
     un atajo a la Microsoft Store, no Python.
   - En Mac y Linux, `python3`.

   Con ese Python corre:

   ```
   <python> "${CLAUDE_PLUGIN_ROOT}/tagi.py" setup --env-dir "${CLAUDE_PLUGIN_DATA}"
   ```

   La primera vez instala lo necesario y puede tardar un par de minutos; avísalo.
   Imprime una línea `TAGI_PYTHON=<ruta>`: esa ruta es **el Python del análisis**.
   Úsala en todos los comandos que siguen y pásala a cada subagente.

   Si no hay ningún Python, o el comando dice que la versión es vieja, explica cómo
   instalarlo desde https://www.python.org/downloads/ (en Windows, marcando "Add
   python.exe to PATH") y detente.

1. **Importar las reseñas.** Lanza el subagente `tagi:importador` con la carpeta de
   las reseñas, la carpeta de salida `<carpeta>/tagi` y el Python del análisis.
   Deja `<carpeta>/tagi/google_reviews.csv`.

   Si el importador pregunta algo (por ejemplo, el día en que se copiaron unas
   reseñas de Google Maps), hazle la pregunta al usuario con palabras sencillas y
   vuelve a lanzarlo con la respuesta. No respondas tú por el usuario.

2. **Delegar el análisis a los dos subagentes, en paralelo** (las dos llamadas en
   el mismo mensaje). A cada uno se le pasa la ruta del CSV, su carpeta y el Python
   del análisis:

   - `tagi:analista-cuantitativo`, con `<carpeta>/tagi`: deja `metrics.json`
     (reporte de limpieza y todas las cifras).
   - `tagi:analista-comentarios`, con `<carpeta>/tagi/comments`: deja
     `comment_metrics.json` (temas, quejas, elogios, detalles pequeños y citas).

   Si alguno reporta un error, detente y explícalo; no adaptes los datos a mano.
   Si el analista de comentarios dice que no hay comentarios, sigue sin ellos: el
   tablero se genera sin `--comments`.
   Si los subagentes no están disponibles, sigue tú las instrucciones de sus
   archivos en `${CLAUDE_PLUGIN_ROOT}/agents/`.

3. **Usar solo esas cifras.** Toda cifra de los textos sale de `metrics.json` o de
   `comment_metrics.json`, leídos por ti, no del resumen que devuelven los
   subagentes. No calcules promedios, porcentajes ni diferencias de cabeza. Si hace
   falta una cifra que no está, déjala fuera.

   Mira `data_warnings` en `metrics.json`. Si trae algún código, hay pocos datos:
   el tablero mostrará un aviso por su cuenta, y los textos se escriben con las
   reglas de "Con pocos datos" de `${CLAUDE_SKILL_DIR}/references/tablero.md`.

4. **Interpretar.** Lee `${CLAUDE_SKILL_DIR}/references/criterios.md`: cómo leen los clientes las
   reseñas, qué señal sugiere qué hipótesis y cómo priorizar.

5. **Escribir los textos del tablero** en `<carpeta>/tagi/insights.json`, con el
   tono, las preguntas previas y los campos de `${CLAUDE_SKILL_DIR}/references/tablero.md`.
   Ejemplo completo: `${CLAUDE_PLUGIN_ROOT}/examples/insights.json`. El nombre
   del negocio sale de los archivos o se le pregunta al usuario.

6. **Generar el tablero.** Las cifras las pone el script; no se escriben a mano.

   ```
   "<Python del análisis>" "${CLAUDE_PLUGIN_ROOT}/tagi.py" dashboard --reviews <carpeta>/tagi/google_reviews.csv --insights <carpeta>/tagi/insights.json --comments <carpeta>/tagi/comments/comment_metrics.json --output <carpeta>/tagi/tablero.html
   ```

   El aviso de pocos datos y el cierre con el contacto de Tagi los pone el script.
   Si puedes abrirlo, revisa que se vea bien y que no haya errores.

7. **Pasar por el revisor.** Lanza el subagente `tagi:revisor` con la ruta del CSV,
   `insights.json`, el tablero, la carpeta de comentarios y el Python del análisis.
   Recalcula cada cifra por su cuenta y comprueba cada cita.

   - Si devuelve `CON ERRORES`: corrige lo que señala, genera el tablero de nuevo
     y vuelve a lanzarlo. Si un error es en realidad una diferencia de definición
     y no del texto, dilo en vez de cambiar el texto para que cuadre.
   - No se entrega nada hasta que devuelva `APROBADO`.
   - Lee también sus observaciones: no bloquean, pero suelen señalar frases que
     comparan cifras de periodos distintos.

   Tú no reemplazas al revisor: quien redactó un texto no ve sus propios errores.

8. **Entregar.** Di dónde quedó el tablero (`<carpeta>/tagi/tablero.html`), que
   se abre con doble clic en cualquier navegador, también sin internet, y resume en
   tres líneas lo más importante: cómo está el negocio y qué hacer primero.

Si alguien pide además un informe escrito, redáctalo después del tablero a partir
de las mismas preguntas de `${CLAUDE_SKILL_DIR}/references/tablero.md`, y pásalo también por el revisor.
Por defecto no se escribe: el dueño solo ve el tablero.

## Reglas

- Toda recomendación se apoya en una cifra del análisis, citada junto a ella.
- Los datos dicen qué pasó, no por qué. Las causas se escriben como hipótesis para
  confirmar con el dueño.
- Máximo tres prioridades.
- Junto a cada cifra importante, cuántas reseñas hay detrás: `previous_n`,
  `recent_n`, `previous_text_n` y `recent_text_n` en `metrics.json`.
- Para comparar un tema entre periodos usa sus proporciones (`previous_share`,
  `recent_share` en `comment_metrics.json`), nunca los conteos: el periodo reciente
  son pocos meses contra muchos.
- Al comparar un antes con un ahora, las dos cifras salen de periodos que no se
  solapan: `previous_*` y `recent_*`. El total o histórico incluye lo reciente y
  no sirve como "antes".
- Lo marcado como [Criterio] en `${CLAUDE_SKILL_DIR}/references/criterios.md` se presenta como
  sugerencia. Lo marcado como [Evidencia] se cita como referencia de otros
  mercados, nunca como promesa de resultado.
- No recomendar incentivos a cambio de reseñas.

## Salida, en `<carpeta>/tagi/`

| Archivo | Qué es |
|---|---|
| `tablero.html` | El tablero para el dueño: un solo archivo que abre sin internet |
| `google_reviews.csv` | Las reseñas ya importadas, sin nombres de clientes |
| `metrics.json`, `comments/` | Las cifras y el análisis de comentarios |
| `insights.json` | Los textos del tablero |

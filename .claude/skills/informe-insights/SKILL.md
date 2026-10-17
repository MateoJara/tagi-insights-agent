---
name: informe-insights
description: Genera el tablero de insights de un negocio a partir de sus reseñas de Google, sea cual sea el negocio: qué cambió, qué dicen los clientes, de qué se quejan, qué valoran y un plan de acción priorizado para el dueño. Usar cuando pidan un informe, reporte, tablero, dashboard o análisis de las reseñas de un negocio, o cuando entreguen reseñas para analizar.
---

# Tablero de insights

El resultado es un **tablero** (un HTML interactivo de un solo archivo) para el
dueño del negocio. Ocupado y no técnico, lo abre en el celular. Vale por el plan de
acción, no por la cantidad de cifras.

Sirve para cualquier negocio con reseñas en Google. Los temas salen de lo que
escriben sus clientes, no de una lista fija por sector.

## Entradas

Un CSV de reseñas de Google con las columnas definidas en `src/schema.py`. Si no
se indica ninguno, se usa el dataset sintético de `data/sample/`.

Si las reseñas vienen en otro formato (Excel, JSON, texto copiado de Google Maps,
un CSV con otros nombres de columna), primero pásalas por el subagente
`importador`, que deja el CSV en ese formato.

Si los archivos son de un cliente real, viven en `data/private/<cliente>/` y todo
lo que se genere se guarda en esa misma carpeta. Nada de un cliente real se copia,
cita ni resume fuera de `data/private/`.

## Pasos

1. **Delegar el análisis a los dos subagentes, en paralelo** (las dos llamadas en
   el mismo mensaje). A cada uno se le pasa la ruta del CSV y su carpeta:

   - `analista-cuantitativo`, con `<carpeta>`: deja `metrics.json` (reporte de
     limpieza y todas las cifras).
   - `analista-comentarios`, con `<carpeta>/comments`: deja `comment_metrics.json`
     (temas, quejas, elogios, detalles pequeños y citas).

   Si alguno reporta un error, detente y repórtalo; no adaptes los datos a mano.
   Si el analista de comentarios dice que no hay comentarios, sigue sin ellos: el
   tablero se genera sin `--comments`.
   Si los subagentes no están disponibles, sigue tú las instrucciones de sus
   archivos en `.claude/agents/`.

2. **Usar solo esas cifras.** Toda cifra de los textos sale de `metrics.json` o de
   `comment_metrics.json`, leídos por ti, no del resumen que devuelven los
   subagentes. No calcules promedios, porcentajes ni diferencias de cabeza. Si hace
   falta una cifra que no está, agrégala al código con su test.

   Mira `data_warnings` en `metrics.json`. Si trae algún código, hay pocos datos:
   el tablero mostrará un aviso por su cuenta, y los textos se escriben con las
   reglas de "Con pocos datos" de `references/tablero.md`.

3. **Interpretar.** Lee `references/criterios.md`: cómo leen los clientes las
   reseñas, qué señal sugiere qué hipótesis y cómo priorizar.

4. **Escribir los textos del tablero** en `<carpeta>/insights.json`, con el tono,
   las preguntas previas y los campos de `references/tablero.md`.

5. **Generar el tablero.** Las cifras las pone el script; no se escriben a mano.

   ```
   .venv\Scripts\python -m src.dashboard --reviews <csv> --insights <carpeta>/insights.json --comments <carpeta>/comments/comment_metrics.json --output <carpeta>/dashboard.html
   ```

   El aviso de pocos datos y el cierre con el contacto de Tagi los pone el script.

   Ábrelo y revisa que se vea bien y que no haya errores.

6. **Pasar por el revisor.** Lanza el subagente `revisor` con la ruta del CSV,
   `insights.json`, el tablero y la carpeta de comentarios. Recalcula cada cifra
   por su cuenta y comprueba cada cita.

   - Si devuelve `CON ERRORES`: corrige lo que señala, genera el tablero de nuevo
     y vuelve a lanzarlo. Si un error es en realidad una diferencia de definición
     y no del texto, corrige la definición donde esté escrita, no el veredicto.
   - No se entrega nada hasta que devuelva `APROBADO`.
   - Lee también sus observaciones: no bloquean, pero suelen señalar frases que
     comparan cifras de periodos distintos.

   Tú no reemplazas al revisor: quien redactó un texto no ve sus propios errores.

Si alguien pide además un informe escrito, redáctalo después del tablero a partir
de las mismas preguntas de `references/tablero.md`, y pásalo también por el revisor.
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
- Lo marcado como [Criterio] en `references/criterios.md` se presenta como
  sugerencia. Lo marcado como [Evidencia] se cita como referencia de otros
  mercados, nunca como promesa de resultado.
- No recomendar incentivos a cambio de reseñas.

## Salida

| | Dataset sintético | Cliente real |
|---|---|---|
| Tablero (se entrega) | `examples/dashboard-ejemplo.html` | `data/private/<cliente>/dashboard.html` |
| Textos del tablero | `examples/insights.json` | `data/private/<cliente>/insights.json` |
| Cifras | `examples/metrics.json` | `data/private/<cliente>/metrics.json` |

El tablero es un solo archivo que abre sin internet.

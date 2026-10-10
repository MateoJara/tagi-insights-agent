---
name: informe-insights
description: Genera el informe de insights de Tagi para un negocio a partir de las respuestas de su formulario de clientes y sus reseñas de Google: métricas clave, gráficas, qué cambió y un plan de acción priorizado para el dueño. Usar cuando pidan un informe, reporte o análisis de un restaurante o cliente de Tagi, o cuando entreguen archivos de encuestas o reseñas para analizar.
---

# Informe de insights

Se producen dos cosas a partir de las mismas cifras:

- **El tablero** (HTML interactivo): es lo que recibe el dueño del negocio. Ocupado,
  no técnico, lo abre en el celular. Visual y con pocas palabras.
- **El informe** (Markdown): documento interno de Tagi con el razonamiento completo.
  De él salen los textos cortos del tablero y es donde se verifica cada cifra.

Los dos valen por el plan de acción, no por la cantidad de cifras.

## Entradas

Dos archivos CSV con las columnas definidas en `src/survey_schema.py`:
respuestas del formulario y reseñas de Google. Si no se indica ninguno, se usa el
dataset sintético de `data/sample/`.

Si los archivos son de un cliente real, viven en `data/private/<cliente>/` y todo
lo que se genere (cifras, gráficas, informe) se guarda en esa misma carpeta. Nada
de un cliente real se copia, cita ni resume fuera de `data/private/`.

## Pasos

1. **Delegar el análisis a los dos subagentes, en paralelo** (las dos llamadas en
   el mismo mensaje). A cada uno se le pasan las rutas de los CSV y su carpeta:

   - `analista-cuantitativo`, con `<carpeta>`: deja `metrics.json` (reporte de
     limpieza y todas las cifras) y las gráficas en `charts/`.
   - `analista-comentarios`, con `<carpeta>/comments`: deja `comment_metrics.json`
     (temas, quejas, elogios, detalles pequeños y citas).

   Si alguno reporta un error, detente y repórtalo; no adaptes los datos a mano.
   Si los subagentes no están disponibles, sigue tú las instrucciones de sus
   archivos en `.claude/agents/`.

2. **Usar solo esas cifras.** Toda cifra del informe sale de `metrics.json` o de
   `comment_metrics.json`, leídos por ti, no del resumen que devuelven los
   subagentes. No calcules promedios, porcentajes ni diferencias de cabeza. Si hace
   falta una cifra que no está, agrégala al código con su test.

3. **Revisar las gráficas.** Abre cada PNG de `<carpeta>/charts` y revisa que se
   lea bien antes de incluirlo.

4. **Interpretar con el conocimiento del sector.** Lee
   `references/sector-<sector>.md`. Hoy solo existe `sector-restaurantes.md`. Si el
   negocio es de otro sector, dilo y pregunta antes de seguir.

5. **Redactar el informe** siguiendo la estructura y el tono de `references/informe.md`.

6. **Escribir los textos del tablero** en `<carpeta>/insights.json`, con los campos
   y límites de `references/informe.md`. Son un resumen del informe, no texto nuevo.

7. **Generar el tablero.** Las cifras las pone el script; no se escriben a mano.

   ```
   .venv\Scripts\python -m src.dashboard --survey <csv> --reviews <csv> --insights <carpeta>/insights.json --comments <carpeta>/comments/comment_metrics.json --output <carpeta>/dashboard.html
   ```

   Ábrelo y revisa que se vea bien y que no haya errores.

8. **Revisar.** Recorre el informe y los textos del tablero cifra por cifra y
   compáralos con `metrics.json` y `comment_metrics.json`. Las citas de clientes se
   copian tal cual, con sus errores. Corrige cualquier diferencia antes de entregar.

## Reglas

- Toda recomendación se apoya en una cifra del análisis, citada junto a ella.
- Los datos dicen qué pasó, no por qué. Las causas se escriben como hipótesis para
  confirmar con el dueño.
- Máximo tres prioridades.
- Junto a cada cifra importante, cuántas respuestas o reseñas hay detrás. Como hay
  preguntas sin responder, la base de cada cifra es menor que el total: tómala de
  `answered`, `previous_n` y `recent_n` en `metrics.json`, no del número de filas.
- Lo marcado como [Criterio] en el archivo del sector se presenta como sugerencia.
  Lo marcado como [Evidencia] se cita como referencia de otros mercados, nunca como
  promesa de resultado.
- No recomendar incentivos a cambio de reseñas.

## Salida

| | Dataset sintético | Cliente real |
|---|---|---|
| Tablero (se entrega) | `examples/dashboard-ejemplo.html` | `data/private/<cliente>/dashboard.html` |
| Informe (interno) | `examples/informe-ejemplo.md` | `data/private/<cliente>/informe.md` |
| Textos del tablero | `examples/insights.json` | `data/private/<cliente>/insights.json` |

El informe enlaza las gráficas PNG por ruta relativa. El tablero es un solo archivo
que abre sin internet.

---
name: informe-insights
description: Genera el informe de insights de Tagi para un negocio a partir de las respuestas de su formulario de clientes y sus reseñas de Google: métricas clave, gráficas, qué cambió y un plan de acción priorizado para el dueño. Usar cuando pidan un informe, reporte o análisis de un restaurante o cliente de Tagi, o cuando entreguen archivos de encuestas o reseñas para analizar.
---

# Informe de insights

El lector es el dueño del negocio: ocupado, no técnico, quiere saber qué hacer.
El informe vale por el plan de acción, no por la cantidad de cifras.

## Entradas

Dos archivos CSV con las columnas definidas en `src/survey_schema.py`:
respuestas del formulario y reseñas de Google. Si no se indica ninguno, se usa el
dataset sintético de `data/sample/`.

Si los archivos son de un cliente real, viven en `data/private/<cliente>/` y todo
lo que se genere (cifras, gráficas, informe) se guarda en esa misma carpeta. Nada
de un cliente real se copia, cita ni resume fuera de `data/private/`.

## Pasos

1. **Cargar, limpiar y calcular.** Un solo comando hace las tres cosas y entrega un
   JSON con el reporte de limpieza y todas las cifras:

   ```
   .venv\Scripts\python -m src.metrics --survey <csv> --reviews <csv> --output <carpeta>/metrics.json
   ```

   Si el comando falla porque faltan columnas, detente y repórtalo; no adaptes los
   datos a mano.

2. **Usar solo esas cifras.** Toda cifra del informe sale de `metrics.json`. No
   calcules promedios, porcentajes ni diferencias de cabeza. Si hace falta una
   cifra que no está, agrégala a `src/metrics.py` con su test.

3. **Generar las gráficas.**

   ```
   .venv\Scripts\python -m src.charts --survey <csv> --reviews <csv> --output-dir <carpeta>/charts
   ```

   Abre cada PNG y revisa que se lea bien antes de incluirlo.

4. **Interpretar con el conocimiento del sector.** Lee
   `references/sector-<sector>.md`. Hoy solo existe `sector-restaurantes.md`. Si el
   negocio es de otro sector, dilo y pregunta antes de seguir.

5. **Redactar** siguiendo la estructura y el tono de `references/informe.md`.

6. **Revisar.** Recorre el informe cifra por cifra y compárala con `metrics.json`.
   Corrige cualquier diferencia antes de entregarlo.

## Reglas

- Toda recomendación se apoya en una cifra del análisis, citada junto a ella.
- Los datos dicen qué pasó, no por qué. Las causas se escriben como hipótesis para
  confirmar con el dueño.
- Máximo tres prioridades.
- Junto a cada cifra importante, cuántas respuestas o reseñas hay detrás.
- Lo marcado como [Criterio] en el archivo del sector se presenta como sugerencia.
  Lo marcado como [Evidencia] se cita como referencia de otros mercados, nunca como
  promesa de resultado.
- No recomendar incentivos a cambio de reseñas.

## Salida

Un archivo Markdown con las gráficas enlazadas por ruta relativa. Con el dataset
sintético: `examples/informe-ejemplo.md`. Con un cliente real:
`data/private/<cliente>/informe.md`.

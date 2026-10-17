# Textos del tablero

El tablero muestra las cifras por su cuenta: estrellas, satisfechos, respuestas,
la tendencia mensual, los temas de los comentarios con sus citas y las reseñas. Lo
único que se escribe a mano es `insights.json`: el resumen, la alerta, el plan de
acción, el siguiente nivel, las preguntas para el dueño y la nota sobre los datos.

Quien lo lee es el dueño del negocio: ocupado, no técnico, lo abre en el celular.

## Tono

- Trate al lector de **usted**.
- Frases cortas y directas. Sin jerga de datos: nada de "media", "outlier" o
  "correlación".
- Primero la conclusión, después la cifra que la respalda.
- Honesto con lo malo y concreto con lo bueno. Sin adjetivos de relleno.
- Las acciones empiezan con un verbo y dicen quién, qué y para cuándo.
- Hable del negocio con sus propias palabras: si es un taller, "el arreglo", no
  "el producto".

## Formato de las cifras

- Calificaciones: un decimal (4.1).
- Porcentajes: sin decimales (71%).
- Cambios de una calificación: con signo y un decimal (-0.9). Cambios de una
  proporción: en puntos (+20 puntos). Cuando escriba el antes y el ahora, el cambio
  es la resta de esas dos cifras ya redondeadas, para que le cuadre a quien lee: de
  4.3 a 3.4 es -0.9, aunque el valor exacto sea -0.88.
- Fechas: "julio de 2026", no "2026-07".

## Antes de escribir

Responda para usted estas preguntas con las cifras de `metrics.json` y
`comment_metrics.json`. No se escriben en ningún archivo, pero cada texto del
tablero sale de ellas:

1. **Cómo está el negocio hoy:** estrellas, satisfechos y respuestas, antes y en
   los últimos meses. ¿Está cerca de 4.0 o de 4.5?
2. **Qué cambió:** desde cuándo y cuánto. ¿Cambió también el número de reseñas por
   mes? Menos reseñas y peores no es lo mismo que las mismas reseñas pero peores.
3. **Qué dicen los comentarios:** las quejas y elogios que más crecen o caen en
   proporción, los detalles pequeños (`small_details`) y las sugerencias. Una queja
   que crece justo cuando caen las estrellas es la pista más concreta sobre qué
   arreglar, aunque no sea la causa confirmada.
4. **Qué funciona y hay que proteger:** los elogios más repetidos y estables.
5. **En qué concentrarse:** una prioridad principal, máximo tres.

## Campos de `insights.json`

Todos son obligatorios.

| Campo | Qué es | Límite |
|---|---|---|
| `business_name` | Nombre del negocio | |
| `headline` | Segunda mitad del título, en minúscula | 8 palabras |
| `summary` | Cómo está el negocio, qué es lo más importante que cambió y qué debe hacer primero | 2 frases |
| `alert` | Lo más urgente, con su cifra. Empieza en minúscula porque sigue a "Atención prioritaria:". Texto vacío si no hay nada urgente | 1 frase |
| `actions` | El plan de acción | 3 a 6 |
| `next_level` | Qué falta para subir de categoría una vez resuelto lo urgente, apoyado en lo que hay que proteger | 3 frases |
| `questions` | Las hipótesis que solo el dueño puede confirmar (por ejemplo, si hubo cambios de personal en la fecha de la caída) | 2 a 4 |
| `data_note` | Qué no puede decir el tablero: bases pequeñas, que las causas son hipótesis | 2 frases |

Cada acción tiene:

- `horizon`: `this_week`, `this_month` u `ongoing`.
- `title`: empieza con un verbo, máximo 6 palabras.
- `text`: qué hacer, máximo 2 frases.
- `why`: la cifra que la justifica, en una línea corta.

Entre las acciones debe haber al menos una por cada prioridad, y conviene nombrar
los detalles pequeños: son lo más fácil de mantener o recuperar.

Ejemplo completo: `examples/insights.json`.

# Estructura y tono del informe y del tablero

El informe es el documento interno de Tagi; el tablero es lo que recibe el dueño.
El tono y el formato de cifras de abajo aplican a los dos. Las secciones del
informe están primero; los textos del tablero, al final.

## Tono

- Trate al lector de **usted**.
- Frases cortas y directas. Sin jerga de datos: nada de "media", "outlier" o
  "correlación". Si usa un término técnico, explíquelo en una línea la primera vez.
- Primero la conclusión, después la cifra que la respalda.
- Honesto con lo malo y concreto con lo bueno. Sin adjetivos de relleno.
- Las acciones empiezan con un verbo y dicen quién, qué y para cuándo.

## Formato de las cifras

- Calificaciones: un decimal (4.1).
- Porcentajes: sin decimales (71%).
- Cambios de una calificación: con signo y un decimal (-0.9). Cambios de una
  proporción: en puntos (+20 puntos). Cuando escriba el antes y el ahora, el cambio
  es la resta de esas dos cifras ya redondeadas, para que le cuadre a quien lee: de
  4.3 a 3.4 es -0.9, aunque el valor exacto sea -0.88.
- Fechas: "julio de 2026", no "2026-07".

## Secciones

El informe responde seis preguntas, en este orden.

### Encabezado
Nombre del negocio, periodo analizado, número de reseñas y cuántas traen comentario.

### Resumen
Tres líneas como máximo: cómo está el negocio, qué es lo más importante que cambió
y qué debe hacer primero. Quien solo lea esto debe poder actuar.

### 1. Cómo está el negocio hoy
Tabla corta con las métricas clave, cada una antes y en los últimos meses:
estrellas promedio, clientes satisfechos (4 y 5 estrellas) y reseñas respondidas
por el dueño. Además, el promedio total, que es el que Google muestra. Una línea de
lectura por métrica, no solo el número. Mencione los umbrales de 4.0 y 4.5 cuando
el negocio esté cerca de uno.

### 2. Qué cambió
Desde cuándo y cuánto cambiaron las estrellas, con la gráfica mensual. Diga si
cambió también el número de reseñas por mes: menos reseñas y peores no es lo mismo
que las mismas reseñas pero peores.

### Qué dicen los comentarios
Va después de "Qué cambió", porque explica con palabras de los clientes lo que las
calificaciones muestran. Sale de `comment_metrics.json`:

- Las tres quejas más frecuentes, con cuántas menciones y qué proporción de los
  comentarios ocupan antes y ahora. Una o dos citas textuales de la principal.
- Los tres elogios más frecuentes.
- Los detalles pequeños (`small_details`): qué es, cuántas menciones y una cita.
  Es lo más fácil de mantener o recuperar, así que conviene nombrarlos siempre.
- Las sugerencias que más se repiten.

Cuando una queja crece justo cuando caen las estrellas (por ejemplo, tiempos de
espera), dígalo: es la pista más concreta sobre qué arreglar. Sigue siendo lo que
los clientes dicen, no la causa confirmada.

### 3. Qué funciona y hay que proteger
Los elogios más repetidos y estables en los comentarios. Es lo que no debe
tocarse al arreglar lo demás.

### 4. En qué concentrarse
Una prioridad principal, máximo tres. Para cada una: qué muestran los datos y por
qué va primero.

### 5. Plan de acción
Tres plazos: **esta semana**, **este mes**, **continuo**. Para cada acción:

- qué hacer,
- la cifra que la justifica,
- cómo saber en el próximo informe si funcionó.

### 6. El siguiente nivel
Qué falta para subir de categoría una vez resuelto lo urgente.

### Preguntas para usted
Las hipótesis que solo el dueño puede confirmar (por ejemplo, si hubo cambios de
personal en la fecha de la caída). Dos a cuatro preguntas.

### Sobre estos datos
Cuántas reseñas se leyeron, cuántos duplicados se quitaron, qué no puede decir
este informe. Breve.

## Textos del tablero (`insights.json`)

El tablero muestra las cifras por su cuenta. Este archivo solo trae los textos, y
cada uno resume algo que ya está en el informe. Todos los campos son obligatorios.

| Campo | Qué es | Límite |
|---|---|---|
| `business_name` | Nombre del negocio | |
| `headline` | Segunda mitad del título, en minúscula | 8 palabras |
| `summary` | El resumen del informe | 2 frases |
| `alert` | Lo más urgente, con su cifra. Empieza en minúscula porque sigue a "Atención prioritaria:". Texto vacío si no hay nada urgente | 1 frase |
| `actions` | Las acciones del plan | 3 a 6 |
| `next_level` | La sección "El siguiente nivel" | 3 frases |
| `questions` | Las preguntas para el dueño | 2 a 4 |
| `data_note` | Qué no puede decir el tablero | 2 frases |

Cada acción tiene:

- `horizon`: `this_week`, `this_month` u `ongoing`.
- `title`: empieza con un verbo, máximo 6 palabras.
- `text`: qué hacer, máximo 2 frases.
- `why`: la cifra que la justifica, en una línea corta.

Ejemplo completo: `examples/insights.json`.

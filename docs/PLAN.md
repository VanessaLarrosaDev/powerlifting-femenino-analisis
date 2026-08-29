# Plan del proyecto

Proyecto final del Máster en Data Analytics. Definido en agosto de 2026.

Este documento fija el alcance y las decisiones metodológicas. Sirve de referencia:
si algo se desvía de aquí, conviene revisarlo antes de cambiarlo.

---

## 1. Pregunta que vertebra el proyecto

¿Cómo ha crecido el powerlifting femenino en el mundo, qué determina el rendimiento
de una atleta, y qué papel juega el contexto social de su país?

Cubre las tres dimensiones que exige la entrega: descriptiva, analítica y un ángulo
propio que diferencia el trabajo.

## 2. Preguntas de análisis

**P1. ¿Cuánto y dónde ha crecido la participación femenina?**
Series temporales, tasas de crecimiento compuesto y análisis geográfico. Demuestra
manipulación y agregación de datos.

**P2. ¿Qué determina el rendimiento: peso corporal, edad, experiencia, material?**
Modelo alométrico, contrastes de hipótesis y tamaños de efecto. Demuestra
estadística inferencial.

**P3. ¿Influye el contexto de igualdad y desarrollo del país?**
Correlación cruda, parcial y de corte transversal. Demuestra integración de fuentes
y rigor metodológico.

**P4. ¿Se puede predecir la marca de una atleta, y qué la explica?**
Gradient boosting, validación temporal e importancia de variables. Demuestra
machine learning.

## 3. Alcance

Entran en el análisis el powerlifting completo (sentadilla, press de banca y peso
muerto), la competición femenina sancionada oficialmente, el periodo de 1975 a 2026
y las 83 columnas del conjunto final.

Quedan fuera las modalidades parciales, como solo press de banca o solo peso muerto;
la predicción de lesiones, para la que no existen datos; y la brecha con los hombres
como objeto principal, que se usa únicamente como métrica de contexto y con la
advertencia metodológica correspondiente.

### El sesgo de Estados Unidos

Estados Unidos concentra el 68% de los registros. La decisión tomada es no ocultarlo
ni eliminarlo, sino separar dos niveles de lectura presentes en el análisis, el
informe y el dashboard.

El nivel global usa todos los datos, y cada conclusión advierte de que refleja sobre
todo la realidad estadounidense. El nivel comparado internacional se restringe a los
países con volumen suficiente para ser comparables, y es el único válido para
afirmar algo sobre diferencias entre países.

La distinción se materializa en la columna `ambito_analisis` del conjunto final,
que etiqueta cada registro según si su país alcanza el volumen necesario para ser
comparable. La segunda página del dashboard aplica ese criterio.

El motivo de plantearlo así es que detectar el sesgo y tomar una postura explícita
ante él vale más que presentar un resultado limpio pero engañoso.

## 4. Capa de machine learning

El objetivo es doble: predecir la marca de una atleta y, sobre todo, explicar qué la
determina.

Se emplea gradient boosting mediante `HistGradientBoostingRegressor`, adecuado para
datos tabulares y tolerante a valores ausentes.

La validación es temporal: se entrena con los años anteriores y se valida con los
posteriores, simulando el uso real. No se usa validación aleatoria, que inflaría los
resultados de forma artificial.

Se comparan dos modelos para cuantificar cuánto aporta la trayectoria. El modelo de
perfil emplea solo variables estructurales (peso, edad, equipamiento, país, año,
experiencia). El modelo con historial añade las marcas anteriores de la atleta.

El control de fuga de datos es estricto: se excluyen todas las variables que
contienen la respuesta (los tres levantamientos parciales, DOTS, Wilks, la fuerza
relativa y las brechas) y las medidas del propio evento a predecir.

La explicabilidad se obtiene por importancia de permutación, que resulta fiable ante
variables correlacionadas.

Todo se compara contra una línea base que predice siempre la media, para que las
métricas signifiquen algo.

## 5. Capa SQL

El conjunto final se carga en una base SQLite acompañada de un fichero de consultas
analíticas con agregaciones, CTEs y funciones de ventana que reproducen parte del
análisis.

La base ocupa 357 MB con sus índices, así que no se versiona: se genera ejecutando
`src/base_datos.py`. El repositorio guarda el script que la construye, las consultas
y sus resultados en CSV.

Se elige SQLite en lugar de PostgreSQL porque el fichero `.db` viaja dentro del
repositorio, de modo que cualquiera puede clonarlo y ejecutar las consultas sin
instalar ni levantar un servidor. El SQL analítico es prácticamente idéntico en
ambos motores.

## 6. Formato del análisis

Los notebooks de `notebooks/` recogen el recorrido paso a paso, con explicación en
texto entre el código y los gráficos. Es el formato que se espera en la entrega y el
que permite seguir el razonamiento junto a los resultados.

Los módulos de `src/` se mantienen como motor reutilizable y reproducible. Los
notebooks los importan en lugar de duplicar lógica.

## 7. Entregables

1. Dos conjuntos en bruto de fuentes distintas, en `data/raw/`
2. Conjunto final transformado, en `data/processed/`
3. Análisis exhaustivo, en `notebooks/` y `reports/`
4. Capa de machine learning, en `src/modelos.py` y su notebook
5. Capa SQL, en `sql/`
6. Dashboard operativo en Power BI, en `dashboard/`
7. Informe del análisis, en `reports/`
8. README del repositorio
9. Publicación en GitHub

## 8. Fases de trabajo

1. Generar las figuras del análisis
2. Notebooks narrados: extracción, transformación y análisis
3. Capa de machine learning: modelos, validación temporal y explicabilidad
4. Capa SQL: base SQLite y consultas analíticas
5. Dashboard en Power BI: datos optimizados y documentación
6. Informe del análisis
7. README y publicación en GitHub

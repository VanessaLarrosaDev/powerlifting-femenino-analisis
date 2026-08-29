# Documentación del dashboard

El dashboard está construido en Power BI Desktop sobre el conjunto final del
proyecto. El fichero es `powerbi-dashboard.pbix` y lleva los datos incrustados, de
modo que se abre y funciona sin necesidad de regenerar nada.

## Modelo de datos

Se ha optado por un esquema en estrella con una tabla de hechos y tres dimensiones,
en lugar de una única tabla plana. El motivo es que los indicadores socioeconómicos
son atributos del país y del año, no de cada participación, y repetirlos en cada una
de las 825.296 filas multiplicaría el tamaño del modelo sin aportar nada.

| Tabla | Filas | Grano |
|---|---|---|
| `hechos` | 825.296 | Una participación de una atleta en una competición |
| `dim_calendario` | 18.602 | Un día, de 1975 a 2026 |
| `dim_pais_anio` | 1.567 | Un país en un año |
| `dim_atleta` | 227.570 | Una atleta |

### Relaciones

Las tres son de varios a uno y con filtrado cruzado simple.

| Desde | Hacia |
|---|---|
| `hechos[fecha]` | `dim_calendario[fecha]` |
| `hechos[clave_pais_anio]` | `dim_pais_anio[clave_pais_anio]` |
| `hechos[id_atleta]` | `dim_atleta[id_atleta]` |

Se descartó el filtrado bidireccional porque introduce ambigüedad cuando existen
varias rutas posibles entre tablas, y produce totales incorrectos que no generan
ningún aviso.

La unión con la dimensión de país se hace por `clave_pais_anio`, una columna que
combina el código ISO3 con el año (`ESP-2023`). Enlazar solo por país duplicaría
filas, ya que esa dimensión tiene una entrada por cada combinación de país y año.

### Tabla de fechas

`dim_calendario` está marcada como tabla de fechas, requisito de Power BI para que
funcionen las comparativas interanuales y los acumulados. Es una tabla continua sin
huecos, construida en `src/exportar_powerbi.py`.

## Medidas

El modelo incluye 23 medidas en DAX agrupadas en una tabla `Medidas`. Su definición
está en `medidas.dax`.

Las de rendimiento usan mediana y no promedio. Las distribuciones de marcas son
asimétricas, con una cola larga hacia los valores altos, de modo que la media queda
inflada por las atletas de élite y no describe el nivel típico.

La medida `Cuota femenina %` merece una nota. Se calcula agregando personas, como el
total de mujeres dividido entre el total de participantes, y no promediando la
columna de porcentaje. Un promedio daría media simple entre países, y entonces una
competición exclusivamente femenina, con cuota del 100%, pesaría lo mismo que
Estados Unidos entero.

Para la brecha respecto a los hombres se emplea `brecha_fuerza_rel_pct` y nunca los
puntos DOTS. DOTS y Wilks aplican coeficientes distintos a cada sexo, precisamente
para permitir comparaciones dentro de un mismo sexo, así que usarlos entre sexos
produce el resultado absurdo de que las mujeres levantan más.

## Las páginas

El dashboard tiene dos páginas, correspondientes a las dos preguntas del proyecto
que mejor se prestan a la exploración interactiva. Las otras dos, la del rendimiento
y la de la trayectoria, se desarrollan en los notebooks y en el informe, donde las
figuras generadas con matplotlib permiten un detalle que Power BI no alcanza.

### Página 1. Panorama

Responde a cuánto y dónde ha crecido la participación femenina.

Cinco indicadores en la banda superior: atletas únicas, participaciones, total
mediano en kilos, países y competiciones.

| Visual | Tipo | Configuración |
|---|---|---|
| Crecimiento de atletas | Áreas | Eje X `dim_calendario[anio]`, eje Y `Atletas únicas` |
| Cuota femenina | Columnas | Eje X `dim_pais_anio[anio]`, eje Y `Cuota femenina %` |
| Distribución mundial | Mapa coroplético | Ubicación `dim_pais_anio[iso3]`, color por formato condicional sobre `Atletas únicas` |
| Ranking de países | Barras horizontales | Eje Y `pais_competicion`, eje X `Atletas únicas`, los 15 primeros |

El eje de la cuota femenina procede de `dim_pais_anio` y no del calendario. La
medida lee de esa tabla, y como ambas dimensiones se relacionan con los hechos pero
no entre sí, un eje tomado del calendario no llegaría a filtrar la medida y la serie
saldría plana.

El mapa y el ranking son complementarios: el primero muestra la distribución de un
vistazo y el segundo aporta las cifras, con Estados Unidos en 139.820 atletas frente
a las 14.229 del segundo país.

### Página 2. Contexto internacional

Responde a si el contexto social del país influye en la participación femenina.

| Visual | Tipo | Configuración |
|---|---|---|
| Renta y participación | Dispersión | X `PIB per cápita medio`, Y `Cuota femenina %`, Valores `pais_competicion`, con línea de tendencia |
| Desigualdad y participación | Dispersión | X `GII medio`, Y `Cuota femenina %`, Valores `pais_competicion`, con línea de tendencia |

Los dos gráficos se leen en conjunto: la línea de tendencia de la renta asciende y
la del índice de desigualdad es plana. Debajo, un cuadro de texto recoge la
conclusión con las cifras del análisis.

Se descartó un gráfico de barras que agregaba la cuota por grupo de renta. Los
grupos resultaban incomparables en volumen, ya que el de renta baja reunía 5.936
participaciones femeninas frente a las 417.145 del de renta alta, y dos tercios de
ese grupo correspondían a un único país. El agregado sugería una relación
inexistente, mientras que los gráficos de dispersión muestran el dato real: un país,
un punto.

## El sesgo geográfico

El conjunto final incluye la columna `ambito_analisis`, que etiqueta cada registro
según si su país alcanza los 2.000 registros necesarios para considerarse comparable
internacionalmente. Treinta países cumplen ese umbral y cubren el 96,3% de los
datos.

La segunda página aplica ese criterio, ya que comparar países exige restringirse a
los que tienen volumen suficiente. La primera trabaja con el conjunto completo y
advierte en el título del mapa del predominio norteamericano.

## Regenerar los datos de origen

Los ficheros que alimentan el modelo no se versionan, porque son datos derivados del
conjunto final, que sí está en el repositorio. Se generan con:

```bash
python src/exportar_powerbi.py
```

Eso crea cuatro tablas en `dashboard/datos/`, en Parquet y en CSV:

| Tabla | Parquet | CSV |
|---|---|---|
| `hechos` | 30,4 MB | 240,1 MB |
| `dim_atleta` | 8,3 MB | 21,9 MB |
| `dim_calendario` | 0,2 MB | 0,9 MB |
| `dim_pais_anio` | 0,1 MB | 0,3 MB |

El formato Parquet ocupa un 85% menos y carga mucho más rápido, pero sobre todo
conserva los tipos de datos. Eso evita los problemas habituales del CSV: fechas
leídas como texto, columnas decimales con nulos interpretadas como enteras, o
indicadores booleanos que llegan como la cadena "True" y rompen los filtros de las
medidas.

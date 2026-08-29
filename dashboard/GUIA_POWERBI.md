# Documentación del dashboard

Construcción del dashboard del proyecto en Power BI Desktop. Los pasos van en orden
porque el modelo de datos condiciona todo lo demás: empezar por los gráficos obliga
a rehacerlos después.

Verificado con Power BI Desktop 2.157.

---

## 1. Generar los datos

```bash
python src/exportar_powerbi.py
```

Crea cuatro tablas en `dashboard/datos/`, cada una en dos formatos:

| Tabla | Filas | Parquet | CSV | Contenido |
|---|---|---|---|---|
| `hechos` | 825.296 | 30,4 MB | 240,1 MB | Una fila por participación |
| `dim_pais_anio` | 1.567 | 0,1 MB | 0,3 MB | Contexto socioeconómico por país y año |
| `dim_atleta` | 227.570 | 8,3 MB | 21,9 MB | Una fila por atleta con su trayectoria |
| `dim_calendario` | 18.602 | 0,2 MB | 0,9 MB | Tabla de fechas continua |
| Total | | 39 MB | 263 MB | |

Estos ficheros no se versionan, porque son datos derivados del conjunto final, que sí
está en el repositorio. El `.pbix` en cambio sí se versiona: Power BI comprime con
VertiPaq y ocupa una fracción de los CSV.

## 2. Importar

Conviene usar los ficheros `.parquet`, desde `Obtener datos > Más > Archivo >
Parquet`. Pesan un 85% menos que los CSV y cargan en segundos, pero la razón
principal es otra: conservan los tipos de datos. No hay que revisar ni corregir nada,
porque las fechas llegan como fechas, los decimales con nulos como decimales y los
indicadores como enteros. Con CSV, Power BI adivina los tipos y se equivoca justo en
los casos molestos. Parquet guarda además el texto en UTF-8 por definición, así que
los acentos nunca se rompen.

Al importar Parquet basta pulsar Cargar, sin pasar por Transformar datos.

Si se prefiere trabajar con los CSV, hay que comprobar que el origen de archivo sea
`65001: Unicode (UTF-8)`. Los ficheros llevan BOM y Power BI debería detectarlo, pero
si aparece `MÃ©xico` en lugar de `México` la codificación está mal. En ese caso hay
que entrar en Transformar datos y ajustar estos tipos:

| Columna | Tipo correcto |
|---|---|
| `fecha`, `primera_fecha`, `ultima_fecha` | Fecha |
| `total_kg`, `fuerza_relativa`, `puntos_dots`, `peso_corporal_kg` | Número decimal |
| `es_podio`, `es_debut`, `es_record_personal` | Número entero (0/1) |
| `edad`, `posicion` | Número decimal, porque tienen nulos y como enteros dan error |
| `iso3`, `clave_pais_anio` | Texto |

## 3. Configurar el modelo

En la vista Modelo, crear tres relaciones arrastrando de una columna a otra:

| Desde (hechos) | Hacia (dimensión) | Cardinalidad |
|---|---|---|
| `hechos[fecha]` | `dim_calendario[fecha]` | Varios a uno |
| `hechos[clave_pais_anio]` | `dim_pais_anio[clave_pais_anio]` | Varios a uno |
| `hechos[id_atleta]` | `dim_atleta[id_atleta]` | Varios a uno |

El filtrado cruzado debe quedar en Simple, es decir, unidireccional. El bidireccional
parece cómodo pero genera ambigüedad en los cálculos y es una fuente habitual de
errores.

### Marcar la tabla de fechas

Seleccionar `dim_calendario`, ir a `Herramientas de tabla > Marcar como tabla de
fechas` y elegir la columna `fecha`.

Este paso es imprescindible. Sin él, las funciones de inteligencia de tiempo
(comparativas interanuales, acumulados) devuelven resultados incorrectos sin avisar.
Es el error más habitual al montar un modelo en Power BI.

### Ocultar columnas técnicas

Conviene ocultar de la vista de informe `clave_pais_anio`, y también `id_atleta` e
`iso3` en la tabla de hechos. Reducen el ruido en el panel de campos sin afectar al
modelo.

## 4. Medidas DAX

Están todas en `medidas.dax`, listas para copiar. Para agruparlas, crear una tabla
vacía con `_Medidas = {1}`, ocultar su única columna y crear las medidas dentro.

Cubren cinco bloques: volumen y participación (participaciones, atletas únicas,
competiciones, países); rendimiento, siempre con mediana en lugar de media porque las
distribuciones son asimétricas; crecimiento, que requiere la tabla de fechas marcada;
resultado deportivo y trayectoria, incluida la tasa de retención; y contexto
socioeconómico.

Una advertencia sobre la brecha frente a los hombres: hay que usar
`brecha_fuerza_rel_pct` y nunca los puntos DOTS. DOTS y Wilks aplican coeficientes
distintos por sexo, de modo que no sirven para comparar sexos. Está explicado en el
informe.

Tras crearlas, dar formato a cada medida en Herramientas de medidas: porcentaje con
un decimal para las de `%`, número decimal con un decimal para los kg, y número
entero con separador de miles para los recuentos.

## 5. El filtro de ámbito

Antes de los gráficos conviene resolver esto, porque afecta a todas las páginas. La
columna `ambito_analisis` implementa la decisión sobre el sesgo de Estados Unidos,
que concentra el 68% de los registros.

En cada página se añade una segmentación de datos con `hechos[ambito_analisis]`, en
formato lista o botones. Distingue entre los países comparables
internacionalmente, que son los que tienen 2.000 registros o más y el único ámbito
válido para comparar países entre sí, y el resto.

Junto al filtro conviene poner un cuadro de texto que lo explique: los análisis
globales están dominados por Estados Unidos, así que para comparar países hay que
filtrar por "Comparable internacionalmente".

Así una limitación de los datos se convierte en una funcionalidad del dashboard, y
queda claro que el sesgo está identificado y gestionado.

## 6. Las páginas del dashboard

El dashboard tiene dos páginas, una por cada una de las dos preguntas que mejor se
prestan a la exploración interactiva. Las otras dos preguntas del proyecto, la del
rendimiento y la de la trayectoria, se desarrollan en los notebooks y en el informe,
donde las figuras de matplotlib permiten un detalle que Power BI no alcanza.

### Página 1. Panorama

Responde a cuánto y dónde ha crecido la participación femenina.

Cinco tarjetas de KPI en la banda superior: atletas únicas, participaciones, total
mediano en kilos, países y competiciones.

| Visual | Tipo | Configuración |
|---|---|---|
| Crecimiento de atletas | Áreas | Eje X `dim_calendario[anio]`, eje Y `Atletas únicas` |
| Cuota femenina | Columnas | Eje X `dim_pais_anio[anio]`, eje Y `Cuota femenina %` |
| Distribución mundial | Mapa coroplético | Ubicación `dim_pais_anio[iso3]`, color por formato condicional sobre `Atletas únicas` |
| Ranking de países | Barras horizontales | Eje Y `pais_competicion`, eje X `Atletas únicas`, filtro N superior 15 |

El eje de la cuota femenina debe venir de `dim_pais_anio` y no de `dim_calendario`.
La medida lee de esa tabla, y como ambas dimensiones se relacionan con los hechos
pero no entre sí, un eje tomado del calendario no filtraría la medida y la serie
saldría plana.

### Página 2. Contexto internacional

Responde a si el contexto social del país influye en la participación femenina, que
es la pregunta más original del proyecto.

| Visual | Tipo | Configuración |
|---|---|---|
| Renta y participación | Dispersión | X `PIB per cápita medio`, Y `Cuota femenina %`, Valores `pais_competicion`, con línea de tendencia |
| Desigualdad y participación | Dispersión | X `GII medio`, Y `Cuota femenina %`, Valores `pais_competicion`, con línea de tendencia |

Los dos gráficos se leen en conjunto: la línea de tendencia del PIB asciende y la
del índice de desigualdad es plana. Debajo, un cuadro de texto recoge la conclusión
con las cifras del análisis.

Se descartó un gráfico de barras que agregaba la cuota por grupo de renta. Los
grupos resultaban incomparables en volumen, ya que el de renta baja reunía 5.936
participaciones femeninas frente a las 417.145 del de renta alta, y además dos
tercios de ese grupo correspondían a un solo país. El agregado sugería una relación
inexistente, mientras que los gráficos de dispersión muestran el dato real: un país,
un punto.

## 7. Acabado

Cada página lleva su título en un cuadro de texto arriba a la izquierda, en tamaño 18
a 20.

La paleta se configura en `Ver > Temas > Personalizar el tema actual`, con los mismos
colores del informe: morado `#6C3FA4`, magenta `#C2367F`, verde azulado `#2E8B8B` y
ámbar `#E0A82E`.

Al pie conviene citar las fuentes: OpenPowerlifting (dominio público), Banco Mundial
y PNUD, con datos a 15 de agosto de 2026.

Merece revisar `Formato > Editar interacciones` para que los filtros cruzados tengan
sentido, porque por defecto todo filtra todo y no siempre interesa.

En la información sobre herramientas de cada visual conviene añadir atletas únicas y
participaciones, de modo que al pasar el ratón se vea el volumen que hay detrás de
cada mediana.

## 8. Comprobaciones antes de entregar

Guardar como `dashboard/dashboard_powerlifting_femenino.pbix` y verificar:

- Las cuatro páginas cargan sin errores
- `dim_calendario` está marcada como tabla de fechas
- Las tres relaciones existen y son unidireccionales
- La página 3 arranca filtrada a "Comparable internacionalmente"
- Los acentos se muestran bien (comprobar con "México" y "Chequia")
- Las medianas no aparecen como medias por error
- Cada página lleva su nota metodológica

Si se publica en Power BI Service, añadir el enlace al README.

## Problemas habituales

| Síntoma | Causa y solución |
|---|---|
| Las comparativas interanuales salen vacías o mal | Falta marcar `dim_calendario` como tabla de fechas |
| El mapa no reconoce países | La columna `iso3` necesita categoría de datos País o región |
| El dashboard va lento | La dispersión con 825.000 puntos es el cuello de botella: añadir un filtro Top N |
| Un total no cuadra al filtrar | Revisar la dirección del filtrado cruzado, que debe ser Simple |
| Una medida da el mismo valor en todas las filas | Falta la relación con la dimensión por la que se desglosa |
| Acentos rotos | Solo ocurre con CSV: reimportar con `65001: Unicode (UTF-8)`, o usar el `.parquet` |
| `es_podio` no filtra | Solo con CSV: se importó como texto, hay que pasarlo a entero y usar `= 1` |
| `edad` da error al cargar | Solo con CSV: está como entero y tiene nulos, hay que pasarla a decimal |

Los tres últimos desaparecen usando los ficheros `.parquet`.

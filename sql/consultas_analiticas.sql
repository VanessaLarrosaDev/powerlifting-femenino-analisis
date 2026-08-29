-- ===========================================================================
-- CONSULTAS ANALITICAS
-- Powerlifting femenino mundial: rendimiento y contexto social
-- Base de datos: powerlifting_femenino.db (SQLite)
--
-- Cada consulta responde a una pregunta concreta del analisis y esta pensada
-- para poder ejecutarse de forma independiente.
--
-- Uso:  sqlite3 sql/powerlifting_femenino.db < sql/consultas_analiticas.sql
--   o:  python src/consultas.py       (ejecuta todas y muestra resultados)
-- ===========================================================================


-- ---------------------------------------------------------------------------
-- C1. Evolucion anual de la participacion y del rendimiento
--
-- Responde a P1. Usa una funcion de ventana LAG para calcular la variacion
-- interanual sin necesidad de autounir la tabla consigo misma.
-- ---------------------------------------------------------------------------
WITH por_anio AS (
    SELECT
        anio,
        COUNT(*)                        AS participaciones,
        COUNT(DISTINCT id_atleta)       AS atletas_unicas,
        ROUND(AVG(total_kg), 1)         AS total_medio_kg,
        ROUND(AVG(fuerza_relativa), 3)  AS fuerza_relativa_media,
        ROUND(AVG(edad), 1)             AS edad_media
    FROM hechos_participacion
    WHERE anio BETWEEN 1990 AND 2025
    GROUP BY anio
)
SELECT
    anio,
    participaciones,
    atletas_unicas,
    -- Variacion respecto al anio anterior
    atletas_unicas - LAG(atletas_unicas) OVER (ORDER BY anio) AS variacion_atletas,
    ROUND(100.0 * (atletas_unicas - LAG(atletas_unicas) OVER (ORDER BY anio))
          / LAG(atletas_unicas) OVER (ORDER BY anio), 1)      AS variacion_pct,
    total_medio_kg,
    fuerza_relativa_media,
    edad_media
FROM por_anio
ORDER BY anio DESC
LIMIT 20;


-- ---------------------------------------------------------------------------
-- C2. Ranking de paises: volumen y nivel competitivo
--
-- Responde a P1 (nivel B del plan: solo paises comparables). Combina la tabla
-- de hechos con la dimension de pais y clasifica con RANK.
-- ---------------------------------------------------------------------------
WITH resumen_pais AS (
    SELECT
        h.iso3,
        MAX(p.pais_competicion)             AS pais,
        MAX(p.region)                       AS region,
        COUNT(*)                            AS participaciones,
        COUNT(DISTINCT h.id_atleta)         AS atletas,
        ROUND(AVG(h.total_kg), 1)           AS total_medio,
        ROUND(AVG(h.puntos_dots), 1)        AS dots_medio,
        ROUND(AVG(p.pct_participacion_femenina), 1) AS cuota_femenina,
        ROUND(AVG(p.pib_per_capita_ppa), 0) AS pib_medio
    FROM hechos_participacion h
    JOIN dim_pais_anio p
      ON h.iso3 = p.iso3 AND h.anio = p.anio
    WHERE h.anio >= 2015
    GROUP BY h.iso3
    HAVING COUNT(*) >= 500          -- umbral de comparabilidad
)
SELECT
    RANK() OVER (ORDER BY atletas DESC)     AS puesto_volumen,
    RANK() OVER (ORDER BY dots_medio DESC)  AS puesto_nivel,
    pais, region, atletas, participaciones,
    total_medio, dots_medio, cuota_femenina, pib_medio
FROM resumen_pais
ORDER BY atletas DESC
LIMIT 25;


-- ---------------------------------------------------------------------------
-- C3. Retencion por cohorte de debut
--
-- Responde a P2. Agrupa a las atletas por el anio en que debutaron y mide
-- cuantas siguen compitiendo despues. Es el analisis que revela que el
-- problema del deporte es la RETENCION, no la captacion.
-- ---------------------------------------------------------------------------
WITH debut AS (
    SELECT id_atleta, MIN(anio) AS anio_debut
    FROM hechos_participacion
    GROUP BY id_atleta
),
actividad AS (
    SELECT
        d.anio_debut,
        d.id_atleta,
        COUNT(*)                                  AS total_comp,
        MAX(h.anio) - d.anio_debut                AS anios_activa
    FROM debut d
    JOIN hechos_participacion h ON h.id_atleta = d.id_atleta
    GROUP BY d.anio_debut, d.id_atleta
)
SELECT
    anio_debut                                              AS cohorte,
    COUNT(*)                                                AS atletas_debutantes,
    -- Agregacion condicional: el equivalente SQL de una tabla de retencion
    ROUND(100.0 * SUM(CASE WHEN total_comp   >= 2 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_2_o_mas,
    ROUND(100.0 * SUM(CASE WHEN total_comp   >= 5 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_5_o_mas,
    ROUND(100.0 * SUM(CASE WHEN anios_activa >= 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_sigue_1_anio,
    ROUND(100.0 * SUM(CASE WHEN anios_activa >= 3 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_sigue_3_anios,
    ROUND(AVG(total_comp), 2)                               AS competiciones_medias
FROM actividad
WHERE anio_debut BETWEEN 2010 AND 2022
GROUP BY anio_debut
ORDER BY anio_debut;


-- ---------------------------------------------------------------------------
-- C4. Las atletas con mayor progresion
--
-- Responde a P2. Compara la primera y la ultima marca de cada atleta usando
-- FIRST_VALUE y LAST_VALUE sobre una ventana ordenada por fecha.
-- ---------------------------------------------------------------------------
WITH trayectoria AS (
    SELECT
        h.id_atleta,
        FIRST_VALUE(h.total_kg) OVER v AS primer_total,
        LAST_VALUE(h.total_kg)  OVER v AS ultimo_total,
        COUNT(*)                OVER (PARTITION BY h.id_atleta) AS n_comp
    FROM hechos_participacion h
    WINDOW v AS (
        PARTITION BY h.id_atleta ORDER BY h.fecha
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    )
)
SELECT
    a.nombre_atleta,
    a.iso3_principal            AS pais,
    t.n_comp                    AS competiciones,
    t.primer_total              AS primera_marca_kg,
    t.ultimo_total              AS ultima_marca_kg,
    ROUND(t.ultimo_total - t.primer_total, 1)                       AS mejora_kg,
    ROUND(100.0 * (t.ultimo_total - t.primer_total) / t.primer_total, 1) AS mejora_pct,
    ROUND(a.anios_trayectoria, 1) AS anios
FROM (SELECT DISTINCT * FROM trayectoria) t
JOIN dim_atleta a ON a.id_atleta = t.id_atleta
WHERE t.n_comp >= 8              -- trayectoria suficiente
  AND t.primer_total >= 100      -- descarta debuts anomalos
ORDER BY mejora_pct DESC
LIMIT 20;


-- ---------------------------------------------------------------------------
-- C5. Posicion relativa de cada atleta dentro de su pais y anio
--
-- Metrica del "nivel B" del plan: normalizar dentro de cada pais-anio elimina
-- el sesgo de composicion geografica. PERCENT_RANK devuelve el percentil.
-- ---------------------------------------------------------------------------
WITH percentiles AS (
    SELECT
        id_atleta, iso3, anio, total_kg, puntos_dots,
        ROUND(PERCENT_RANK() OVER (
            PARTITION BY iso3, anio ORDER BY puntos_dots
        ), 4)                                   AS percentil_en_su_pais,
        NTILE(4) OVER (
            PARTITION BY iso3, anio ORDER BY puntos_dots
        )                                       AS cuartil,
        COUNT(*) OVER (PARTITION BY iso3, anio) AS competidoras_pais_anio
    FROM hechos_participacion
    WHERE puntos_dots IS NOT NULL AND anio >= 2020
)
SELECT
    p.iso3, p.anio, p.competidoras_pais_anio,
    a.nombre_atleta,
    p.total_kg, p.puntos_dots,
    p.percentil_en_su_pais, p.cuartil
FROM percentiles p
JOIN dim_atleta a ON a.id_atleta = p.id_atleta
WHERE p.competidoras_pais_anio >= 200
  AND p.percentil_en_su_pais >= 0.999   -- la elite de cada pais-anio
ORDER BY p.anio DESC, p.puntos_dots DESC
LIMIT 20;


-- ---------------------------------------------------------------------------
-- C6. Efecto del equipamiento medido INTRA-ATLETA
--
-- Reproduce en SQL el hallazgo clave del analisis: la comparacion directa
-- entre grupos sugiere que el equipamiento perjudica, pero comparando a cada
-- atleta CONSIGO MISMA el signo se invierte. El sesgo estaba en que el
-- material va ligado a la federacion, y las federaciones difieren en nivel.
-- ---------------------------------------------------------------------------
WITH por_atleta_modalidad AS (
    SELECT
        id_atleta,
        tipo_equipamiento,
        AVG(fuerza_relativa) AS frel
    FROM hechos_participacion
    WHERE fuerza_relativa IS NOT NULL
    GROUP BY id_atleta, tipo_equipamiento
),
pareadas AS (
    -- Solo atletas presentes en AMBAS modalidades
    SELECT
        e.id_atleta,
        e.frel AS frel_equipada,
        r.frel AS frel_sin_equipar,
        e.frel - r.frel AS diferencia
    FROM por_atleta_modalidad e
    JOIN por_atleta_modalidad r ON e.id_atleta = r.id_atleta
    WHERE e.tipo_equipamiento = 'Con equipamiento (Equipped)'
      AND r.tipo_equipamiento = 'Sin equipamiento (Raw)'
)
SELECT
    'Comparacion pareada (intra-atleta)' AS metodo,
    COUNT(*)                             AS n_atletas,
    ROUND(AVG(frel_equipada), 3)         AS frel_equipada,
    ROUND(AVG(frel_sin_equipar), 3)      AS frel_sin_equipar,
    ROUND(AVG(diferencia), 3)            AS diferencia_media,
    ROUND(100.0 * AVG(diferencia) / AVG(frel_sin_equipar), 1) AS ventaja_pct
FROM pareadas

UNION ALL

SELECT
    'Comparacion directa entre grupos'   AS metodo,
    COUNT(DISTINCT id_atleta)            AS n_atletas,
    ROUND(AVG(CASE WHEN tipo_equipamiento = 'Con equipamiento (Equipped)'
                   THEN fuerza_relativa END), 3) AS frel_equipada,
    ROUND(AVG(CASE WHEN tipo_equipamiento = 'Sin equipamiento (Raw)'
                   THEN fuerza_relativa END), 3) AS frel_sin_equipar,
    NULL, NULL
FROM hechos_participacion;


-- ---------------------------------------------------------------------------
-- C7. Cuota femenina frente al contexto economico del pais
--
-- Responde a P3. Solo indicadores OBSERVADOS (no propagados) y paises con
-- volumen suficiente, que es la unica lectura valida entre paises.
-- ---------------------------------------------------------------------------
SELECT
    p.grupo_renta,
    p.grupo_desigualdad,
    COUNT(DISTINCT p.iso3)                              AS paises,
    SUM(p.n_mujeres_pais_anio)                          AS mujeres,
    SUM(p.n_hombres_pais_anio)                          AS hombres,
    ROUND(AVG(p.pct_participacion_femenina), 2)         AS cuota_femenina_media,
    ROUND(AVG(p.indice_desigualdad_gen), 3)             AS gii_medio,
    ROUND(AVG(p.pib_per_capita_ppa), 0)                 AS pib_medio
FROM dim_pais_anio p
WHERE p.indicadores_imputados = 0
  AND p.anio BETWEEN 2015 AND 2022
  AND p.n_mujeres_pais_anio + p.n_hombres_pais_anio >= 100
  AND p.grupo_renta IS NOT NULL
GROUP BY p.grupo_renta, p.grupo_desigualdad
ORDER BY cuota_femenina_media DESC;


-- ---------------------------------------------------------------------------
-- C8. Marcas de referencia por categoria de peso y decada
--
-- Tabla cruzada construida con agregacion condicional (el patron clasico de
-- pivot en SQL). Muestra la evolucion del nivel maximo en cada categoria.
-- ---------------------------------------------------------------------------
SELECT
    categoria_peso,
    COUNT(*)                                                    AS registros,
    ROUND(MAX(CASE WHEN decada = '1990s' THEN total_kg END), 1) AS max_1990s,
    ROUND(MAX(CASE WHEN decada = '2000s' THEN total_kg END), 1) AS max_2000s,
    ROUND(MAX(CASE WHEN decada = '2010s' THEN total_kg END), 1) AS max_2010s,
    ROUND(MAX(CASE WHEN decada = '2020s' THEN total_kg END), 1) AS max_2020s,
    ROUND(AVG(CASE WHEN decada = '2020s' THEN total_kg END), 1) AS media_2020s,
    ROUND(AVG(CASE WHEN decada = '2020s' THEN fuerza_relativa END), 3)
                                                                AS frel_2020s
FROM hechos_participacion
WHERE categoria_peso IS NOT NULL
GROUP BY categoria_peso
ORDER BY registros DESC;


-- ---------------------------------------------------------------------------
-- C9. Reparto de la fuerza entre los tres movimientos por perfil
--
-- Responde a P2: confirma que el reparto es muy estable y que el perfil
-- dominante no se traduce en mas exito competitivo.
-- ---------------------------------------------------------------------------
SELECT
    perfil_fuerza,
    COUNT(*)                                    AS registros,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_del_total,
    ROUND(AVG(pct_sentadilla), 2)               AS pct_sentadilla,
    ROUND(AVG(pct_banca), 2)                    AS pct_banca,
    ROUND(AVG(pct_peso_muerto), 2)              AS pct_peso_muerto,
    ROUND(AVG(total_kg), 1)                     AS total_medio,
    ROUND(AVG(puntos_dots), 1)                  AS dots_medio,
    ROUND(100.0 * AVG(CAST(es_podio AS REAL)), 1) AS pct_podio
FROM hechos_participacion
WHERE perfil_fuerza IS NOT NULL
GROUP BY perfil_fuerza
ORDER BY registros DESC;

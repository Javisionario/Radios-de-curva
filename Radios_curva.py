from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingException,
    QgsFeature,
    QgsFields,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsFeatureSink,
    QgsWkbTypes,
)

import processing
import math

class ExtraerCurvasYCentroides(QgsProcessingAlgorithm):
    """
    Extrae segmentos de curva de líneas densificadas, calcula su radio de curvatura,
    agrupa centros cercanos y genera dos capas:
      • Curvas: ID_Curva, ID_Centroide, Radio, Longitud
      • Centroides: ID_Centroide, Radio_medio, Conteo
    """

    INPUT_LAYER      = 'INPUT_LAYER'
    INTERVAL         = 'INTERVAL'
    MIN_RADIUS       = 'MIN_RADIUS'
    MAX_RADIUS       = 'MAX_RADIUS'
    MIN_DIST         = 'MIN_DIST'
    ADD_CENTERS      = 'ADD_CENTERS'
    CLUSTER_DISTANCE = 'CLUSTER_DISTANCE'
    OUTPUT_CURVES    = 'OUTPUT_CURVES'
    OUTPUT_CENTERS   = 'OUTPUT_CENTERS'

    def initAlgorithm(self, config=None):
        # Parámetros de entrada
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LAYER, 'Capa de líneas de entrada',
                [QgsProcessing.TypeVectorLine]
            )
        )
        # Distancia entre vértices tras densificar
        self.addParameter(QgsProcessingParameterNumber(
            self.INTERVAL, 'Intervalo de densificación (m)',
            type=QgsProcessingParameterNumber.Double, defaultValue=15.0
        ))
        # Radio mínimo para filtrar curvas muy cerradas
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_RADIUS, 'Radio mínimo (m)',
            type=QgsProcessingParameterNumber.Double, defaultValue=2.0
        ))
        # Radio máximo para filtrar curvas muy suaves
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_RADIUS, 'Radio máximo (m)',
            type=QgsProcessingParameterNumber.Double, defaultValue=50.0
        ))
        # Evitar tripletas de puntos demasiado cercanos
        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_DIST, 'Distancia mínima entre vértices (m)',
            type=QgsProcessingParameterNumber.Double, defaultValue=0.5
        ))
        # Opción de generar capa de centros
        self.addParameter(QgsProcessingParameterBoolean(
            self.ADD_CENTERS, 'Generar capa de centros de curva',
            defaultValue=False
        ))
        # Radio de agrupación de centros cercanos
        self.addParameter(QgsProcessingParameterNumber(
            self.CLUSTER_DISTANCE, 'Distancia de agrupación de centros (m)',
            type=QgsProcessingParameterNumber.Double, defaultValue=10.0
        ))
        # Salida principal: segmentos de curva
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_CURVES, 'Capa de segmentos de curva'
        ))
        # Salida secundaria (opcional): centroides
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_CENTERS, 'Capa de centroides (agrupados)',
            optional=True
        ))

    def name(self):
        return 'extraer_curvas_centroides'

    def displayName(self):
        return 'Extraer curvas y centroides'

    def group(self):
        return 'Análisis de línea'

    def groupId(self):
        return 'line_analysis'

    def createInstance(self):
        return ExtraerCurvasYCentroides()

    def checkParameterValues(self, parameters, context):
        # Validación básica de parámetros
        errores = []
        intervalo = parameters[self.INTERVAL]
        md        = parameters[self.MIN_DIST]
        rmin      = parameters[self.MIN_RADIUS]
        rmax      = parameters[self.MAX_RADIUS]
        cd        = parameters[self.CLUSTER_DISTANCE]
        if intervalo is None or intervalo <= 0:
            errores.append('• Intervalo de densificación debe ser > 0')
        if md is None or md < 0:
            errores.append('• Distancia mínima entre vértices no puede ser negativa')
        if rmin is None or rmax is None or rmin >= rmax:
            errores.append('• Radio mínimo debe ser menor que radio máximo')
        if cd is None or cd < 0:
            errores.append('• Distancia de agrupación debe ser ≥ 0')
        if errores:
            return False, '\n'.join(errores)
        return True, ''

    @staticmethod
    def circle_radius(p1, p2, p3):
        """
        Calcula el radio de la circunferencia circunscrita a los tres puntos.
        Usamos la fórmula de Herón para el área:
          s = (a + b + c) / 2
          área = sqrt[s(s−a)(s−b)(s−c)]
        Luego:
          radio = (a·b·c) / (4·área)
        """
        a = p1.distance(p2)
        b = p2.distance(p3)
        c = p3.distance(p1)
        s = (a + b + c) / 2
        try:
            area = math.sqrt(s * (s - a) * (s - b) * (s - c))
            # evitar división por cero si área muy pequeña
            return (a * b * c) / (4 * area)
        except:
            return None

    @staticmethod
    def circle_center(p1, p2, p3):
        """
        Calcula el centro (Ux, Uy) de la circunferencia circunscrita:
          d = 2·[ax(by−cy) + bx(cy−ay) + cx(ay−by)]
          Ux = [ (ax²+ay²)(by−cy) + ... ] / d
          Uy = [ (ax²+ay²)(cx−bx) + ... ] / d
        Si d≈0, puntos colineales y no se devuelve centro.
        """
        ax, ay = p1.x(), p1.y()
        bx, by = p2.x(), p2.y()
        cx, cy = p3.x(), p3.y()
        d = 2 * (ax*(by-cy) + bx*(cy-ay) + cx*(ay-by))
        if abs(d) < 1e-9:
            return None
        ux = ((ax*ax+ay*ay)*(by-cy) +
              (bx*bx+by*by)*(cy-ay) +
              (cx*cx+cy*cy)*(ay-by)) / d
        uy = ((ax*ax+ay*ay)*(cx-bx) +
              (bx*bx+by*by)*(ax-cx) +
              (cx*cx+cy*cy)*(bx-ax)) / d
        return QgsPointXY(ux, uy)

    def processAlgorithm(self, parameters, context, feedback):
        # 1. Leer y validar parámetros de entrada
        layer       = self.parameterAsVectorLayer(parameters, self.INPUT_LAYER, context)
        intervalo   = self.parameterAsDouble(parameters, self.INTERVAL, context)
        rmin        = self.parameterAsDouble(parameters, self.MIN_RADIUS, context)
        rmax        = self.parameterAsDouble(parameters, self.MAX_RADIUS, context)
        md          = self.parameterAsDouble(parameters, self.MIN_DIST, context)
        incluir_ctr = self.parameterAsBool(parameters, self.ADD_CENTERS, context)
        dist_agrup  = self.parameterAsDouble(parameters, self.CLUSTER_DISTANCE, context)
        if not layer:
            raise QgsProcessingException('Capa de entrada inválida')

        # 2. Densificar geometrías para tener vértices regulares
        dens = processing.run(
            "native:densifygeometriesgivenaninterval",
            {'INPUT': layer, 'INTERVAL': intervalo, 'OUTPUT': 'memory:dens'},
            context=context, feedback=feedback
        )['OUTPUT']

        # 3. Extraer segmentos de curva válidos
        segmentos = []
        total_f = dens.featureCount()
        for i, feat in enumerate(dens.getFeatures()):
            if feedback.isCanceled():
                break
            # obtener líneas (multi o simple)
            parts = feat.geometry().asMultiPolyline() if feat.geometry().isMultipart() else [feat.geometry().asPolyline()]
            for line in parts:
                # recorrer tripletas consecutivas de puntos
                for j in range(len(line) - 2):
                    p1, p2, p3 = QgsPointXY(line[j]), QgsPointXY(line[j+1]), QgsPointXY(line[j+2])
                    # descartar distancias muy cortas
                    if p1.distance(p2) < md or p2.distance(p3) < md:
                        continue
                    # calcular radio y filtrar por rango
                    r = self.circle_radius(p1, p2, p3)
                    if r and rmin < r < rmax:
                        geom = QgsGeometry.fromPolylineXY([p1, p2, p3])
                        length = geom.length()
                        # calcular centro sólo si se solicitó
                        center = self.circle_center(p1, p2, p3) if incluir_ctr else None
                        segmentos.append({
                            'geom': geom,
                            'radio': r,
                            'long': length,
                            'centro': center
                        })
            feedback.setProgress(int(100 * i / total_f))

        # 4. Agrupar centros de curva cercanos
        mapa_cluster = {}
        clusters = []
        if incluir_ctr:
            for idx, seg in enumerate(segmentos):
                pt = seg['centro']
                if not pt:
                    continue
                asignado = False
                for cid, cl in enumerate(clusters):
                    # si el punto está dentro del radio de agrupación
                    if pt.distance(cl['centroid']) <= dist_agrup:
                        cl['indices'].append(idx)
                        cl['sum_r'] += seg['radio']
                        # recalcular el centroide promedio
                        xs = [segmentos[k]['centro'].x() for k in cl['indices']]
                        ys = [segmentos[k]['centro'].y() for k in cl['indices']]
                        cl['centroid'] = QgsPointXY(sum(xs)/len(xs), sum(ys)/len(ys))
                        mapa_cluster[idx] = cid
                        asignado = True
                        break
                # nuevo clúster si no encaja en ninguno existente
                if not asignado:
                    clusters.append({
                        'centroid': pt,
                        'indices': [idx],
                        'sum_r': seg['radio']
                    })
                    mapa_cluster[idx] = len(clusters) - 1

        # 5. Construir la capa de curvas con solo los campos requeridos
        campos_curvas = QgsFields()
        campos_curvas.append(QgsField('ID_Curva',     QVariant.Int))
        campos_curvas.append(QgsField('ID_Centroide', QVariant.Int))
        campos_curvas.append(QgsField('Radio',        QVariant.Double))
        campos_curvas.append(QgsField('Longitud',     QVariant.Double))
        sink_curvas, id_curvas = self.parameterAsSink(
            parameters, self.OUTPUT_CURVES, context,
            campos_curvas, QgsWkbTypes.LineString, dens.sourceCrs()
        )
        # poblar la capa de curvas
        for idx, seg in enumerate(segmentos):
            f = QgsFeature(campos_curvas)
            f.setGeometry(seg['geom'])
            f.setAttribute('ID_Curva', idx)
            f.setAttribute('ID_Centroide', mapa_cluster.get(idx, -1))
            f.setAttribute('Radio', seg['radio'])
            f.setAttribute('Longitud', seg['long'])
            sink_curvas.addFeature(f, QgsFeatureSink.FastInsert)

        # 6. Construir la capa de centroides (si procede)
        id_centros = None
        if incluir_ctr:
            campos_ctr = QgsFields()
            campos_ctr.append(QgsField('ID_Centroide', QVariant.Int))
            campos_ctr.append(QgsField('Radio_medio',   QVariant.Double))
            campos_ctr.append(QgsField('Conteo',        QVariant.Int))
            sink_ctr, id_centros = self.parameterAsSink(
                parameters, self.OUTPUT_CENTERS, context,
                campos_ctr, QgsWkbTypes.Point, dens.sourceCrs()
            )
            # poblar la capa de centroides
            for cid, cl in enumerate(clusters):
                cnt = len(cl['indices'])
                avg = cl['sum_r'] / cnt if cnt else 0
                f = QgsFeature(campos_ctr)
                f.setGeometry(QgsGeometry.fromPointXY(cl['centroid']))
                f.setAttribute('ID_Centroide', cid)
                f.setAttribute('Radio_medio', avg)
                f.setAttribute('Conteo', cnt)
                sink_ctr.addFeature(f, QgsFeatureSink.FastInsert)

        # 7. Mensaje de resumen en el log
        feedback.pushInfo("=== Estadísticas de curvas ===")
        feedback.pushInfo(f"Total segmentos: {len(segmentos)}")
        if incluir_ctr:
            feedback.pushInfo(f"Total centroides: {len(clusters)}")

        resultado = {self.OUTPUT_CURVES: id_curvas}
        if id_centros is not None:
            resultado[self.OUTPUT_CENTERS] = id_centros
        return resultado

    def shortHelpString(self):
        return """
<b>Descripción</b><br>
Este algoritmo densifica la capa de líneas de entrada, extrae todos los tramos de curva
analizando cada grupo de tres vértices consecutivos y calcula el radio de curvatura.  
Opcionalmente agrupa los centros de esas curvas que estén a menos de cierta distancia
y devuelve dos capas:<br>
• <b>Capa de Curvas</b>: campos  
  – ID_Curva: identificador único de cada segmento.  
  – ID_Centroide: identifica a qué centro pertenece la curva (-1 si no aplica).  
  – Radio: radio de curvatura (m).  
  – Longitud: longitud del segmento (m).<br>
• <b>Capa de Centroides</b> (opcional): campos  
  – ID_Centroide: identificador de cada agrupación de centros.  
  – Radio_medio: promedio de radios de sus curvas (m).  
  – Conteo: número de curvas agrupadas.<br><br>

<b>Parámetros</b><br>
• Capa de líneas de entrada: línea/vectorial.<br>
• Intervalo de densificación (m): distancia fija entre nuevos vértices (por defecto 15).<br>
• Radio mínimo/máximo (m): filtra curvas muy cerradas o muy suaves (por defecto 2–50).<br>
• Distancia mínima entre vértices (m): omite puntos muy cercanos (por defecto 0.5).<br>
• Generar capa de centros de curva: marca si se crea la segunda capa.<br>
• Distancia de agrupación (m): radio para agrupar centros próximos (por defecto 10).<br><br>

<b>Método de cálculo del radio</b><br>
Para tres puntos p1–p2–p3:<br>
1. a = distancia(p1,p2), b = distancia(p2,p3), c = distancia(p3,p1)<br>
2. s = (a + b + c)/2<br>
3. área = √[s(s–a)(s–b)(s–c)] (Herón)<br>
4. radio = (a·b·c)/(4·área)<br>
Si los puntos son casi colineales (área ≈ 0), no se calcula el radio.
"""

__author__ = 'gudmandras'
__date__ = '2025-12-21'
__copyright__ = '(C) 2025 by gudmandras'

__revision__ = '$Format:%H$'

import time, os, datetime, math
from itertools import combinations
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsWkbTypes,
                       QgsPointXY,
                       QgsGeometry,
                       QgsFeature,
                       QgsField,
                       QgsFields,
                       QgsVectorLayer,
                       QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterString,
                       QgsProcessingParameterField,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterFile,
                       QgsProcessingException,
                       QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterFileDestination)

class BreakPointIndexAlgorithm(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('InputLayer', 'Input layer',
                                                            types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterNumber('LowerT', 'Lower tolerance',
                                                       type=QgsProcessingParameterNumber.Integer,
                                                       minValue=0, maxValue=360, defaultValue=20))
        self.addParameter(QgsProcessingParameterNumber('UpperT', 'Upper tolerance',
                                                       type=QgsProcessingParameterNumber.Integer,
                                                       minValue=0, maxValue=360, defaultValue=160))
        self.addParameter(QgsProcessingParameterBoolean('InnerRings', 'Use inner rings for the index calculation',
                                                        defaultValue=True))
        self.addParameter(QgsProcessingParameterString('NSCPField', 'NSCP field name in the result file', defaultValue='nscp_t'))
        self.addParameter(QgsProcessingParameterString('PerimField', 'Perimeter density field name in the result file', defaultValue='dens_perim'))
        self.addParameter(QgsProcessingParameterString('AreaDField', 'Area density field name in the result file', defaultValue='dens_area'))
        self.addParameter(QgsProcessingParameterVectorDestination('OutputLayer', 'Break Point Index point layer',
                                                    type=QgsProcessing.TypeVectorPoint, defaultValue=None))

        id_field = QgsProcessingParameterString('IDField', 'Polygons ID field name in the result file', optional=True)
        id_field.setFlags(id_field.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(id_field)

        cat_field = QgsProcessingParameterField('CatField', 'Extra category field for shared breakpoints between category pairs, edge lenght and density', type=QgsProcessingParameterField.Any, parentLayerParameterName='InputLayer', optional=True)
        cat_field.setFlags(cat_field.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(cat_field)

        text_path = QgsProcessingParameterFileDestination('Outxt', 'Output txt file', 'Text files (*.txt)', optional=True)
        text_path.setFlags(text_path.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(text_path)

    def name(self):
        return 'BreakPointIndex'

    def displayName(self):
        return self.tr(self.name())

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Landscape metrics'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return BreakPointIndexAlgorithm()

    def processAlgorithm(self, parameters, context, model_feedback):
        import ptvsd
        ptvsd.debug_this_thread()
        results = {}
        LowerT = parameters['LowerT']
        UpperT = parameters['UpperT']
        InnerRings = parameters['InnerRings']
        NSCPField = parameters['NSCPField']
        PerimField = parameters['PerimField']
        AreaDField = parameters['AreaDField']
        IDField = parameters['IDField']
        CatField = parameters['CatField']
        Outxt = parameters['Outxt']
        if CatField and Outxt:
            feedback = QgsProcessingMultiStepFeedback(5, model_feedback)
        else:
            feedback = QgsProcessingMultiStepFeedback(4, model_feedback)
        inputLayer = self.parameterAsVectorLayer(parameters, 'InputLayer', context)
        
        startTime = datetime.datetime.now()
        feedback.pushInfo(f"Start Time: {startTime}")
        feedback.pushInfo(f"Using angle thresholds: {LowerT}° to {UpperT}°")

        self.createAttributeFields(inputLayer, [NSCPField, PerimField, AreaDField], feedback)
        if feedback.isCanceled():
            return None
        feedback.pushInfo(f"Fields updated for layer: {inputLayer.name()}")
        feedback.setCurrentStep(1)

        outputLayer, outputLayerPath = self.createOutputPointVector(parameters, inputLayer, IDField, context)
        if feedback.isCanceled():
            return None
        feedback.pushInfo(f"Output point layer created: {outputLayerPath}")
        feedback.setCurrentStep(2)

        data, categoryPoints = self.calculateNSCP(inputLayer, outputLayer, LowerT, UpperT, InnerRings, IDField, CatField, feedback)
        if data is None or feedback.isCanceled():
            return None
        feedback.pushInfo(f"NSCP calculation done!")
        feedback.setCurrentStep(3)

        self.setAttributes(inputLayer, data, [NSCPField, PerimField, AreaDField])
        if feedback.isCanceled():
            return None
        feedback.pushInfo(f"Attributes set for layer: {inputLayer.name()}")
        feedback.setCurrentStep(4)

        if CatField and Outxt:
            self.saveTxt(categoryPoints, Outxt, feedback)
            if feedback.isCanceled():
                return None
            feedback.pushInfo(f"Results saved to txt: {Outxt}")
            results['OutputTxt'] = Outxt
            feedback.setCurrentStep(5)
        endTime = datetime.datetime.now()
        feedback.pushInfo(f"Calculation completed: {endTime} (Duration: {endTime - startTime})")

        del outputLayer
        results['OutputLayer'] = outputLayerPath

        return results

    def createAttributeFields(self, inputLayer, newFields, feedback):
        layerFields = [field.name() for field in inputLayer.fields()]
        for fieldName in newFields:
            if fieldName not in layerFields:
                inputLayer.dataProvider().addAttributes([QgsField(fieldName, QVariant.Double, len=10, prec=5)])
                feedback.pushInfo(f"Added field '{fieldName}' to {inputLayer.name()}")
        inputLayer.updateFields()

    def createOutputPointVector(self, parameters, inputLayer, id_field, context):
        crs = inputLayer.crs()
        fields = QgsFields()
        fields.append(QgsField('angle1', QVariant.Double))
        fields.append(QgsField('angle2', QVariant.Double))
        fields.append(QgsField('angle', QVariant.Double))
        if id_field:
            fields.append(QgsField(id_field, QVariant.String))
        
        sink, dest_id = self.parameterAsSink(
            parameters,
            'OutputLayer',
            context,
            fields,
            QgsWkbTypes.Point,
            crs
        )

        return sink, dest_id


    def angleBetween(self, points):
        a, b, c = points
        ang1 = math.degrees(math.atan2(a.y() - b.y(), a.x() - b.x()))
        ang2 = math.degrees(math.atan2(c.y() - b.y(), c.x() - b.x()))
        ang = abs(abs(ang2 - ang1) - 180)
        return ang, ang1, ang2

    def calculateNSCP(self, inputLayer, outputLayer, LowerT, UpperT, InnerRings, IDField, CatField, feedback):
        import ptvsd
        ptvsd.debug_this_thread()
        data = {}
        categoryCounts = {}
        categoryPoints = {}
        totalFeatures = inputLayer.featureCount()
        processedFeatures = 0

        for feature in inputLayer.getFeatures():
            fid = feature.id()
            geom = feature.geometry()
            poly_id = feature[IDField] if IDField else None
            cat_value = feature[CatField] if CatField else None

            nscp_count = 0
            area = geom.area()
            perimeter = geom.length()

            polygons = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
            if not InnerRings and polygons:
                max_area = 0
                max_index = 0
                for i, part in enumerate(polygons):
                    ring_geom = QgsGeometry.fromPolygonXY(part)
                    ring_area = ring_geom.area()
                    if ring_area > max_area:
                        max_area = ring_area
                        max_index = i
                polygons = [polygons[max_index]]

            for polygon in polygons:
                points = [QgsPointXY(pt) for ring in polygon for pt in ring if pt is not None]
                pointsNumber = len(points)
                if pointsNumber < 3:
                    continue
                if points[0] == points[-1]:
                    points = points[:-1]
                    pointsNumber = len(points)

                for point in range(pointsNumber):
                    pointsForAngle = (points[point - 1], points[point], points[(point + 1) % pointsNumber])
                    if None in pointsForAngle:
                        continue

                    angle, angle1, angle2 = self.angleBetween(pointsForAngle)
                    if LowerT <= angle <= UpperT:
                        nscp_count += 1
                        pt_xy = (round(pointsForAngle[1].x(), 6), round(pointsForAngle[1].y(), 6))

                        if cat_value is not None:
                            categoryPoints.setdefault(cat_value, set()).add(pt_xy)

                        feat = QgsFeature()
                        feat.setGeometry(QgsGeometry.fromPointXY(pointsForAngle[1]))
                        attributes = [angle1, angle2, angle]
                        if IDField:
                            attributes.append(poly_id)
                        feat.setAttributes(attributes) 
                        outputLayer.addFeature(feat)
                    if feedback.isCanceled():
                        return None, None

            data[fid] = {
                'count': nscp_count,
                'area': area,
                'perimeter': perimeter
            }

            #if cat_value is not None:
            #    categoryCounts[cat_value] = categoryCounts.get(cat_value, 0) + nscp_count

            processedFeatures += 1
            processedRatio = int((processedFeatures / totalFeatures) * 100)
            if processedRatio % 10 == 0:
                feedback.pushInfo(f'NSCP calculation {str(processedRatio)} % completed')

        return data, categoryPoints

    def setAttributes(self, inputLayer, data, attributes):
        attributesIndices = [
            inputLayer.fields().indexFromName(attributes[0]),
            inputLayer.fields().indexFromName(attributes[1]),
            inputLayer.fields().indexFromName(attributes[2])
        ]
        attribute_map = {}

        for feature in inputLayer.getFeatures():
            fid = feature.id()
            if fid not in data: 
                continue
            
            count = float(data[fid]['count'])
            dens_perim = float(data[fid]['count'] / data[fid]['perimeter']) if data[fid]['perimeter'] > 0 else None
            dens_area = float(data[fid]['count'] / data[fid]['area']) if data[fid]['area'] > 0 else None

            attribute_map[fid] = {
                attributesIndices[0]: count,
                attributesIndices[1]: dens_perim,
                attributesIndices[2]: dens_area
            }
        inputLayer.dataProvider().changeAttributeValues(attribute_map)

    def saveTxt(self, categoryPoints, Outxt, feedback):
        category_pairs_counts = {}
        category_pairs_lengths = {}
        categories = list(categoryPoints.keys())
        for cat1, cat2 in combinations(categories, 2):
            common_points = categoryPoints[cat1].intersection(categoryPoints[cat2])
            count_common = len(common_points)
            category_pairs_counts[(cat1, cat2)] = count_common

            if count_common >= 2:
                common_list = list(common_points)
                cx = sum(x for x, y in common_list) / len(common_list)
                cy = sum(y for x, y in common_list) / len(common_list)

                sorted_pts = sorted(common_list, key=lambda pt: math.atan2(pt[1] - cy, pt[0] - cx))

                total_len = 0.0
                for i in range(len(sorted_pts) - 1):
                    x1, y1 = sorted_pts[i]
                    x2, y2 = sorted_pts[i + 1]
                    total_len += math.hypot(x2 - x1, y2 - y1)

                category_pairs_lengths[(cat1, cat2)] = total_len
            else:
                category_pairs_lengths[(cat1, cat2)] = 0.0
        with open(Outxt, 'w', encoding='utf-8') as f:
            f.write("Category1\tCategory2\tShared break points\tShared edge lenght (m)\tDensity (point / 100m)\n")
            for (cat1, cat2) in sorted(category_pairs_counts, key=lambda x: -category_pairs_counts[x]):
                cnt = category_pairs_counts[(cat1, cat2)]
                length_m = category_pairs_lengths.get((cat1, cat2), 0.0)
                density = cnt / (length_m / 100) if length_m > 0 else 0.0
                f.write(f"{cat1}\t{cat2}\t{cnt}\t{length_m:.2f}\t{density:.2f}\n")
        
        html_file = os.path.splitext(Outxt)[0] + ".html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write("<html><head><meta charset='utf-8'><title>Category pairs</title>")
            f.write("<style>table {border-collapse: collapse;} td, th {border: 1px solid #ccc; padding: 4px;}</style>")
            f.write("</head><body><h2>Shared category points</h2><table>")
            f.write("<tr><th>Category 1</th><th>Category 2</th><th>Shared brake points</th><th>Shared edge lenght (m)</th><th>Density (pont / 100m)</th></tr>")

            for (cat1, cat2) in sorted(category_pairs_counts, key=lambda x: -category_pairs_counts[x]):
                cnt = category_pairs_counts[(cat1, cat2)]
                length_m = category_pairs_lengths.get((cat1, cat2), 0.0)
                density = cnt / (length_m / 100) if length_m > 0 else 0.0
                f.write(f"<tr><td>{cat1}</td><td>{cat2}</td><td>{cnt}</td><td>{length_m:.2f}</td><td>{density:.2f}</td></tr>")

            f.write("</table></body></html>")
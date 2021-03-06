# -*- coding: utf-8 -*-
"""
dtprolonglinetool
`````````````
"""
"""
Part of DigitizingTools, a QGIS plugin that
subsumes different tools neded during digitizing sessions
some code adopted/adapted from:
 'CadTools Plugin', Copyright (C) Stefan Ziegler

* begin                : 2013-02-25
* copyright          : (C) 2013 by Bernhard Ströbl
* email                : bernhard.stroebl@jena.de

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""
from PyQt4 import QtCore,  QtGui
from qgis.core import *
from qgis.gui import *
import dtutils
from dttools import DtMapTool

class DtProlongLineTool(DtMapTool):
    startedDigitizing = QtCore.pyqtSignal(QgsVectorLayer,  QgsFeature,  QgsPoint,  QgsRubberBand)
    finishedDigitizing = QtCore.pyqtSignal(QgsGeometry)
    stoppedDigitizing = QtCore.pyqtSignal()

    def __init__(self, canvas, iface):
        DtMapTool.__init__(self, canvas, iface)
        self.iface = iface
        self.marker = None
        self.rubberBand = None
        settings = QtCore.QSettings()
        settings.beginGroup("Qgis/digitizing")
        a = settings.value("line_color_alpha",200,type=int)
        b = settings.value("line_color_blue",0,type=int)
        g = settings.value("line_color_green",0,type=int)
        r = settings.value("line_color_red",255,type=int)
        lw = settings.value("line_width",1,type=int)
        settings.endGroup()
        self.rubberBandColor = QtGui.QColor(r, g, b, a)
        self.rubberBandWidth = lw
        self.reset()

    def reset(self,  emitSignal = False):
        self.lineFeature = None

        if self.rubberBand != None:
            self.rubberBand.reset()
            self.canvas.scene().removeItem(self.rubberBand)
            self.rubberBand = None

        if self.marker != None:
            self.canvas.scene().removeItem(self.marker)
            self.marker = None
            # only emit signal if digitizing has already started
            if emitSignal:
                self.stoppedDigitizing.emit()

    def canvasMoveEvent(self, event):
        # move the last point
        if self.rubberBand != None:
            x = event.pos().x()
            y = event.pos().y()
            thisPoint = QtCore.QPoint(x, y)
            # try to snap
            snapper = self.canvas.snappingUtils()
            # snap to any layer within snap tolerance
            snapMatch = snapper.snapToMap(thisPoint)

            if not snapMatch.isValid():
                mapToPixel = self.canvas.getCoordinateTransform()
                self.rubberBand.movePoint(self.rubberBand.numberOfVertices() -1,
                    mapToPixel.toMapCoordinates(thisPoint))
            else:
                self.rubberBand.movePoint(self.rubberBand.numberOfVertices() -1,
                    snapMatch.point())

    def canvasReleaseEvent(self, event):
        layer = self.canvas.currentLayer()

        if layer <> None:
            #Get the click
            x = event.pos().x()
            y = event.pos().y()
            thisPoint = QtCore.QPoint(x, y)
            #QgsMapToPixel instance
            mapToPixel = self.canvas.getCoordinateTransform()

            if event.button() == QtCore.Qt.LeftButton:
                if self.lineFeature == None:
                    # step 1: snap to a start/end point of an existing line
                    #we snap to the current layer (we don't have exclude points and use the tolerances from the qgis properties)
                    snapper = self.canvas.snappingUtils()
                    snapper.setCurrentLayer(layer)

                    # snapType = 0: no snap, 1 = vertex, 2 = segment, 3 = vertex & segment
                    snapType = 1
                    snapMatch = snapper.snapToCurrentLayer(thisPoint, snapType)
                    snappedVertex = snapMatch.point()

                    if not snapMatch.isValid():
                        dtutils.showSnapSettingsWarning(self.iface)
                    else:
                        snappedIdx = snapMatch.vertexIndex()
                        fid = snapMatch.featureId()
                        self.lineFeature = QgsFeature()
                        # get the snapped feature
                        featureFound = layer.getFeatures(
                            QgsFeatureRequest().setFilterFid(fid)).nextFeature(self.lineFeature)

                        if featureFound:
                            #check if this is the start/end vertex of the line
                            if snappedIdx == 0 or \
                                QgsGeometry(self.lineFeature.geometry()).vertexAt(snappedIdx + 1) == QgsPoint(0, 0):

                                #mark the vertex
                                startPoint = QgsPoint()
                                startPoint.setX(snappedVertex.x())
                                startPoint.setY(snappedVertex.y())
                                self.marker = QgsVertexMarker(self.canvas)
                                self.marker.setIconType(1)
                                self.marker.setColor(QtGui.QColor(255,0,0))
                                self.marker.setIconSize(12)
                                self.marker.setPenWidth (3)
                                self.marker.setCenter(startPoint)
                                # step 2: create a QgsRubberBand
                                self.rubberBand = QgsRubberBand(self.canvas)
                                self.rubberBand.setColor(self.rubberBandColor)
                                self.rubberBand.setWidth(self.rubberBandWidth)
                                self.rubberBand.addPoint(startPoint)
                                self.rubberBand.addPoint(startPoint) # second point to be moved
                                self.startedDigitizing.emit(layer, self.lineFeature,  startPoint,  self.rubberBand)
                            else:
                                self.lineFeature = None
                        else:
                            self.lineFeature = None
                else: # step 3: have user digitize line
                    self.rubberBand.addPoint(mapToPixel.toMapCoordinates(thisPoint))
            else: # right click
                if self.lineFeature != None: # step 4: end digitizing merge rubbber band and existing geometry
                    self.rubberBand.removeLastPoint()

                    if self.rubberBand.numberOfVertices() > 1:
                        rbGeom = self.rubberBand.asGeometry()
                        self.finishedDigitizing.emit(rbGeom)
                        self.reset()
                    else:
                        self.reset(True)

                    self.canvas.refresh()

    def keyPressEvent(self,  event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.reset(True )

    def deactivate(self):
        self.reset(True)

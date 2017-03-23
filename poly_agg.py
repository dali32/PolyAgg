# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PolyAggregator
                                 A QGIS plugin
 this plugin aggregates polygons
                              -------------------
        begin                : 2016-03-04
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Mohamed Ali Khechine
        email                : mohamedalikhechine@yahoo.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from osgeo import gdal
import os
from osgeo import ogr,osr
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import concavehull
from qgis.core import QgsMessageLog,QgsField,QgsGeometry
from qgis.core import QgsMapLayerRegistry,QgsVectorLayer,QgsFeature,QgsVectorFileWriter
from qgis.core import QgsMessageLog
import qgis
import os.path
import time
import json
# Initialize Qt resources from file resources.py
import resources
import shapefile
from pyproj import Proj
import pyproj
import shapely.ops as ops
from shapely.geometry.polygon import Polygon
from functools import partial
from pyproj import transform

# Import the code for the dialog
from poly_agg_dialog import PolyAggregatorDialog
import os.path


def addPolygon(simplePolygon, out_lyr):
        featureDefn = out_lyr.GetLayerDefn()
        polygon = ogr.CreateGeometryFromWkb(simplePolygon)
        out_feat = ogr.Feature(featureDefn)
        out_feat.SetGeometry(polygon)
        out_lyr.CreateFeature(out_feat)


def multipoly2poly(in_lyr, out_lyr):
        for in_feat in in_lyr:
            geom = in_feat.GetGeometryRef()
            if geom.GetGeometryName() == 'MULTIPOLYGON':
                for geom_part in geom:
                    addPolygon(geom_part.ExportToWkb(), out_lyr)
            else:
                addPolygon(geom.ExportToWkb(), out_lyr)


class PolyAggregator:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'PolyAggregator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = PolyAggregatorDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&polygon aggregator')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'PolyAggregator')
        self.toolbar.setObjectName(u'PolyAggregator')

        self.dlg.lineEdit.clear()
        self.dlg.pushButton.clicked.connect(self.select_output_file)

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('PolyAggregator', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/PolyAggregator/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'aggregates polygons'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&polygon aggregator'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def select_output_file(self):
        filename = QFileDialog.getSaveFileName(self.dlg, "Select output file ","", '*.shp')
        self.dlg.lineEdit.setText(filename)

    def run(self):
        layer_list = []
        layers = self.iface.legendInterface().layers()
        self.dlg.comboBox.clear()
        for layer in layers:
		        layer_list.append(layer.name())

        self.dlg.comboBox.addItems(layer_list)
        limit = self.dlg.lineEdit_2.text()
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:


            minimumarea  = float(self.dlg.lineEdit_3.text())
            maximumdistance =  float(self.dlg.lineEdit_2.text())


            selectedLayerIndex = self.dlg.comboBox.currentIndex()
            selectedLayer = layers[selectedLayerIndex]
            provider = selectedLayer.dataProvider()
            path = provider.dataSourceUri()
            tmp = path.split("|")
            path_to_shp_data = tmp[0]
            gdal.UseExceptions()
            driver = ogr.GetDriverByName('ESRI Shapefile')
            dataSource = driver.Open(path_to_shp_data,1) #'C:/Program Files/QGIS Lyon/bin/ne_10m_land.shp'
            in_lyr = dataSource.GetLayer()
            outputshp = self.dlg.lineEdit.text()
            #outputshp = os.path.join(os.path.dirname(path),'auxpfile.shp')
            if os.path.exists(outputshp):
                driver.DeleteDataSource(outputshp)
            #out_ds = driver.CreateDataSource(outputshp)
            #out_lyr = out_ds.CreateLayer('poly', geom_type=ogr.wkbPolygon)


            geom=[]
            polys = []
            landtypes = []



            list = []
            for feat in selectedLayer.getFeatures():
                list.append(feat)


            filteredbyarea = []
            for polyatt in list:
                filteredbyarea.append(filterarea(polyatt, minimumarea))


            input = [y for x in filteredbyarea for y in x]


            filterdbydistance  = []
            filterdbydistance.append(filterdistance(input, maximumdistance))

            # QgsMessageLog.logMessage(str(filterdbydistance[0]), "aez")

            srs = qgis.utils.iface.activeLayer().crs().authid()
            #srs = self.iface.mapCanvas().mapRenderer().destinationCrs().authid()
            layer = QgsVectorLayer('Polygon?crs=' + str(srs) + '&field=id:integer&field=count:integer',
                                   'newlayer', 'memory')



            QgsMessageLog.logMessage(str(input), "done")

            #getting the list with biggest length
            # aplatir the list
            hull_list = []
            newList = []
            nl = []
            aux = []
            for lis in filterdbydistance[0]:
                aux = lis[1]
                geom.extend(concavehull.extract_points(lis[0].geometry()))
                for i in aux:
                    geom.extend(concavehull.extract_points(i.geometry()))
                hull_list.append(concave(geom))

            # QgsMessageLog.logMessage(str(hull_list), "done")

            

            # hull_list = []
            # geom = []
            # for polys in filterdbydistance[0]:
            #     geom = []
            #     for feat in polys:
            #         geom.extend(concavehull.extract_points(feat.geometry()))
            #         hull_list.append(concave(geom))



            provider = layer.dataProvider()
            # add hull geometry to data provider
            fid = 0
            for h in hull_list:
                for z in h:
                    feature = QgsFeature()
                    feature.setGeometry(z[0])
                    if layer.fieldNameIndex('id') > -1:
                        feature.setAttributes([fid, z[1]])
                        fid += 1
                    provider.addFeatures([feature])
            for i in input:
                provider.addFeatures([i])
            QgsVectorFileWriter.writeAsVectorFormat(layer, outputshp, str(srs), None, 'ESRI Shapefile')
            base_name = os.path.splitext(os.path.basename(str(outputshp)))[0]
            layer_name = QgsVectorLayer(outputshp, base_name, 'ogr')
            QgsMapLayerRegistry.instance().addMapLayer(layer_name)



            # num_points = len(nex)
            # if (num_points == 0):
            #     srs = qgis.utils.iface.activeLayer().crs().authid()
            #     #srs = self.iface.mapCanvas().mapRenderer().destinationCrs().authid()
            #     layer = QgsVectorLayer('Polygon?crs=' + str(srs) + '&field=id:integer&field=count:integer',
            #                            'newlayer', 'memory')
            #     provider = layer.dataProvider()
            #
            #     # add hull geometry to data provider
            #     fid = 0
            #     for feat in selectedLayer.getFeatures():
            #             provider.addFeatures([feat])
            #     QgsVectorFileWriter.writeAsVectorFormat(layer, outputshp, str(srs), None, 'ESRI Shapefile')
            #     base_name = os.path.splitext(os.path.basename(str(outputshp)))[0]
            #     layer_name = QgsVectorLayer(outputshp, base_name, 'ogr')
            #     QgsMapLayerRegistry.instance().addMapLayer(layer_name)
            #     return None

# QgsMessageLog.logMessage(str(tlist), "aez")


def toarrayofpoints(corners):
            list = []
            for point in corners:
                    list.append((point[0],point[1]))
                    return list


def filterarea(feat, minarea):
    list1 = []
    area = feat.geometry().area() * 10000
    if area >= minarea:
        list1.append(feat)
    return list1


def filterdistance(tlist ,maxdist):
    return head(filterpolsdist(parcour(tlist),maxdist))


def parcour(list):
    polys = []
    test = []
    for pol in list:
        l = []
        dpol = Polygon(concavehull.extract_points(pol.geometry()))
        for pol1 in list:
            dpol1 = Polygon(concavehull.extract_points(pol1.geometry()))
            dist = dpol.distance(dpol1) * 100
            l.append([pol,pol1,dist])
        test.append(l)
    return test


def filterpolsdist(listaoflista, max):
    lista = []
    final = []
    for item in listaoflista:
        lista = []
        for y in item:
            if (y[2] <= max and y[2] != 0.0):
                lista.append([y[0],y[1]])
        final.append(lista)
    return final


def head(filterdlist):
    list = []
    for item in filterdlist:
            if len(item) > 0 :
                list.append([item[0][0],[el[1] for el in item]])
    return list

def concave(poly):
    # generate the hull geometry
    # process points with prior clustering
    hull_list = []
     # process points without clustering
    the_hull = concavehull.concave_hull(poly,3)
    hull_list.append([concavehull.as_polygon(the_hull), len(poly)])
    return hull_list 


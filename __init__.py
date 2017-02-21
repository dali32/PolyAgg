# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PolyAggregator
                                 A QGIS plugin
 this plugin aggregates polygons
                             -------------------
        begin                : 2016-03-04
        copyright            : (C) 2016 by Mohamed Ali Khechine
        email                : mohamedalikhechine@yahoo.fr
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load PolyAggregator class from file PolyAggregator.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .poly_agg import PolyAggregator
    return PolyAggregator(iface)

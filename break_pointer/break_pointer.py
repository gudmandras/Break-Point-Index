__author__ = 'gudmandras'
__date__ = '2025-12-21'
__copyright__ = '(C) 2025 by gudmandras'

import os
import sys
import inspect
import traceback
import processing
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication,  QVariant, QSize
from qgis.core import QgsProcessingAlgorithm, QgsApplication, QgsMessageLog, Qgis
from qgis.utils import iface
from .break_pointer_provider import BreakPointIndexProvider

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

MESSAGE_CATEGORY = 'Messages'

"""
def enable_remote_debugging():
    try:
        import ptvsd
        if ptvsd.is_attached():
            QgsMessageLog.logMessage("Remote Debug for Visual Studio is already active", MESSAGE_CATEGORY, Qgis.Info)
            return
        ptvsd.enable_attach(address=('localhost', 5678))
        QgsMessageLog.logMessage("Attached remote Debug for Visual Studio", MESSAGE_CATEGORY, Qgis.Info)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        format_exception = traceback.format_exception(exc_type, exc_value, exc_traceback)
        QgsMessageLog.logMessage(str(e), MESSAGE_CATEGORY, Qgis.Critical)        
        QgsMessageLog.logMessage(repr(format_exception[0]), MESSAGE_CATEGORY, Qgis.Critical)
        QgsMessageLog.logMessage(repr(format_exception[1]), MESSAGE_CATEGORY, Qgis.Critical)
        QgsMessageLog.logMessage(repr(format_exception[2]), MESSAGE_CATEGORY, Qgis.Critical)
"""

class BreakPointIndexPlugin(object):

    def __init__(self, iface):
        #enable_remote_debugging()
        self.provider = None
        self.iface = iface

        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'vgle_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = BreakPointIndexProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        icon = QIcon()
        icon.addFile(os.path.join(self.plugin_dir, 'icons', 'icon.png'), QSize(16, 16))
        icon.addFile(os.path.join(self.plugin_dir, 'icons', 'icon_big.png'), QSize(24, 24))
        self.action = QAction(icon, 
            u'Break Point Index',
            parent=self.iface.mainWindow())

        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu(u"&Landscape Metrics", self.action)
        self.iface.addToolBarIcon(self.action)

        self.first_start = True

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)
        self.iface.removePluginVectorMenu("&Landscape Metrics", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        if self.first_start == True:
            self.first_start = False
        processing.execAlgorithmDialog("Landscaper:BreakPointIndex")

__author__ = 'gudmandras'
__date__ = '2025-12-21'
__copyright__ = '(C) 2025 by gudmandras'

import os
import sys
import inspect
import traceback
import processing
from qgis.core import QgsProcessingAlgorithm, QgsApplication, QgsMessageLog, Qgis
from .break_pointer_provider import BreakPointIndexProvider

cmd_folder = os.path.split(inspect.getfile(inspect.currentframe()))[0]

if cmd_folder not in sys.path:
    sys.path.insert(0, cmd_folder)

MESSAGE_CATEGORY = 'Messages'

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


class BreakPointIndexPlugin(object):

    def __init__(self):
        enable_remote_debugging()
        self.provider = None

    def initProcessing(self):
        """Init Processing provider for QGIS >= 3.8."""
        self.provider = BreakPointIndexProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

    def unload(self):
        QgsApplication.processingRegistry().removeProvider(self.provider)

    def run():
        if self.first_start == True:
            self.first_start = False
        import ptvsd
        ptvsd.debug_this_thread()
        processing.execAlgorithmDialog("Landscaper:BreakPointIndex")

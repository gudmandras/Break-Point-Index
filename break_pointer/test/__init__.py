# import qgis libs so that ve set the correct sip api version

def classFactory(iface):  # pylint: disable=invalid-name
    """Load vgle class from file vgle.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .break_pointer import break_pointer
    return break_pointer(iface)   # pylint: disable=W0611  # NOQA
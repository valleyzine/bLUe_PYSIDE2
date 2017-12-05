"""
This File is part of bLUe software.

Copyright (C) 2017  Bernard Virot <bernard.virot@libertysurf.fr>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
Lesser General Lesser Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

from PySide2 import QtWidgets, QtCore
from PySide2.QtCore import QSettings, QSize
import sys

from PySide2.QtWidgets import QApplication, QLabel, QMainWindow

import resources_rc   # DO NOT REMOVE !!!!
from graphicsHist import histForm
from layerView import QLayerView
from pyside_dynamicLoader import loadUi


class Form1(QMainWindow):#, Ui_MainWindow): #QtGui.QMainWindow):
    """
    Main window class.
    The layout is loaded from the ui form bLUe.ui.
    """
    def __init__(self, parent=None):
        super(Form1, self).__init__()
        #self.setupUi(self)
        # load UI
        loadUi('bLUe.ui', baseinstance=self, customWidgets= {'QLayerView': QLayerView, 'QLabel': QLabel, 'histForm': histForm})
        #self = QtUiTools.QUiLoader().load("bLUe.ui", self)

        # Status window updating
        self.updateStatus = lambda : 0
        # hooks used for event slots:
        self.onWidgetChange = lambda : 0
        self.onShowContextMenu = lambda : 0
        self.onExecFileOpen = lambda : 0
        self.onUpdateMenuAssignProfile = lambda : 0

        # State recording.
        self.slidersValues = {}
        self.btnValues = {}
        #self._recentFiles = []

        # connections to SLOTS
        #for slider in self.findChildren(QtGui.QSlider):
        for slider in self.findChildren(QtWidgets.QSlider):
            slider.valueChanged.connect(
                            lambda value, slider=slider : self.handleSliderMoved(value, slider)
                            )
            self.slidersValues [str(slider.accessibleName())] = slider.value()

        for button in self.findChildren(QtWidgets.QPushButton) :
            button.pressed.connect(
                            lambda button=button : self.handlePushButtonClicked(button)
                            )
            self.btnValues[str(button.accessibleName())] = button.isChecked()

        for button in self.findChildren(QtWidgets.QToolButton) :
            button.pressed.connect(
                            lambda button=button : self.handleToolButtonClicked(button)
                            )
            self.btnValues[str(button.accessibleName())] = button.isChecked()

        #for widget in self.findChildren(QtWidgets.QLabel):
            #widget.customContextMenuRequested.connect(lambda pos, widget=widget : self.showContextMenu(pos, widget))

    #def showContextMenu(self, pos, widget):
        #self.onShowContextMenu(pos, widget)

    def handlePushButtonClicked(self, button):
        self.onWidgetChange(button)

    def handleToolButtonClicked(self, button):
        """
        button.pressed signal slot
        mutually exclusive selection
        @param button:
        @type button: QButton
        """
        for k in self.btnValues :
            self.btnValues[k] = False
        self.btnValues[str(button.accessibleName())] = True
        self.onWidgetChange(button)

    def handleSliderMoved (self, value, slider) :
        """
        Slider.valueChanged event handler
        @param value:
        @param slider:
        @type slider : QSlider
        """
        self.slidersValues[slider.accessibleName()] = value
        self.onWidgetChange(slider)

    def readSettings(self):
        self.settings = QSettings("bLUe.ini", QSettings.IniFormat)
        self.resize(self.settings.value("mainwindow/size", QSize(250, 200)))

    def writeSettings(self):
        self.settings.sync()
        """
        settings = QSettings("bLUe.ini", QSettings.IniFormat);

        print settings.value('paths/dlgdir', 'novalue').toString()
        return
        settings = QSettings("bLUe.ini", QSettings.IniFormat);

        settings.beginGroup("mainwindow")
        settings.setValue("size", self.size())
        settings.endGroup()

        settings.beginGroup("text")
        settings.setValue("font", 1 )
        settings.setValue("size", 2)
        settings.endGroup()
        """

    def closeEvent(self, event):
        if self.onCloseEvent(event):
            #close
            event.accept()
        else:
            event.ignore()
            return
        """
        quit_msg = "Are you sure you want to exit the program?"
        reply = QMessageBox.question(self, 'Message', quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
            return
        """
        self.writeSettings()
        super(Form1, self).closeEvent(event)

def enumerateMenuActions(menu):
    """
    recursively builds   the list of actions contained in a menu
    and all its submenus.
    @param menu: Qmenu object
    @return: list of actions
    """
    actions = []
    for action in menu.actions():
        #subMenu
        if action.menu():
            actions.extend(enumerateMenuActions(action.menu()))
            action.menu().parent()
        else:
            actions.append(action)
    return actions

########
# QApplication and mainWindow init
# A Python module is a singleton : the initialization code below
# is executed only once, regardless the number of module imports.
#######

#######
# PySide2 : Without the next line, app is unable to load
# imageformat dlls for reading and writing QImage objects.
#######
QtCore.QCoreApplication.addLibraryPath("D:/Python36/Lib/site-packages/PySide2/plugins")
#######
app = QApplication(sys.argv)
window = Form1()



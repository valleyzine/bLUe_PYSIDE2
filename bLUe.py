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


"""
The QtHelp module uses the CLucene indexing library
Copyright (C) 2003-2006 Ben van Klinken and the CLucene Team

Changes are Copyright (C) 2010 Nokia Corporation and/or its subsidiary(-ies).

This library is free software; you can redistribute it and/or modify it under the terms of the GNU Lesser General Public License
as published by the Free Software Foundation; either version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License along with this library; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
"""
import sys
from os import path, walk
from os.path import isfile
from types import MethodType
from grabcut import segmentForm
from PySide.QtCore import Qt, QRect, QEvent, QDir, QUrl
from PySide.QtGui import QPixmap, QColor, QPainter, QApplication, QMenu, QAction, QCursor, QFileDialog, QMessageBox, \
    QMainWindow, QLabel, QDockWidget, QSizePolicy, QKeySequence, QToolTip, QScrollArea, QVBoxLayout, QBrush, QPen, QSplashScreen
from QtGui1 import app, window
import exiftool
from imgconvert import *
from MarkedImg import imImage, metadata

from graphicsRGBLUT import graphicsForm
from graphicsLUT3D import graphicsForm3DLUT
from LUT3D import LUTSIZE, LUT3D, LUT3DIdentity
from colorModels import cmHSP, cmHSB
import icc

from PySide.QtWebKit import QWebView

from colorTemperature import temperatureForm
from time import sleep

from re import search
import weakref

import gc

from graphicsFilter import filterForm
from graphicsHspbLUT import graphicsHspbForm
from graphicsLabLUT import graphicsLabForm


# Global paintEvent painter and background color
qp=QPainter()
defaultBgColor=QColor(191,191,191)

def paintEvent(widg, e) :
    """
    Paint event handler for widgets that display a mImage object.
    The widget must have a valid img attribute of type QImage.
    The handler should override the paintEvent method of widg. This can be done
    by subclassing, or by dynamically assigning paintEvent
    to widg.paintEvent (cf. the function set_event_handler
    below).
    Image layers are painted in stack ascending order,
    each with its own opacity.
    @param widg: widget object with a img attribute
    @param e: paint event
    """
    if not hasattr(widg, 'img'):
        raise ValueError("paintEvent : no image attribute")
    mimg = widg.img
    if mimg is None:
        return
        #raise ValueError("paintEvent : no image set")
    r = mimg.resize_coeff(widg)
    qp.begin(widg)
    # background
    qp.fillRect(QRect(0, 0, widg.width() , widg.height() ), defaultBgColor)
    # draw layers
    for layer in mimg.layersStack :
        if layer.visible:
            qp.setOpacity(layer.opacity)
            qp.setCompositionMode(layer.compositionMode)
            if layer.qPixmap is not None:
                qp.drawPixmap(QRect(mimg.xOffset,mimg.yOffset, mimg.width()*r, mimg.height()*r), # target rect
                           layer.transfer() #layer.qPixmap
                         )
            else:
                qp.drawImage(QRect(mimg.xOffset, mimg.yOffset, mimg.width() * r , mimg.height() * r ), # target rect
                              layer  # layer.qPixmap
                              )
    # draw selection rectangle for active layer only
    qp.setPen(QColor(0, 255, 0))
    if (mimg.getActiveLayer().visible) and (mimg.getActiveLayer().rect is not None ):
        rect = mimg.getActiveLayer().rect
        qp.drawRect(rect.left()*r + mimg.xOffset, rect.top()*r +mimg.yOffset, rect.width()*r, rect.height()*r)
    qp.end()

# mouse event handler for image widgets (dynamically set attribute widget.img, currently label and label_2)

pressed=False
clicked = True
# Mouse coordinates recording
State = {'drag':False, 'drawing':False , 'tool_rect':False, 'rect_over':False, 'ix':0, 'iy':0, 'ix_begin':0, 'iy_begin':0, 'rawMask':None}
CONST_FG_COLOR = QColor(255, 255, 255, 255)
CONST_BG_COLOR = QColor(255, 0, 255, 255)

def mouseEvent(widget, event) :
    """
    Mouse event handler for QLabel object.
    It handles image positionning, zooming, and
    tool actions. It must be called by mousePressed,
    mouseMoved and mouseReleased. This can be done by subclassing
    and overidding, or by dynamically assigning mouseEvent
    to the former three methods (cf. the function set_event_handler
    below)
    @param widget: QLabel object
    @param event: mouse event
    """
    global pressed, clicked
    # get image and active layer
    img= widget.img
    layer = img.getActiveLayer()

    r = img.resize_coeff(widget)
    x, y = event.x(), event.y()
    # read keyboard modifiers
    modifier = QApplication.keyboardModifiers()
    # press event
    if event.type() == QEvent.MouseButtonPress :
        pressed=True
        if event.button() == Qt.LeftButton:
            # no move yet
            clicked=True
        State['ix'], State['iy'] = x, y
        State['ix_begin'], State['iy_begin'] = x, y
        State['x_imagePrecPos'], State['y_imagePrecPos'] = (x - img.xOffset) // r, (y - img.yOffset) // r
    elif event.type() == QEvent.MouseMove :
        clicked=False
        if pressed :
            # button pressed
            if img.isMouseSelectable:
                # marquee tool
                if window.btnValues['rectangle']:
                    # rectangle coordinates are relative to image
                    x_img = (min(State['ix_begin'], x) - img.xOffset) // r
                    y_img = (min(State['iy_begin'], y) - img.yOffset) // r
                    w = abs(State['ix_begin'] - x) // r
                    h = abs(State['iy_begin'] - y) // r
                    layer.rect = QRect(x_img, y_img, w, h)
                elif (window.btnValues['drawFG'] or window.btnValues['drawBG']):
                    if layer.maskIsEnabled:
                        color = QColor(0, 0, 0, 255) if window.btnValues['drawFG'] else QColor(0, 0, 0, 0)
                        tmp = layer.mask
                        qp.begin(tmp)
                        w = window.verticalSlider1.value()
                        qp.setPen(QPen(color, w))
                        # result is source (pen) pixel
                        qp.setCompositionMode(qp.CompositionMode_Source)
                        tmp_x = (x - img.xOffset) // r
                        tmp_y = (y - img.yOffset) // r
                        qp.drawEllipse(tmp_x, tmp_y, w , w)
                        qp.drawLine(State['x_imagePrecPos'], State['y_imagePrecPos'], tmp_x, tmp_y)
                        qp.end()
                        State['x_imagePrecPos'], State['y_imagePrecPos'] = tmp_x, tmp_y
                        i = layer.getStackIndex()
                        for l in img.layersStack[i:] :
                            l.updatePixmap(maskOnly=True)
                        #layer.updatePixmap(maskOnly=True)
                        window.label.repaint()
                else:
                    img.xOffset+=(x-State['ix'])
                    img.yOffset+=(y-State['iy'])
            else:
                img.xOffset+=(x-State['ix'])
                img.yOffset+=(y-State['iy'])
        #update current coordinates
        State['ix'],State['iy']=x,y
    elif event.type() == QEvent.MouseButtonRelease :
        pressed=False
        if event.button() == Qt.LeftButton:
            if img.isMouseSelectable:
                # click event
                if clicked:
                    # Picking color from active layer - for adjustment layers, use full image
                    c = QColor(img.getActivePixel((State['ix']  -  img.xOffset) // r, (State['iy'] - img.yOffset) // r))
                    #cM = QColor(img.getActiveLayer().pixel(State['ix'] // r - img.xOffset // r, State['iy'] // r - img.yOffset // r))
                    red, green, blue = c.red(), c.green(), c.blue()
                    #rM, gM, bM = cM.red(), cM.green(), cM.blue()
                    # select grid node for 3DLUT form
                    if hasattr(layer, "view") and layer.view is not None:
                        if hasattr(layer.view.widget(), 'selectGridNode'):
                            layer.view.widget().selectGridNode(red, green, blue)#, rM, gM, bM)
                    #window.label.repaint()
                if window.btnValues['rectangle']:
                    #layer.rect = QRect(min(State['ix_begin'], x)//r-img.xOffset//r, min(State['iy_begin'], y)//r- img.yOffset//r, abs(State['ix_begin'] - x)//r, abs(State['iy_begin'] - y)//r)
                    layer.rect = QRect((min(State['ix_begin'], x) - img.xOffset) // r,
                                       (min(State['iy_begin'], y) - img.yOffset) // r,
                                       abs(State['ix_begin'] - x) // r, abs(State['iy_begin'] - y) // r)
                elif (window.btnValues['drawFG'] or window.btnValues['drawBG']):
                    if layer.maskIsEnabled:
                        color = QColor(0,0,0,255) if window.btnValues['drawFG'] else QColor(0,0,0,0)
                        # qp.begin(img._layers['drawlayer'])
                        tmp = layer.mask
                        qp.begin(tmp)
                        w = window.verticalSlider1.value()
                        qp.setPen(QPen(color, w))
                        tmp_x = (x - img.xOffset) // r
                        tmp_y = (y - img.yOffset) // r
                        # qp.drawEllipse(tmp_x, tmp_y, 8, 8)
                        # result is source (pen) pixel
                        qp.setCompositionMode(qp.CompositionMode_Source)
                        qp.drawEllipse(tmp_x, tmp_y, w, w)
                        qp.drawLine(State['x_imagePrecPos'], State['y_imagePrecPos'], tmp_x, tmp_y)
                        qp.end()
                        #layer.updatePixmap(maskOnly=True)
                        i = layer.getStackIndex()
                        for l in img.layersStack[i:] :
                            l.updatePixmap(maskOnly=True)
                        window.label.repaint()
                        #tmp.isModified = True
                else:
                    img.xOffset += (x - State['ix'])
                    img.yOffset += (y - State['iy'])
    widget.repaint()

def wheelEvent(widget,img, event):
    """
    Mouse wheel event handler for zooming
    imImage objects.
    @param widget: widget displaying image
    @param img: imImage object to display
    @param event: mouse wheel event (type QWheelEvent)
    """
    pos = event.pos()
    # delta unit is 1/8 of degree
    # Most mice have a resolution of 15 degrees
    numDegrees = event.delta() / 8
    numSteps = numDegrees / 150.0
    r=img.Zoom_coeff
    img.Zoom_coeff *= (1.0 + numSteps)
    # correct image offset to keep unchanged the image point
    # under the cursor : (pos - offset) / resize_coeff should be invariant
    img.xOffset = -pos.x() * numSteps + (1.0+numSteps)*img.xOffset
    img.yOffset = -pos.y() * numSteps + (1.0+numSteps)*img.yOffset
    widget.repaint()

def enterEvent(widget,img, event):
    if not window.btnValues['colorPicker']:
        return
    layer = window.label.img.getActiveLayer()
    if layer.isAdjustLayer():
        if layer.view.isVisible():
            if not QApplication.overrideCursor():
                QApplication.setOverrideCursor(window.cursor_EyeDropper)

def leaveEvent(widget,img, event):
    QApplication.restoreOverrideCursor()

def set_event_handler(widg):
    """
    Pythonic way for redefining event handlers, without
    subclassing or overridding. However, the PySide dynamic
    ui loader needs that we set the corresponding classes as customWidget
    (cf. file pyside_dynamicLoader.py).
    @param widg:
    """
    widg.paintEvent = MethodType(lambda instance, e, wdg=widg: paintEvent(wdg, e), widg.__class__)
    widg.mousePressEvent = MethodType(lambda instance, e, wdg=widg : mouseEvent(wdg, e), widg.__class__)
    widg.mouseMoveEvent = MethodType(lambda instance, e, wdg=widg : mouseEvent(wdg, e), widg.__class__)
    widg.mouseReleaseEvent = MethodType(lambda instance, e, wdg=widg : mouseEvent(wdg, e), widg.__class__)
    widg.wheelEvent = MethodType(lambda instance, e, wdg=widg : wheelEvent(wdg, wdg.img, e), widg.__class__)
    widg.enterEvent = MethodType(lambda instance, e, wdg=widg : enterEvent(wdg, wdg.img, e), widg.__class__)
    widg.leaveEvent = MethodType(lambda instance, e, wdg=widg : leaveEvent(wdg, wdg.img, e), widg.__class__)

# button change event handler
def widgetChange(widget):
    """
    
    @param widget:
    @type widget: QWidget
    """
    wdgName = widget.accessibleName()
    if wdgName == "Fit_Screen" :
        window.label.img.fit_window(window.label)
        window.label.repaint()
    elif wdgName == "verticalSlider1":
        pass

"""
def contextMenu(widget):
    qmenu = QMenu("Context menu")
    for k in widget.img.layers.keys():
        action1 = QAction(k, qmenu, checkable=True)
        qmenu.addAction(action1)
        action1.triggered[bool].connect(lambda b, widget=widget, layer=widget.img.layers[k]: toggleLayer(widget, layer,b))
        action1.setChecked(widget.img.layers[k].visible)
    qmenu.exec_(QCursor.pos())

def toggleLayer(widget, layer, b):
    layer.visible = b
    widget.repaint()
"""
def loadImageFromFile(f):
    """
    loads metadata and image from file.
    @param f: path to file
    @type f: str
    @return: image
    @rtype: imImage
    """
    # metadata
    try:
        with exiftool.ExifTool() as e:
            profile, metadata = e.get_metadata(f)
    except ValueError as er:
        # Default metadata and profile
        metadata = [{'SourceFile': f}]
        profile = ''
    # trying to get color space info : 1 = sRGB
    colorSpace = metadata[0].get("EXIF:ColorSpace", -1)
    if colorSpace < 0:
        desc_colorSpace = metadata[0].get("ICC_Profile:ProfileDescription", '')
        if isinstance(desc_colorSpace, unicode) or isinstance(desc_colorSpace, str):
            if 'sRGB' in desc_colorSpace:
                # sRGBIEC61966-2.1
                colorSpace = 1
    # orientation
    orientation = metadata[0].get("EXIF:Orientation", 0)
    transformation = exiftool.decodeExifOrientation(orientation)
    # rating
    rating = metadata[0].get("XMP:Rating", 5)
    # load image file
    name = path.basename(f)
    img = imImage(filename=f, colorSpace=colorSpace, orientation=transformation, rawMetadata=metadata, profile=profile, name=name, rating=rating)
    img.initThumb()
    if img.format() < 4:
        msg = QMessageBox()
        msg.setText("Cannot edit indexed formats\nConvert image to a non indexed mode first")
        msg.exec_()
        return None
    if colorSpace < 0:
        print 'colorspace', colorSpace
        msg = QMessageBox()
        msg.setText("Color profile missing\nAssigning sRGB profile")
        msg.exec_()
        img.meta.colorSpace = 1
        img.updatePixmap()
    return img

def openFile(f):
    """
    @param f: file name (type str)
    """
    # extract embedded profile and metadata, if any.
    # metadata is a list of dicts with len(metadata) >=1.
    # metadata[0] contains at least 'SourceFile' : path.
    # profile is a string containing the profile binary data.
    # Currently, we do not use these data : standard profiles
    # are loaded from disk, non standard profiles are ignored.
    try :
        img = loadImageFromFile(f)
    except ValueError as e:
        msg = QMessageBox()
        msg.setWindowTitle('Warning')
        msg.setIcon(QMessageBox.Warning)
        msg.setText(str(e))
        msg.exec_()
        return
    setDocumentImage(img)

def setDocumentImage(img):
    """
    display img
    @param img: image
    @type img: imImage
    @return: 
    """
    window.label.img =  img
    window.label.img.onModify = lambda : updateEnabledActions()
    window.label.img.onImageChanged = window.label.repaint
    #window.label_2.img = imImage(QImg=img.copy(), meta=img.meta)
    window.label_2.img = imImage(QImg=img, meta=img.meta)
    # no mouse drawing or painting
    window.label_2.img.isMouseSelectable = False
    # init layer view
    window.tableView.setLayers(window.label.img)
    window.label.repaint()
    window.label_2.repaint()
    # used by graphicsForm3DLUT.onReset
    window.label.img.window = window.label
    window.label_2.img.window = window.label_2
    updateStatus()

def updateMenuOpenRecent():
    window.menuOpen_recent.clear()
    for f in window._recentFiles :
        window.menuOpen_recent.addAction(f, lambda x=f: window.execFileOpen(x))

def updateEnabledActions():
    window.actionSave.setEnabled(window.label.img.isModified)
    window.actionSave_Hald_Cube.setEnabled(window.label.img.isHald)

def menuFile(x, name):
    """
    Exec File Menu
    @param x: dummy
    @param name: action name
    @type name: str
    """
    def openDlg():
        if window.label.img.isModified:
            ret = savingDialog(window.label.img)
            if ret == QMessageBox.Yes:
                save(window.label.img)
            elif ret == QMessageBox.Cancel:
                return
        lastDir = window.settings.value('paths/dlgdir', '.')
        dlg = QFileDialog(window, "select", lastDir)
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            newDir = dlg.directory().absolutePath()
            window.settings.setValue('paths/dlgdir', newDir)
            # update list of recent files
            filter(lambda a: a != filenames[0], window._recentFiles)
            window._recentFiles.append(filenames[0])
            if len(window._recentFiles) > 10:
                window._recentFiles.pop(0)
            window.settings.setValue('paths/recent', window._recentFiles)
            # update menu and actions
            updateMenuOpenRecent()
            return filenames[0]
        else:
            return None
    window._recentFiles = window.settings.value('paths/recent', [])
    # update menu and actions
    updateMenuOpenRecent()
    if name in ['actionOpen', 'actionHald_from_file'] :
        # open dialog
        filename = openDlg()
        if filename is not None:
            openFile(filename)
    # save dialog
    elif name == 'actionSave':
        save(window.label.img)
    # closing dialog : close opened document
    elif name == 'actionClose':
        if window.label.img.isModified:
            ret = savingDialog(window.label.img)
            if ret == QMessageBox.Yes:
                save(window.label.img)
            elif ret == QMessageBox.Cancel:
                return
        #r = weakref.ref(window.label.img)
        #print 'ref', r()
        window.label.img = defaultImImage
        window.label_2.img = defaultImImage
        window.tableView.clear() #setLayers(window.label.img)
        # free (almost) all memory used by images
        gc.collect()
        #print 'ref', r()
        window.label.repaint()
        window.label_2.repaint()
    elif name == 'actionHald_identity':
        img = QImage(LUTSIZE, LUTSIZE**2, QImage.Format_ARGB32)
        buf = QImageBuffer(img)
        buf[:,:,:3] = LUT3DIdentity.getHaldImage(LUTSIZE, LUTSIZE**2)
        img1 = imImage(QImg=img)
        img1.initThumb()
        setDocumentImage(img1)
        img1.isHald = True
    elif name == 'actionSave_Hald_Cube':
        # apply stack
        doc = window.label.img
        if not doc.isHald:
            return
        doc.layersStack[0].applyToStack()
        window.label.repaint()
        # get resulting image
        img = doc.mergeVisibleLayers()
        # convert image to LUT3D object
        LUT = LUT3D.HaldImage2LUT3D(img, size=33)
        # open file and save
        lastDir = window.settings.value('paths/dlgdir', '.')
        dlg = QFileDialog(window, "select", lastDir)
        dlg.setNameFilter('*.cube')
        dlg.setDefaultSuffix('cube')
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            newDir = dlg.directory().absolutePath()
            window.settings.setValue('paths/dlgdir', newDir)
            LUT.writeToTextFile(filenames[0])
        """
        img = doc.mergeVisibleLayers()
        # convert image to LUT3D object
        LUT = LUT3D.HaldImage2LUT3D(img, size=33)
        LUT.writeToTextFile('toto')
        """
    updateEnabledActions()
    updateStatus()

isSuspended= False
def playDiaporama(diaporamaGenerator, parent=None):
    """
    Plays diaporama
    @param diaporamaGenerator: generator of file names
    @type  diaporamaList: list of str
    @param parent: 
    @return: 
    """
    newwindow = QMainWindow(parent)
    newwindow.setAttribute(Qt.WA_DeleteOnClose)
    newwindow.setContextMenuPolicy(Qt.CustomContextMenu)
    newwindow.setWindowTitle(parent.tr('Slide show'))
    global isSuspended
    isSuspended = False
    # Pause shortcut
    actionEsc = QAction('Pause', None)
    actionEsc.setShortcut(QKeySequence(Qt.Key_Escape))
    newwindow.addAction(actionEsc)
    # context menu event handler
    def h(action):
        global isSuspended
        if action.text() == 'Pause':
            isSuspended = True
        elif action.text() == 'Resume':
            newwindow.close()
            isSuspended = False
            playDiaporama(diaporamaGenerator, parent=window)
        elif action.text() in ['0', '1','2','3','4','5']:
            with exiftool.ExifTool() as e:
                e.writeXMPTag(name, 'XMP:rating', int(action.text()))
    actionEsc.triggered.connect(lambda name=actionEsc: h(name))
    # context menu
    def contextMenu(position):
        menu = QMenu()
        action1 = QAction('Pause', None)
        action1.setEnabled(not isSuspended)
        action3 = QAction('Resume', None)
        action3.setEnabled(isSuspended)
        for action in [action1, action3]:
            menu.addAction(action)
            action.triggered.connect(lambda name=action : h(name))
        subMenuRating = menu.addMenu('Rating')
        for i in range(6):
            action = QAction(str(i), None)
            subMenuRating.addAction(action)
            action.triggered.connect(lambda name=action : h(name))
        menu.exec_(position)

    newwindow.customContextMenuRequested.connect(contextMenu)

    label = QLabel()
    label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    label.img = None
    newwindow.setCentralWidget(label)
    newwindow.showMaximized()
    set_event_handler(label)
    while True:
        if isSuspended:
            newwindow.setWindowTitle(newwindow.windowTitle() + ' Paused')
            break
        try:
            # test if window was closed :
            # close = hide();delete_later()
            if not newwindow.isVisible():
                break
            name = diaporamaGenerator.next()
            try:
                with exiftool.ExifTool() as e:
                    rating = e.readXMPTag(name, 'XMP:rating')
                    r = search("\d", rating)
                    if r:
                        rating = int(r.group(0))
            except ValueError as er:
                # No metadata found
                rating = 5
            if rating < 2:
                app.processEvents()
                print 'skip'
                continue
            imImg= loadImageFromFile(name)
            if label.img is not None:
                imImg.Zoom_coeff = label.img.Zoom_coeff
            coeff = imImg.resize_coeff(label)
            imImg.yOffset -= (imImg.height()*coeff - label.height()) / 2.0
            imImg.xOffset -= (imImg.width()*coeff - label.width()) / 2.0
            app.processEvents()
            if isSuspended:
                newwindow.setWindowTitle(newwindow.windowTitle() + ' Paused')
                break
            newwindow.setWindowTitle(parent.tr('Slide show') + ' ' + name + ' ' + ' '.join(['*']*imImg.meta.rating))
            label.img = imImg
            label.repaint()
            app.processEvents()
            gc.collect()
            sleep(2)
            app.processEvents()
        except StopIteration:
            newwindow.close()
            window.diaporamaGenerator = None
            break
        except ValueError as ev:
            continue
        except RuntimeError as er:
            #newwindow.close()
            window.diaporamaGenerator = None
            break
        except:
            print "Unexpected error:", sys.exc_info()[0]
            #newwindow.close()
            window.diaporamaGenerator = None
            raise
        app.processEvents()

def menuWindow(x, name):
    """

    @param x: dummy
    @param name: action name
    """
    if name == 'actionShow_hide_left_window' :
        pass
    elif name == 'actionShow_hide_right_window_3' :
        if window.label_2.isHidden() :
            window.label_2.show()
        else:
            window.label_2.hide()
    elif name == 'actionDiaporama':
        if hasattr(window, 'diaporamaGenerator'):
            if window.diaporamaGenerator is not None:
                reply = QMessageBox()
                reply.setWindowTitle('Question')
                reply.setIcon(QMessageBox.Information)
                reply.setText("A diaporama was suspended. Resume ?")
                reply.setStandardButtons(QMessageBox.No | QMessageBox.Yes)
                reply.setDefaultButton(QMessageBox.Yes)
                ret = reply.exec_()
                if ret == QMessageBox.No:
                    window.diaporamaGenerator = None
        else:
            window.diaporamaGenerator = None
        if window.diaporamaGenerator is None:
            lastDir = window.settings.value('paths/dlgdir', '.')
            dlg = QFileDialog(window, "select", lastDir)
            dlg.setNameFilters( ['Image Files (*.jpg *.png)'])
            dlg.setFileMode(QFileDialog.Directory)
            diaporamaList = []
            if dlg.exec_():
                #filenames = dlg.selectedFiles()
                newDir = dlg.directory().absolutePath()
                window.settings.setValue('paths/dlgdir', newDir)
                for dirpath, dirnames, filenames in walk(newDir):
                    for filename in [f for f in filenames if (f.endswith(".jpg") or f.endswith(".png"))]:
                        diaporamaList.append(path.join(dirpath, filename))
            def f():
                for filename in diaporamaList:
                    yield filename
            window.diaporamaGenerator = f()
        playDiaporama(window.diaporamaGenerator, parent=window)

def menuImage(x, name) :
    """

    @param x: dummy
    @param name: action name
    """
    img = window.label.img
    # display image info
    if name == 'actionImage_info' :
        # Format
        s = "Format : %s\n(cf. QImage formats in the doc for more info)" % QImageFormats.get(img.format(), 'unknown')
        # dimensions
        s = s + "\n\ndim : %d x %d" % (img.width(), img.height())
        # working profile
        if img.colorTransformation is not None:
            workingProfileInfo = img.colorTransformation.fromProfile.info
        else:
            workingProfileInfo = 'None'
        s = s + "\n\nWorking Profile : %s" % workingProfileInfo
        # embedded profile
        if len(img.meta.profile) > 0:
            s = s +"\n\nEmbedded profile found, length %d" % len(img.meta.profile)
        s = s + "\nRating %s" % ''.join(['*']*img.meta.rating)
        # raw meta data
        l = img.meta.rawMetadata
        s = s + "\n\nMETADATA :\n"
        for d in l:
            s = s + '\n'.join('%s : %s' % (k,v) for k, v in d.iteritems())
        w, label = handleTextWindow(parent=window, title='Image info')
        label.setWordWrap(True)
        label.setText(s)
    elif name == 'actionColor_manage':
        icc.COLOR_MANAGE = window.actionColor_manage.isChecked()
        img.updatePixmap()
        window.label_2.img.updatePixmap()
    elif name == 'actionWorking_profile':
        w, label = handleTextWindow(parent=window, title='profile info')
        s = 'Working profile\n' + icc.workingProfile.info
        s = s + '-------------\n' + 'Monitor profile\n'+ icc.monitorProfile.info
        s = s + '\nNote : The working profile is the color profile currently associated\n with the opened image.'
        s = s + '\nThe monitor profile is associated with your monitor'
        s = s + '\nBoth profles are used in conjunction to display exact colors'
        s = s + '\n\nIf the monitor profile listed above is not the right profile\nfor your monitor, check the system settings for color management'
        label.setText(s)
    # snapshot
    elif name == 'actionSnap':
        snap = img.snapshot()
        # keep zoom and offset
        snap.setView(*window.label_2.img.view())
        window.label_2.img = snap
        window.label_2.repaint()
    elif name in ['action0', 'action1', 'action2', 'action3', 'action4', 'action5']:
        img.meta.rating = int(name[-1:])
        updateStatus()
        with exiftool.ExifTool() as e:
            e.writeXMPTag(img.meta.filename, 'XMP:rating', img.meta.rating)

def menuLayer(x, name):
    """

    @param x: dummy
    @param name: action name
    @type name: str
    """
    # curves
    axeSize = 200
    if name in ['actionBrightness_Contrast', 'actionCurves_HSpB', 'actionCurves_Lab']:
        if name == 'actionBrightness_Contrast':
            layerName = 'Curves R, G, B'
        elif name == 'actionCurves_HSpB':
            layerName = 'Curves H, S, pB'
        elif name == 'actionCurves_Lab':
            layerName = 'Curves L, a, b'
        # add new layer on top of active layer
        l = window.label.img.addAdjustmentLayer(name=layerName)
        if name == 'actionBrightness_Contrast':
            grWindow=graphicsForm.getNewWindow(axeSize=axeSize, targetImage=window.label.img, layer=l, parent=window, mainForm=window)
        elif name == 'actionCurves_HSpB':
            grWindow = graphicsHspbForm.getNewWindow(axeSize=axeSize, targetImage=window.label.img, layer=l, parent=window, mainForm=window)
        elif name == 'actionCurves_Lab':
            grWindow = graphicsLabForm.getNewWindow(axeSize=axeSize, targetImage=window.label.img, layer=l, parent=window, mainForm=window)
        # redimensionable window
        grWindow.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # Curve change event handler
        # Apply current LUT and repaint window
        def f():
            l.execute()
            #l.applyToStack()
            #l.applyLUT(grWindow.graphicsScene.cubicItem.getStackedLUTXY())
            window.label.repaint()
        # wrapper for the right apply method
        if name == 'actionBrightness_Contrast':
            l.execute = lambda : l.apply1DLUT(grWindow.graphicsScene.cubicItem.getStackedLUTXY())
        elif name == 'actionCurves_HSpB':
            l.execute = lambda: l.applyHSPB1DLUT(grWindow.graphicsScene.cubicItem.getStackedLUTXY())
        elif name == 'actionCurves_Lab':
            l.execute = lambda: l.applyLab1DLUT(grWindow.graphicsScene.cubicItem.getStackedLUTXY())
        grWindow.graphicsScene.onUpdateLUT = f
    # 3D LUT
    elif name in ['action3D_LUT', 'action3D_LUT_HSB']:
        # color model
        ccm = cmHSP if name == 'action3D_LUT' else cmHSB
        layerName = '3D LUT HSpB' if name == 'action3D_LUT' else '3D LUT HSB'
        # add new layer on top of active layer
        l = window.label.img.addAdjustmentLayer(name=layerName)
        #window.tableView.setLayers(window.label.img)
        grWindow = graphicsForm3DLUT.getNewWindow(ccm, size=800, targetImage=window.label.img, LUTSize=LUTSIZE, layer=l, parent=window, mainForm=window)
        # LUT change event handler
        def g(options={}):
            """
            Apply current 3D LUT and repaint window
            @param options: dictionary of options
            """
            #l.options = options
            l.applyToStack()
            #l.apply3DLUT(grWindow.graphicsScene.LUT3D, options=options)
            window.label.repaint()
        grWindow.graphicsScene.onUpdateLUT = g
        # wrapper for the right apply method
        #l.execute = lambda : l.apply3DLUT(grWindow.graphicsScene.LUT3DArray, options=l.options)
        l.execute = lambda: l.apply3DLUT(grWindow.graphicsScene.LUT3DArray, options=grWindow.graphicsScene.options)
        #window.tableView.setLayers(window.label.img)
    # segmentation grabcut
    elif name == 'actionNew_segmentation_layer':
        lname = 'Segmentation'
        l = window.label.img.addSegmentationLayer(name=lname)
        #window.tableView.setLayers(window.label.img)
        # link to grabcut form
        grWindow = segmentForm.getNewWindow(targetImage=window.label.img, layer=l, mainForm=window)
        #window.tableView.update()
        # TODO continue
    # Temperature
    elif name == 'actionColor_Temperature':
        lname = 'Color Temperature'
        l = window.label.img.addAdjustmentLayer(name=lname)
        grWindow = temperatureForm.getNewWindow(size=axeSize, targetImage=window.label.img, layer=l, parent=window, mainForm=window)
        # temperature change event handler
        def h(temperature):
            l.temperature = temperature
            l.applyToStack()
            window.label.repaint()
        grWindow.onUpdateTemperature = h
        # wrapper for the right apply method
        l.execute = lambda: l.applyTemperature(l.temperature, grWindow.options)
        # l.execute = lambda: l.applyLab1DLUT(grWindow.graphicsScene.cubicItem.getStackedLUTXY())
    elif name == 'actionFilter':
        lname = 'Filter'
        l = window.label.img.addAdjustmentLayer(name=lname)
        grWindow = filterForm.getNewWindow(axeSize=axeSize, targetImage=window.label.img, layer=l, parent=window, mainForm=window)
        # temperature change event handler
        def h(category, radius, amount):
            l.kernelCategory = category
            l.radius = radius
            l.amount = amount
            l.applyToStack()
            window.label.repaint()
        grWindow.onUpdateFilter = h
        # wrapper for the right apply method
        l.execute = lambda: l.applyFilter2D()
        # l.execute = lambda: l.applyLab1DLUT(grWindow.graphicsScene.cubicItem.getStackedLUTXY())
    elif name == 'actionSave_Layer_Stack':
        lastDir = window.settings.value('paths/dlgdir', '.')
        dlg = QFileDialog(window, "select", lastDir)
        dlg.setNameFilter('*.sba')
        dlg.setDefaultSuffix('sba')
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            newDir = dlg.directory().absolutePath()
            window.settings.setValue('paths/dlgdir', newDir)
            window.label.img.saveStackToFile(filenames[0])
            return
    elif name == 'actionLoad_Layer_Stack':
        lastDir = window.settings.value('paths/dlgdir', '.')
        dlg = QFileDialog(window, "select", lastDir)
        dlg.setNameFilter('*.sba')
        dlg.setDefaultSuffix('sba')
        if dlg.exec_():
            filenames = dlg.selectedFiles()
            newDir = dlg.directory().absolutePath()
            window.settings.setValue('paths/dlgdir', newDir)
            script, qf, dataStream = window.label.img.loadStackFromFile(filenames[0])
            script = '\n'.join(script)
            # secure env for exec
            safe_list = ['menuLayer', 'window']
            safe_dict = dict([(k, globals().get(k, None)) for k in safe_list])
            exec script in safe_dict, locals() #globals(), locals()
            qf.close()
            return
    # adjustment layer from .cube file
    elif name == 'actionLoad_3D_LUT' :
        lastDir = window.settings.value('paths/dlgdir', '.')
        dlg = QFileDialog(window, "select", lastDir)
        dlg.setNameFilter('*.cube')
        dlg.setDefaultSuffix('cube')
        if dlg.exec_():
            newDir = dlg.directory().absolutePath()
            window.settings.setValue('paths/dlgdir', newDir)
            filenames = dlg.selectedFiles()
            name = filenames[0]
            """
            if name[-4:] == '.png':
                LUT3DArray = LUT3D.readFromHaldFile(name)
            else :
            """
            try:
                LUT3DArray, size = LUT3D.readFromTextFile(name)
            except (ValueError, IOError) as e:
                reply = QMessageBox()
                reply.setText('Unable to load 3D LUT')
                reply.setInformativeText(str(e))
                reply.setStandardButtons(QMessageBox.Ok)
                ret = reply.exec_()
                return
            lname = path.basename(name)
            l = window.label.img.addAdjustmentLayer(name=lname)
            l.execute = lambda: l.apply3DLUT(LUT3DArray, {'use selection': False})
            window.tableView.setLayers(window.label.img)
            l.applyToStack()
            #l.apply3DLUT(LUT3DArray, {'use selection':False})
        return
    elif name == 'actionSave_Layer_Stack_as_LUT_Cube':
        doc = window.label.img
        buf = LUT3DIdentity.getHaldImage(doc.width(), doc.height())
        try:
            layer = doc.addLayer(None, name='Hald', index=1)
            #layer = doc.layersStack[0]
            docBuf = QImageBuffer(layer)
            docBuf[:, :, :3] = buf
            layer.applyToStack()
            window.label.repaint()
            img = doc.mergeVisibleLayers()
            # convert image to LUT3D object
            LUT = LUT3D.HaldImage2LUT3D(img, size=33)
            # open file and save
            lastDir = window.settings.value('paths/dlgdir', '.')
            dlg = QFileDialog(window, "select", lastDir)
            dlg.setNameFilter('*.cube')
            dlg.setDefaultSuffix('cube')
            if dlg.exec_():
                newDir = dlg.directory().absolutePath()
                window.settings.setValue('paths/dlgdir', newDir)
                filenames = dlg.selectedFiles()
                newDir = dlg.directory().absolutePath()
                window.settings.setValue('paths/dlgdir', newDir)
                LUT.writeToTextFile(filenames[0])
            return
        finally:
            # restore doc
            doc.removeLayer(1)
            doc.layersStack[0].applyToStack()
    else:
        return
    # record action name for scripting
    l.actionName = name
    # dock widget
    dock = QDockWidget(window)
    dock.setWidget(grWindow)
    dock.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint)  # | Qt.WindowStaysOnTopHint)
    dock.setWindowTitle(grWindow.windowTitle())
    dock.move(900, 40)
    # set modal : docked windows
    # are not modal, so docking
    # must be disabled
    #dock.setAllowedAreas(Qt.NoDockWidgetArea)
    #dock.setWindowModality(Qt.ApplicationModal)
    l.view = dock
    # update layer stack view
    window.tableView.setLayers(window.label.img)

def menuHelp(x, name):
    """
    Init help browser
    A single instance is created.
    Unused parameters are for the sake of symmetry
    with other menu function calls.
    @param x:
    @param name:
    """
    if name == "actionBlue_Help":
        global helpWindow
        link = "Help.html"
        if helpWindow is None:
            helpWindow = QWebView()
            helpWindow.load(QUrl(link))
        helpWindow.show()
    elif name == "actionAbout_bLUe":
        w, label = handleTextWindow(parent=window, title='About bLUe')
        label.setStyleSheet("background-image: url(logo.png); color: white;")
        label.setAlignment(Qt.AlignCenter)
        label.setText("Version 1.0")
        w.show()

def handleNewWindow(imImg=None, parent=None, title='New window', show_maximized=False, event_handler=True, scroll=False):
    """
    Show a floating window containing a QLabel object. It can be used
    to display text or iamge. If the parameter event_handler is True (default)
    the QLabel object redefines its handlers for paint and mouse events to display
    the image imImg
    @param imImg: Image to display
    @type imImg: imImage
    @param parent:
    @param title:
    @param show_maximized:
    @param event_handler:
    @type event_handler: boolean
    @return: new window, label
    @rtype: QMainWindow, QLabel
    """
    newwindow = QMainWindow(parent)
    newwindow.setAttribute(Qt.WA_DeleteOnClose)
    newwindow.setWindowTitle(parent.tr(title))
    label = QLabel()
    if scroll:
        scarea = QScrollArea(parent=newwindow)
        scarea.setWidget(label)
        newwindow.setCentralWidget(scarea)
        scarea.setWidgetResizable(True)
    else:
        newwindow.setCentralWidget(label)
    # The attribute img is used by event handlers
    label.img = imImg
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
    if event_handler:
        set_event_handler(label)
    if show_maximized:
        newwindow.showMaximized()
    else:
        newwindow.show()
    return newwindow, label

def handleTextWindow(parent=None, title=''):
    """
    Display a floating modal text window
    @param parent:
    @param title:
    @return (new window, label)
    @rtype: QMainWindow, QLabel
    """
    w, label = handleNewWindow(parent=parent, title=title, event_handler=False, scroll = True)

    w.setFixedSize(500,500)
    label.setAlignment(Qt.AlignTop)
    w.hide()
    w.setWindowModality(Qt.WindowModal)
    w.show()
    return w, label

def initMenuAssignProfile():
    window.menuAssign_profile.clear()
    for f in PROFILES_LIST:
        window.menuAssign_profile.addAction(f[0]+" "+f[1], lambda x=f : window.execAssignProfile(x))

def savingDialog(img):
    reply = QMessageBox()
    reply.setText("%s has been modified" % img.meta.name if len(img.meta.name) > 0 else 'unnamed image')
    reply.setInformativeText("Save your changes ?")
    reply.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
    reply.setDefaultButton(QMessageBox.Save)
    ret = reply.exec_()
    return ret

def save(img):
    lastDir = window.settings.value('paths/dlgdir', QDir.currentPath())
    dlg = QFileDialog(window, "Save", lastDir)
    dlg.selectFile(img.filename)
    if dlg.exec_():
        newDir = dlg.directory().absolutePath()
        window.settings.setValue('paths/dlgdir', newDir)
        filenames = dlg.selectedFiles()
        if filenames:
            filename = filenames[0]
        else:
            msg = QMessageBox()
            msg.setWindowTitle('Warning')
            msg.setIcon(QMessageBox.Warning)
            msg.setText("You must select a file")
            msg.exec_()
            return False
        if isfile(filename):
            reply = QMessageBox()
            reply.setWindowTitle('Warning')
            reply.setIcon(QMessageBox.Warning)
            reply.setText("File %s exists\n" % filename)
            reply.setInformativeText("Save image as a new copy ?<br><font color='red'>CAUTION : Answering No will overwrite the file</font>")
            reply.setStandardButtons(QMessageBox.No | QMessageBox.Yes | QMessageBox.Cancel)
            reply.setDefaultButton(QMessageBox.Yes)
            ret = reply.exec_()
            if ret == QMessageBox.Cancel:
                return False
            elif ret == QMessageBox.Yes:
                i = 0
                base = filename
                if '_copy' in base:
                    flag = '_'
                else:
                    flag = '_copy'
                while isfile(filename):
                    filename = base[:-4] + flag + str(i) + base[-4:]
                    i = i+1
        #img = window.label.img
        # quality range 0..100
        # Note : class vImage overrides QImage.save()
        res = img.save(filename, quality=100)
        if res:
            # copy sidecar to file
            with exiftool.ExifTool() as e:
                e.restoreMetadata(img.filename, filename)
        else:
            return False
        return True

def close(e):
    """
    app close event handler
    @param e: close event
    """
    if window.label.img.isModified:
        ret = savingDialog(window.label.img)
        if ret == QMessageBox.Save:
            save(window.label.img)
            return True
        elif ret == QMessageBox.Cancel:
            return False
    return True

def updateStatus():
    img = window.label.img
    s = img.filename + ' ' + (' '.join(['*']*img.meta.rating))
    if img.useThumb:
        s = s + '  ' + '<font color=red><b>Preview</b></font> '
    window.Label_status.setText(s)

###########
# app init
##########
# help Window
helpWindow=None

# style sheet
app.setStyleSheet("QMainWindow, QGraphicsView, QListWidget, QMenu, QTableView {background-color: rgb(200, 200, 200)}\
                   QMenu, QTableView { selection-background-color: blue;\
                                        selection-color: white;}"
                 )
# status bar
window.Label_status = QLabel()
window.statusBar().addWidget(window.Label_status)
window.updateStatus = updateStatus

# splash screen
pixmap = QPixmap('logo.png')
splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
splash.show()
app.processEvents()
splash.showMessage("Loading .", color=Qt.white, alignment=Qt.AlignCenter)
app.processEvents()
sleep(1)
splash.showMessage("Loading ...", color=Qt.white, alignment=Qt.AlignCenter)
app.processEvents()
#sleep(1)

# close event handler
window.onCloseEvent = close

# mouse hover events
window.label.setMouseTracking(True)

# GUI Slot hooks
window.onWidgetChange = widgetChange
#window.onShowContextMenu = contextMenu
window.onExecMenuFile = menuFile
window.onExecFileOpen = openFile
window.onExecMenuWindow = menuWindow
window.onExecMenuImage = menuImage
window.onExecMenuLayer = menuLayer
window.onExecMenuHelp = menuHelp


# load current settings
window.readSettings()
window._recentFiles = window.settings.value('paths/recent', [])

set_event_handler(window.label)
set_event_handler(window.label_2)

img=QImage(200, 200, QImage.Format_ARGB32)
img.fill(Qt.darkGray)
defaultImImage = imImage(QImg=img, meta=metadata(name='noName'))

PROFILES_LIST = icc.getProfiles()
initMenuAssignProfile()
updateMenuOpenRecent()

window.label.img = defaultImImage
window.label_2.img = defaultImImage

window.showMaximized()
splash.finish(window)

# init EyeDropper
window.cursor_EyeDropper = QCursor(QPixmap.fromImage(QImage(":/images/resources/Eyedropper-icon.png")))

sys.exit(app.exec_())
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
import numpy as np
from math import factorial
from PySide2.QtGui import QColor, QPainterPath, QPen, QImage, QPainter
from PySide2.QtWidgets import QListWidget, QListWidgetItem, QGraphicsPathItem, QDialog, QVBoxLayout, \
    QFileDialog, QSlider, QWidget, QHBoxLayout, QLabel, QMessageBox, QPushButton
from PySide2.QtCore import Qt, QPoint, QEvent, QObject, QUrl, QRect, QDir
from os.path import isfile

import exiftool
from imgconvert import QImageBuffer


class channelValues():
    RGB, Red, Green, Blue =[0,1,2], [0], [1], [2]
    HSB, Hue, Sat, Br = [0, 1, 2], [0], [1], [2]
    Lab, L, a, b = [0, 1, 2], [0], [1], [2]

def saveChangeDialog(img):
    reply = QMessageBox()
    reply.setText("%s has been modified" % img.meta.name if len(img.meta.name) > 0 else 'unnamed image')
    reply.setInformativeText("Save your changes ?")
    reply.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
    reply.setDefaultButton(QMessageBox.Save)
    ret = reply.exec_()
    return ret

def save(img, mainWidget):
    """
    Image saving dialogs. The actual saving is
    done by mImage.save(). Raises ValueError if saving fails.
    @param img:
    @type img: QImage
    """
    # get last accessed dir
    lastDir = mainWidget.settings.value("paths/dlgdir", QDir.currentPath())
    # file dialogs
    dlg = savingDialog(mainWidget, "Save", lastDir)
    dlg.selectFile(img.filename)
    if dlg.exec_():
        newDir = dlg.directory().absolutePath()
        mainWidget.settings.setValue('paths/dlgdir', newDir)
        filenames = dlg.selectedFiles()
        if filenames:
            filename = filenames[0]
        else:
            raise ValueError("You must select a file")
        if isfile(filename):
            reply = QMessageBox()
            reply.setWindowTitle('Warning')
            reply.setIcon(QMessageBox.Warning)
            reply.setText("File %s already exists\n" % filename)
            #reply.setInformativeText("Save image as a new copy ?<br><font color='red'>CAUTION : Answering No will overwrite the file</font>")
            #reply.setStandardButtons(QMessageBox.No | QMessageBox.Yes | QMessageBox.Cancel)
            reply.setStandardButtons(QMessageBox.Cancel)
            accButton = QPushButton("Save as New Copy")
            rejButton = QPushButton("OverWrite")
            reply.addButton(accButton, QMessageBox.AcceptRole)
            reply.addButton(rejButton, QMessageBox.RejectRole)
            reply.setDefaultButton(accButton)
            reply.exec_()
            retButton = reply.clickedButton()
            # build a new name
            if retButton is accButton:
                i = 0
                base = filename
                if '_copy' in base:
                    flag = '_'
                else:
                    flag = '_copy'
                while isfile(filename):
                    filename = base[:-4] + flag + str(i) + base[-4:]
                    i = i+1
            # overwrite
            elif retButton is rejButton:
                pass
            else:
                raise ValueError("Saving Operation Failure")
        quality = dlg.sliderQual.value()
        compression = dlg.sliderComp.value()
        img.save(filename, quality=quality, compression=compression)  #mImage.save()
        with exiftool.ExifTool() as e:
            e.restoreMetadata(img.filename, filename)
        return filename
    else:
        raise ValueError("Saving Operation Failure")

def openDlg(mainWidget):
    if mainWidget.label.img.isModified:
        ret = saveChangeDialog(mainWidget.label.img)
        if ret == QMessageBox.Yes:
            save(mainWidget.label.img, mainWidget)
        elif ret == QMessageBox.Cancel:
            return
    lastDir = mainWidget.settings.value('paths/dlgdir', '.')
    dlg = QFileDialog(mainWidget, "select", lastDir, "*.jpg *.jpeg *.png *.tif *.tiff *.bmp")
    if dlg.exec_():
        filenames = dlg.selectedFiles()
        newDir = dlg.directory().absolutePath()
        mainWidget.settings.setValue('paths/dlgdir', newDir)
        # update list of recent files
        filter(lambda a: a != filenames[0], mainWidget._recentFiles)
        mainWidget._recentFiles.insert(0, filenames[0])
        if len(mainWidget._recentFiles) > 10:
            mainWidget._recentFiles.pop()  # remove last item
        mainWidget.settings.setValue('paths/recent', mainWidget._recentFiles)
        return filenames[0]
    else:
        return None

class optionsWidget(QListWidget) :
    """
    Displays a list of options with checkboxes.
    The choices can be mutually exclusive (default) or not
    exclusive.
    """

    def __init__(self, options=[], exclusive=True, parent=None):
        """
        @param options: list of strings
        @param exclusive: boolean
        """
        super(optionsWidget, self).__init__(parent)
        self.items = {}
        self.options = {}
        for option in options:
            listItem = QListWidgetItem(option, self)
            listItem.setCheckState(Qt.Unchecked)
            self.addItem(listItem)
            self.items[option] = listItem
            self.options[option] = (listItem.checkState() == Qt.Checked)
        #self.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.setMinimumWidth(self.sizeHintForColumn(0))
        self.setMinimumHeight(self.sizeHintForRow(0)*len(options))
        self.exclusive = exclusive
        self.itemClicked.connect(self.select)
        # selection hook.
        self.onSelect = lambda x : 0

    def select(self, item):
        """
        Item clicked event handler
        @param item:
        @type item: QListWidgetItem
        """
        if self.exclusive:
            for r in range(self.count()):
                currentItem = self.item(r)
                if currentItem is not item:
                    currentItem.setCheckState(Qt.Unchecked)
                else:
                    currentItem.setCheckState(Qt.Checked)
        for option in self.options.keys():
            self.options[option] = (self.items[option].checkState() == Qt.Checked)
        # if item.checkState() == Qt.Checked: # TODO modified 5/11 : mandatory modif. for histView update when deselecting options
        self.onSelect(item)

    def checkOption(self, name):
        item = self.items[name]
        item.setCheckState(Qt.Checked)
        self.select(item)

class croppingHandle(QPushButton):

    def __init__(self, role='', parent=None):
        super().__init__(parent=parent)
        self.role = role
        self.margin = 0

    def mouseMoveEvent(self, event):
        p = self.mapToParent(event.pos())
        widg = self.parent()
        img = widg.img
        r = img.resize_coeff(widg)
        if self.role == 'left':
            if (p.x() < img.xOffset) or (p.x() > img.xOffset + img.width() * r):
                return
            p.setY(self.pos().y())
            self.margin  = (p.x() - img.xOffset) // r
        elif self.role == 'right':
            if (p.x() < img.xOffset) or (p.x() > img.xOffset + img.width() * r):
                return
            p.setY(self.pos().y())
            self.margin  = img.width() - (p.x() - img.xOffset) // r
        elif self.role == 'top':
            if (p.y() < img.yOffset) or (p.y() > img.yOffset + img.height() * r):
                return
            p.setX(self.pos().x())
            self.margin = (p.y() - img.yOffset) // r
        elif self.role == 'bottom':
            if (p.y() < img.yOffset) or (p.y() > img.yOffset + img.height() * r):
                return
            p.setX(self.pos().x())
            self.margin = img.height() - (p.y() - img.yOffset) // r
        self.move(p)
        widg.repaint()


class savingDialog(QDialog):
    """
    File dialog with quality and compression sliders added.
    We use a standard QFileDialog as a child widget and we
    forward its methods to the top level.
    """
    def __init__(self, parent, text, lastDir):
        """

        @param parent:
        @type parent: QObject
        @param text:
        @type text: str
        @param lastDir:
        @type lastDir:str
        """
        # QDialog __init__
        super().__init__()
        # File Dialog
        self.dlg = QFileDialog(caption=text, directory=lastDir)
        # sliders
        self.sliderComp = QSlider(Qt.Horizontal)
        self.sliderComp.setTickPosition(QSlider.TicksBelow)
        self.sliderComp.setRange(0, 100)
        self.sliderComp.setSingleStep(10)
        self.sliderComp.setValue(100)
        self.sliderQual = QSlider(Qt.Horizontal)
        self.sliderQual.setTickPosition(QSlider.TicksBelow)
        self.sliderQual.setRange(0, 100)
        self.sliderQual.setSingleStep(10)
        self.sliderQual.setValue(100)
        self.dlg.setVisible(True)
        l = QVBoxLayout()
        h = QHBoxLayout()
        l.addWidget(self.dlg)
        h.addWidget(QLabel("Quality"))
        h.addWidget(self.sliderQual)
        h.addWidget(QLabel("Compression"))
        h.addWidget(self.sliderComp)
        l.addLayout(h)
        self.setLayout(l)
        # file dialog close event handler
        def f():
            self.close()
        self.dlg.finished.connect(f)

    def exec_(self):
        # QDialog exec_
        super().exec_()
        # forward file dialog result
        return self.dlg.result()

    def selectFile(self, fileName):
        self.dlg.selectFile(fileName)

    def selectedFiles(self):
        return self.dlg.selectedFiles()

    def directory(self):
        return self.dlg.directory()

def savitzky_golay(y, window_size, order, deriv=0, rate=1):
    """
    This pure numpy implementation of the savitzky_golay filter is taken
    from http://stackoverflow.com/questions/22988882/how-to-smooth-a-curve-in-python
    Many thanks to elviuz.
    @param y: data (type numpy array)
    @param window_size:
    @param order:
    @param deriv:
    @param rate:
    @return: smoothed data array
    """

    try:
        window_size = np.abs(np.int(window_size))
        order = np.abs(np.int(order))
    except ValueError :
        raise ValueError("window_size and order have to be of type int")
    if window_size % 2 != 1 or window_size < 1:
        raise TypeError("window_size size must be a positive odd number")
    if window_size < order + 2:
        raise TypeError("window_size is too small for the polynomials order")

    order_range = range(order+1)
    half_window = (window_size -1) // 2

    # precompute coefficients
    b = np.mat([[k**i for i in order_range] for k in range(-half_window, half_window+1)])
    m = np.linalg.pinv(b).A[deriv] * rate**deriv * factorial(deriv)

    # pad the signal at the extremes with
    # values taken from the signal itself
    firstvals = y[0] - np.abs( y[1:half_window+1][::-1] - y[0] )
    lastvals = y[-1] + np.abs(y[-half_window-1:-1][::-1] - y[-1])
    y = np.concatenate((firstvals, y, lastvals))
    return np.convolve( m[::-1], y, mode='valid')

def checkeredImage(w, h, format=QImage.Format_ARGB32):
    image = QImage(w, h, format)

    # init pattern
    base = QImage(20, 20, format)
    qp = QPainter(base)
    qp.setCompositionMode(QPainter.CompositionMode_Source)
    qp.fillRect(0, 0, 10, 10, Qt.gray)
    qp.fillRect(10, 0, 10, 10, Qt.white)
    qp.fillRect(0, 10, 10, 10, Qt.white)
    qp.fillRect(10, 10, 10, 10, Qt.gray)
    qp.end()

    qp=QPainter(image)
    qp.setCompositionMode(QPainter.CompositionMode_Source)

    # draw the pattern once at 0,0
    qp.drawImage(0, 0, base)

    imageW = image.width()
    imageH = image.height()
    baseW = base.width()
    baseH = base.height()
    while ((baseW < imageW) or (baseH < imageH) ):
        if (baseW < imageW) :
            # Copy and draw the existing pattern to the right
            qp.drawImage(QRect(baseW, 0, baseW, baseH), image, QRect(0, 0, baseW, baseH))
            baseW *= 2
        if (baseH < imageH) :
            # Copy and draw the existing pattern to the bottom
            qp.drawImage(QRect(0, baseH, baseW, baseH), image, QRect(0, 0, baseW, baseH))
            # Update height of our pattern
            baseH *= 2
    qp.end()
    return image

def clip(image, mask, inverted=False):
    """
    clip an image by applying a mask to its alpha channel
    @param image:
    @type image:
    @param mask:
    @type mask:
    @param inverted:
    @type inverted:
    @return:
    @rtype:
    """
    bufImg = QImageBuffer(image)
    bufMask = QImageBuffer(mask)
    if inverted:
        bufMask = bufMask.copy()
        bufMask[:,:,3] = 255 - bufMask[:,:,3]
    bufImg[:,:,3] = bufMask[:,:,3]

def drawPlotGrid(axeSize):
    item = QGraphicsPathItem()
    item.setPen(QPen(QColor(255, 0, 0), 1, Qt.DashLine))
    qppath = QPainterPath()
    qppath.moveTo(QPoint(0, 0))
    qppath.lineTo(QPoint(axeSize, 0))
    qppath.lineTo(QPoint(axeSize, -axeSize))
    qppath.lineTo(QPoint(0, -axeSize))
    qppath.closeSubpath()
    qppath.lineTo(QPoint(axeSize, -axeSize))
    for i in range(1, 5):
        a = (axeSize * i) / 4
        qppath.moveTo(a, -axeSize)
        qppath.lineTo(a, 0)
        qppath.moveTo(0, -a)
        qppath.lineTo(axeSize, -a)
    item.setPath(qppath)
    return item
    #self.graphicsScene.addItem(item)

def boundingRect(img, pattern):
    """
    Given an image img, the function builds the bounding rectangle
    of the region defined by img == pattern. If the region is empty, the function
    returns an invalid rectangle.
    @param img:
    @type img: 2D array
    @param pattern:
    @type pattern: a.dtype
    @return:
    @rtype: QRect or None
    """
    def leftPattern(b):
        """
        For a 1-channel image, returns the leftmost
        x-coordinate of max value.
        @param b: image
        @type b: 2D array, dtype=int or float
        @return: leftmost x-coordinate of max value
        @rtype: int
        """
        # we build the array of first occurrences of row max
        XMin = np.argmax(b, axis=1)
        # To exclude the rows with a max different of the global max,
        # we assign to them a value greater than all possible indices.
        XMin = np.where(np.diagonal(b[:, XMin])==np.max(b), XMin, np.sum(b.shape)+1)
        return np.min(XMin)

    # indicator function of the region
    img = np.where(img==pattern, 1, 0)
    # empty region
    if np.max(img) == 0:
        return None
    # building enclosing rectangle
    left = leftPattern(img)
    right = img.shape[1] - 1 - leftPattern(img[::-1, ::-1])
    top = leftPattern(img.T)
    bottom = img.shape[0] - 1 - leftPattern(img.T[::-1, ::-1])
    return QRect(left, top, right - left, bottom - top)


"""
#pickle example
saved_data = dict(outputFile, 
                  saveFeature1 = feature1, 
                  saveFeature2 = feature2, 
                  saveLabel1 = label1, 
                  saveLabel2 = label2,
                  saveString = docString)

with open('test.dat', 'wb') as outfile:
    pickle.dump(saved_data, outfile, protocol=pickle.HIGHEST_PROTOCOL)
"""
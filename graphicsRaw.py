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
from math import log
import numpy as np
from PySide2 import QtCore
from PySide2.QtCore import Qt
from PySide2.QtGui import QFontMetrics
from PySide2.QtWidgets import QSizePolicy, QVBoxLayout, QLabel, QHBoxLayout, QFrame, QGroupBox, QWidget
from colorConv import temperatureAndTint2RGBMultipliers, RGBMultipliers2TemperatureAndTint
from graphicsLUT import graphicsQuadricForm
from utils import optionsWidget, UDict, QbLUeSlider

class rawForm (QWidget): #(QGraphicsView): TODO Modified 25/06/18 validate
    """
    GUI for postprocessing of raw files
    # cf https://github.com/LibRaw/LibRaw/blob/master/src/libraw_cxx.cpp
    """
    dataChanged = QtCore.Signal(bool)
    @classmethod
    def getNewWindow(cls, targetImage=None, axeSize=500, layer=None, parent=None, mainForm=None):
        wdgt = rawForm(axeSize=axeSize, layer=layer, parent=parent, mainForm=mainForm)
        wdgt.setWindowTitle(layer.name)
        return wdgt

    @classmethod
    def slider2Temp(cls, v):
        return 2000 + v * v

    @classmethod
    def temp2Slider(cls, T):
        return np.sqrt(T - 2000)

    @classmethod
    def slider2Tint(cls, v):
        return 0.1 + 0.0125 * v  # 0.2 + 0.0125 * v  # wanted range : 0.2...2.5
        # coeff = (self.tempCorrection / 4000 - 1) * 1.2 # experimental formula
        # eturn coeff + 0.01*v

    @classmethod
    def tint2Slider(cls, t):
        return (t - 0.1) / 0.0125
        # coeff = (self.tempCorrection / 4000 - 1) * 1.2 # experimental formula
        # return (t-coeff)/0.01
        # displayed value

    @classmethod
    def sliderTint2User(cls, v):
        return v - 75  # ((slider2Tint(v) - 1)*100)

    @classmethod
    def slider2Exp(cls, v):
        return v / 20.0 - 2.0

    @classmethod
    def exp2Slider(cls, e):
        return round((e + 2.0) * 20.0)

    @classmethod
    def slider2Cont(cls, v):
        return v

    @classmethod
    def cont2Slider(cls, e):
        return e

    @classmethod
    def slider2Br(cls, v):
        return (np.power(3, v/50) - 1) / 2

    @classmethod
    def br2Slider(cls, v):
        return 50 * log(2*v + 1, 3) #int(round(50.0 * e))

    @classmethod
    def brSlider2User(cls, v):
        return (v - 50)

    @classmethod
    def slider2Sat(cls, v):
        return v - 50

    @classmethod
    def sat2Slider(cls, e):
        return e + 50

    def __init__(self, targetImage=None, axeSize=500, layer=None, parent=None, mainForm=None):
        super().__init__(parent=parent)
        self.setStyleSheet('QRangeSlider * {border: 0px; padding: 0px; margin: 0px}')
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMinimumSize(axeSize, axeSize+200)  # +200 to prevent scroll bars in list Widgets
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.layer = layer
        #######################################
        # Libraw correspondances:
        # rgb_xyz_matrix is libraw cam_xyz
        # camera_whitebalance is libraw cam_mul
        # daylight_whitebalance is libraw pre_mul
        ##########################################
        rawpyObj = layer.parentImage.rawImage
        # initial post processing multipliers (as shot)
        self.rawMultipliers = rawpyObj.camera_whitebalance
        self.sampleMultipliers = False
        self.samples = []
        # pre multipliers
        self.daylight = rawpyObj.daylight_whitebalance
        # convert multipliers to White Point RGB coordinates, modulo tint green correction (mult[1] = tint*WP_G)
        self.cameraMultipliers = [self.daylight[i] / self.rawMultipliers[i] for i in range(3)]
        #print ('WB', [self.daylight[i]*(10**5)/ rawpyObj.camera_whitebalance[i] for i in range(3)])
        ########################################
        # Camera RGB -> XYZ conversion matrix:
        # This matrix is constant for each camera model,
        # Last row is zero for RGB cameras and non-zero for
        # different color models (CMYG and so on), cf. rawpy and libraw docs.
        # type ndarray, shape (4,3)
        #########################################
        self.rgb_xyz_matrix = rawpyObj.rgb_xyz_matrix[:3,:]
        self.rgb_xyz_matrix_inverse = np.linalg.inv(self.rgb_xyz_matrix)
        ##########################################
        # Color_matrix, read from file for some cameras, calculated for others,
        # type ndarray of shape (3,4), seems to be 0.
        # color_matrix = rawpyObj.color_matrix
        ##########################################
        # initial temp and tint (as shot values)
        self.cameraTemp, self.cameraTint = RGBMultipliers2TemperatureAndTint(*self.cameraMultipliers, self.rgb_xyz_matrix_inverse)
        # base tint correction. It depends on temperature only.
        # We use the product baseTint * tintCorrection as the current tint adjustment,
        # keeping tintCorrection near to 1.0
        self.baseTint = self.cameraTint
        # attributes initialized in setDefaults, declared here
        # for the sake of correctness
        self.tempCorrection, self.tintCorrection, self.expCorrection, self.highCorrection,\
                                                   self.contCorrection, self.satCorrection, self.brCorrection = [None] * 7
        # contrast spline view, initialized in setContrastSpline
        self.contrastForm = None
        # options : it turns out that the most accurate description for the 'Auto Brightness' option of rawpy.postprocess is 'Auto Expose'
        optionList0, optionNames0 = ['Auto Brightness', 'Preserve Highlights', 'manualCurve'], ['Auto Expose', 'Preserve Highlights', 'Show Contrast Curve']
        self.listWidget1 = optionsWidget(options=optionList0, optionNames=optionNames0, exclusive=False, changed=lambda: self.dataChanged.emit(True))
        self.listWidget1.checkOption(self.listWidget1.intNames[0])
        self.listWidget1.checkOption(self.listWidget1.intNames[1])
        optionList1, optionNames1 = ['Auto WB', 'Camera WB', 'User WB'], ['Auto', 'Camera (As Shot)', 'User']
        self.listWidget2 = optionsWidget(options=optionList1, optionNames=optionNames1,  exclusive=True, changed=lambda: self.dataChanged.emit(True))
        self.listWidget2.checkOption(self.listWidget2.intNames[1])
        self.options = UDict(self.listWidget1.options, self.listWidget2.options)

        # highlight correction slider
        self.sliderHigh= QbLUeSlider(Qt.Horizontal)
        self.sliderHigh.setStyleSheet(QbLUeSlider.bLueSliderDefaultColorStylesheet)
        self.sliderHigh.setRange(0, 9)
        self.sliderHigh.setSingleStep(1)

        self.highLabel = QLabel()
        self.highLabel.setText("High. ")

        self.highValue = QLabel()
        font = self.highValue.font()
        metrics = QFontMetrics(font)
        w = metrics.width("100")
        h = metrics.height()
        self.highValue.setMinimumSize(w, h)
        self.highValue.setMaximumSize(w, h)
        self.highValue.setText(str("{:.0f}".format(self.sliderHigh.value())))

        # highlight update event handler
        def highUpdate(value):
            self.highValue.setText(str("{:+d}".format(int(self.sliderHigh.value()))))
            # move not yet terminated or value not modified
            if self.sliderHigh.isSliderDown() or self.sliderHigh.value() == self.highCorrection:
                return
            self.sliderHigh.valueChanged.disconnect()
            self.sliderHigh.sliderReleased.disconnect()
            self.highCorrection = self.sliderHigh.value()
            self.dataChanged.emit(True)
            self.sliderHigh.sliderReleased.connect(lambda: highUpdate(self.sliderHigh.value()))
            self.sliderHigh.valueChanged.connect(highUpdate)  # send new value as parameter

        self.sliderHigh.valueChanged.connect(highUpdate)  # send new value as parameter
        self.sliderHigh.sliderReleased.connect(lambda: highUpdate(self.sliderHigh.value()))

        # temp slider
        self.sliderTemp = QbLUeSlider(Qt.Horizontal)
        self.sliderTemp.setStyleSheet(QbLUeSlider.bLueSliderDefaultColorStylesheet)
        self.sliderTemp.setRange(0,130)
        self.sliderTemp.setSingleStep(1)

        self.tempLabel = QLabel()
        self.tempLabel.setText("Temp")

        self.tempValue = QLabel()
        font = self.tempValue.font()
        metrics = QFontMetrics(font)
        w = metrics.width("10000")
        h = metrics.height()
        self.tempValue.setMinimumSize(w, h)
        self.tempValue.setMaximumSize(w, h)
        self.tempValue.setText(str("{:.0f}".format(self.slider2Temp(self.sliderTemp.value()))))

        self.sliderTemp.valueChanged.connect(self.tempUpdate)  # send new value as parameter
        self.sliderTemp.sliderReleased.connect(lambda :self.tempUpdate(self.sliderTemp.value()))  # signal has no parameter

        # tint slider
        self.sliderTint = QbLUeSlider(Qt.Horizontal)
        # self.sliderTint.setStyleSheet(self.sliderTint.styleSheet()+'QSlider::groove:horizontal {background: red;}')
        self.sliderTint.setStyleSheet(QbLUeSlider.bLueSliderDefaultColorStylesheet)
        self.sliderTint.setRange(0, 150)

        self.sliderTint.setSingleStep(1)

        self.tintLabel = QLabel()
        self.tintLabel.setText("Tint")

        self.tintValue = QLabel()
        font = self.tempValue.font()
        metrics = QFontMetrics(font)
        w = metrics.width("100")
        h = metrics.height()
        self.tintValue.setMinimumSize(w, h)
        self.tintValue.setMaximumSize(w, h)
        self.tintValue.setText(str("{:.0f}".format(self.sliderTint2User(self.sliderTint.value()))))

        self.sliderTint.valueChanged.connect(self.tintUpdate)
        self.sliderTint.sliderReleased.connect(lambda :self.tintUpdate(self.sliderTint.value()))  # signal has no parameter)

        ######################
        # From libraw and dcraw sources:
        # Exposure and brightness are curve transformations.
        # Exposure curve is y = alpha*x, with cubic root ending, applied before demosaicing.
        # Brightness is (similar to) y = x**alpha and part of gamma transformation from linear sRGB to RGB.
        # Exposure and brightness both dilate the histogram towards highlights.
        # Exposure dilatation is uniform (homothety), brightness dilataion is
        # maximum for the midtones and the highlghts are preserved.
        # As a consequence, normal wokflow begins with the adjustment of exposure,
        # to fill the entire range of the histogram and to adjust the highlights. Next,
        # one adjusts the brightness to put the midtones at the level we want them to be.
        # Cf. https://www.cambridgeincolour.com/forums/thread653.htm
        #####################

        # exp slider
        self.sliderExp = QbLUeSlider(Qt.Horizontal)
        self.sliderExp.setStyleSheet(QbLUeSlider.bLueSliderDefaultBWStylesheet)
        self.sliderExp.setRange(0, 100)

        self.sliderExp.setSingleStep(1)

        self.expLabel = QLabel()
        self.expLabel.setText("Exp.")

        self.expValue = QLabel()
        font = self.expValue.font()
        metrics = QFontMetrics(font)
        w = metrics.width("+1.0")
        h = metrics.height()
        self.expValue.setMinimumSize(w, h)
        self.expValue.setMaximumSize(w, h)
        self.expValue.setText(str("{:.1f}".format(self.slider2Exp(self.sliderExp.value()))))

        # exp done event handler
        def expUpdate(value):
            self.expValue.setText(str("{:.1f}".format(self.slider2Exp(self.sliderExp.value()))))
            # move not yet terminated or value not modified
            if self.sliderExp.isSliderDown() or self.slider2Exp(value) == self.expCorrection:
                return
            self.sliderExp.valueChanged.disconnect()
            self.sliderExp.sliderReleased.disconnect()
            # rawpy: expCorrection range is -2.0...3.0, boiling down to exp_shift range 2**(-2)=0.25...2**3=8.0
            self.expCorrection = self.slider2Exp(self.sliderExp.value())
            self.dataChanged.emit(True)
            self.sliderExp.valueChanged.connect(expUpdate)  # send new value as parameter
            self.sliderExp.sliderReleased.connect(lambda: expUpdate(self.sliderExp.value()))  # signal has no parameter
        self.sliderExp.valueChanged.connect(expUpdate)  # send new value as parameter
        self.sliderExp.sliderReleased.connect(lambda: expUpdate(self.sliderExp.value()))      # signal has no parameter

        # brightness slider
        brSlider = QbLUeSlider(Qt.Horizontal)
        brSlider.setRange(1, 101)

        self.sliderExp.setSingleStep(1)

        brSlider.setStyleSheet(QbLUeSlider.bLueSliderDefaultBWStylesheet)

        self.sliderBrightness = brSlider
        brLabel = QLabel()
        brLabel.setText("Bright.")

        self.brValue = QLabel()
        font = self.expValue.font()
        metrics = QFontMetrics(font)
        w = metrics.width("+99")
        h = metrics.height()
        self.brValue.setMinimumSize(w, h)
        self.brValue.setMaximumSize(w, h)
        self.brValue.setText(str("{:+d}".format(int(self.brSlider2User(self.sliderBrightness.value())))))

        # brightness done event handler
        def brUpdate(value):
            self.brValue.setText(str("{:+d}".format(int(self.brSlider2User(self.sliderBrightness.value())))))
            # move not yet terminated or value not modified
            if self.sliderBrightness.isSliderDown() or self.slider2Br(value) == self.brCorrection:
                return
            self.sliderBrightness.valueChanged.disconnect()
            self.sliderBrightness.sliderReleased.disconnect()
            self.brCorrection = self.slider2Br(self.sliderBrightness.value())
            self.dataChanged.emit(True)
            self.sliderBrightness.sliderReleased.connect(lambda: brUpdate(self.sliderBrightness.value()))
            self.sliderBrightness.valueChanged.connect(brUpdate)  # send new value as parameter
        self.sliderBrightness.valueChanged.connect(brUpdate)  # send new value as parameter
        self.sliderBrightness.sliderReleased.connect(lambda: brUpdate(self.sliderBrightness.value()))

        # contrast slider
        self.sliderCont = QbLUeSlider(Qt.Horizontal)
        self.sliderCont.setStyleSheet(QbLUeSlider.bLueSliderDefaultBWStylesheet)
        self.sliderCont.setRange(0, 20)

        self.sliderCont.setSingleStep(1)

        self.contLabel = QLabel()
        self.contLabel.setText("Cont.")

        self.contValue = QLabel()
        font = self.contValue.font()
        metrics = QFontMetrics(font)
        w = metrics.width("100")
        h = metrics.height()
        self.contValue.setMinimumSize(w, h)
        self.contValue.setMaximumSize(w, h)
        self.contValue.setText(str("{:.0f}".format(self.slider2Cont(self.sliderCont.value()))))

        # cont done event handler
        def contUpdate(value):
            self.contValue.setText(str("{:.0f}".format(self.slider2Cont(self.sliderCont.value()))))
            # move not yet terminated or value not modified
            if self.sliderCont.isSliderDown() or self.slider2Cont(value) == self.tempCorrection:
                return
            self.sliderCont.valueChanged.disconnect()
            self.sliderCont.sliderReleased.disconnect()
            self.contCorrection = self.slider2Cont(self.sliderCont.value())
            self.contValue.setText(str("{:+d}".format(self.contCorrection)))
            # force to recalculate the spline
            self.layer.autoSpline = True
            self.dataChanged.emit(False)
            self.sliderCont.valueChanged.connect(contUpdate)  # send new value as parameter
            self.sliderCont.sliderReleased.connect(lambda: contUpdate(self.sliderCont.value()))  # signal has no parameter
        self.sliderCont.valueChanged.connect(contUpdate)  # send new value as parameter
        self.sliderCont.sliderReleased.connect(lambda: contUpdate(self.sliderCont.value()))  # signal has no parameter

        # saturation slider
        self.sliderSat = QbLUeSlider(Qt.Horizontal)
        self.sliderSat.setStyleSheet(QbLUeSlider.bLueSliderDefaultColorStylesheet)
        self.sliderSat.setRange(0, 100)

        self.sliderSat.setSingleStep(1)

        satLabel = QLabel()
        satLabel.setText("Sat.")

        self.satValue = QLabel()
        font = self.satValue.font()
        metrics = QFontMetrics(font)
        w = metrics.width("+10")
        h = metrics.height()
        self.satValue.setMinimumSize(w, h)
        self.satValue.setMaximumSize(w, h)
        self.satValue.setText(str("{:+d}".format(self.slider2Sat(self.sliderSat.value()))))

        """sat done event handler"""
        def satUpdate(value):
            self.satValue.setText(str("{:+d}".format(self.slider2Sat(self.sliderSat.value()))))
            # move not yet terminated or value not modified
            if self.sliderSat.isSliderDown() or self.slider2Sat(value) == self.satCorrection:
                return
            self.sliderSat.valueChanged.disconnect()
            self.sliderSat.sliderReleased.disconnect()
            self.satCorrection = self.slider2Sat(self.sliderSat.value())
            self.dataChanged.emit(False)
            self.sliderSat.valueChanged.connect(satUpdate)  # send new value as parameter
            self.sliderSat.sliderReleased.connect(lambda: satUpdate(self.sliderSat.value()))  # signal has no parameter
        self.sliderSat.valueChanged.connect(satUpdate)  # send new value as parameter
        self.sliderSat.sliderReleased.connect(lambda: satUpdate(self.sliderSat.value()))  # signal has no parameter

        self.dataChanged.connect(self.updateLayer)
        self.setStyleSheet("QListWidget, QLabel {font : 7pt;}")

        """layout"""
        l = QVBoxLayout()
        l.setContentsMargins(8, 8, 8, 8)  # left, top, right, bottom
        l.setAlignment(Qt.AlignBottom)
        hl1 = QHBoxLayout()
        hl1.addWidget(self.expLabel)
        hl1.addWidget(self.expValue)
        hl1.addWidget(self.sliderExp)
        l.addWidget(self.listWidget1)
        self.listWidget2.setStyleSheet("QListWidget {border: 0px;} QListWidget::item {border: 0px; padding-left: 20px;}")
        vl1 = QVBoxLayout()
        vl1.addWidget(QLabel('White Balance'))
        vl1.addWidget(self.listWidget2)
        gb1 = QGroupBox()
        gb1.setStyleSheet("QGroupBox {border: 1px solid gray; border-radius: 4px}")
        hl2 = QHBoxLayout()
        hl2.addWidget(self.tempLabel)
        hl2.addWidget(self.tempValue)
        hl2.addWidget(self.sliderTemp)
        hl3 = QHBoxLayout()
        hl3.addWidget(self.tintLabel)
        hl3.addWidget(self.tintValue)
        hl3.addWidget(self.sliderTint)
        vl1.addLayout(hl2)
        vl1.addLayout(hl3)
        gb1.setLayout(vl1)
        l.addWidget(gb1)
        hl4 = QHBoxLayout()
        hl4.addWidget(self.contLabel)
        hl4.addWidget(self.contValue)
        hl4.addWidget(self.sliderCont)
        hl8 = QHBoxLayout()
        hl8.addWidget(brLabel)
        hl8.addWidget(self.brValue)
        hl8.addWidget(self.sliderBrightness)
        hl7 = QHBoxLayout()
        hl7.addWidget(satLabel)
        hl7.addWidget(self.satValue)
        hl7.addWidget(self.sliderSat)
        #hl5 = QHBoxLayout()
        #hl5.addWidget(noiseLabel)
        #hl5.addWidget(self.noiseValue)
        #hl5.addWidget(self.sliderNoise)
        #l.addLayout(hl2)
        #l.addLayout(hl3)
        l.addLayout(hl1)
        hl10 = QHBoxLayout()
        hl10.addWidget(self.highLabel)
        hl10.addWidget(self.highValue)
        hl10.addWidget(self.sliderHigh)
        l.addLayout(hl10)
        l.addLayout(hl8)
        # separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        l.addWidget(sep)
        l.addLayout(hl4)
        l.addLayout(hl7)
        #l.addLayout(hl5)
        l.addStretch(1)
        self.setLayout(l)
        self.adjustSize()
        self.setDefaults()
        self.setWhatsThis(
"""Development of raw files
Contrast enhancement is based on an automatic algorithm well suited to multi-mode histograms. \
However, the correction curve can be edited manually by checking the option Show Contrast Curve. 
"""
                        ) # end of setWhatsThis

    def setContrastSpline(self, a, b, d, T):
        """
        Updates and displays the contrast spline
        @param a:
        @type a:
        @param b:
        @type b:
        @param d:
        @type d:
        @param T:
        @type T:
        """
        axeSize = 500
        if self.contrastForm is None:
            form = graphicsQuadricForm.getNewWindow(targetImage=None, axeSize=axeSize, layer=self.layer, parent=None,
                                                    mainForm=None)
            form.setWindowFlags(Qt.WindowStaysOnTopHint)
            form.setAttribute(Qt.WA_DeleteOnClose, on=False)
            form.setWindowTitle('Contrast Curve')
            self.contrastForm = form
        else:
            form = self.contrastForm
        form.scene().quadricB.setCurve(a * axeSize, b * axeSize, d, T * axeSize)
        form.showNormal()

    # temp changed  event handler
    def tempUpdate(self, value):
        self.tempValue.setText(str("{:.0f}".format(self.slider2Temp(self.sliderTemp.value()))))
        # move not yet terminated or value not modified
        if self.sliderTemp.isSliderDown() or self.slider2Temp(value) == self.tempCorrection:
            return
        self.sliderTemp.valueChanged.disconnect()
        self.sliderTemp.sliderReleased.disconnect()
        self.tempCorrection = self.slider2Temp(self.sliderTemp.value())

        multipliers = temperatureAndTint2RGBMultipliers(self.tempCorrection, 1.0, self.rgb_xyz_matrix_inverse)
        # Adjust the green multiplier to keep constant the ratio Mg/Mr, modulo the correction factor self.tintCorrection
        self.baseTint = self.cameraMultipliers[1] / self.cameraMultipliers[0] * multipliers[0] / multipliers[1] * self.tintCorrection
        m1 = multipliers[1] * (self.baseTint * self.tintCorrection)
        multipliers = (multipliers[0], m1, multipliers[2])
        self.rawMultipliers = [self.daylight[i] / multipliers[i] for i in range(3)] + [self.daylight[1] / multipliers[1]]
        m = min(self.rawMultipliers[:3])
        self.rawMultipliers = [self.rawMultipliers[i] / m for i in range(4)]
        self.dataChanged.emit(True)
        self.sliderTemp.valueChanged.connect(self.tempUpdate)  # send new value as parameter
        self.sliderTemp.sliderReleased.connect(lambda: self.tempUpdate(self.sliderTemp.value()))  # signal has no parameter

    # tint change event handler
    def tintUpdate(self, value):
        self.tintValue.setText(str("{:.0f}".format(self.sliderTint2User(self.sliderTint.value()))))
        # move not yet terminated or value not modified
        if self.sliderTint.isSliderDown() or self.slider2Tint(value) == self.tintCorrection:
            return
        self.sliderTint.valueChanged.disconnect()
        self.sliderTint.sliderReleased.disconnect()
        self.tintCorrection = self.slider2Tint(self.sliderTint.value())
        multipliers = temperatureAndTint2RGBMultipliers(self.tempCorrection, 1, self.rgb_xyz_matrix_inverse)
        m1 = multipliers[1] * (self.baseTint* self.tintCorrection)
        multipliers = (multipliers[0], m1, multipliers[2])
        self.rawMultipliers = [self.daylight[i] / multipliers[i] for i in range(3)] + [
            self.daylight[1] / multipliers[1]]
        m = min(self.rawMultipliers[:3])
        self.rawMultipliers = [self.rawMultipliers[i] / m for i in range(4)]
        self.dataChanged.emit(True)
        self.sliderTint.valueChanged.connect(self.tintUpdate)
        self.sliderTint.sliderReleased.connect(lambda: self.tintUpdate(self.sliderTint.value()))  # signal has no parameter)

    def setRawMultipliers(self, m0, m1, m2, sampling=True):
        mi = min(m0, m1, m2)
        m0, m1, m2 = m0/mi, m1/mi, m2/mi
        self.rawMultipliers = [m0, m1, m2, m1]
        # convert multipliers to White Point RGB coordinates, modulo tint green correction (mult[1] = tint*WP_G)
        invMultipliers = [self.daylight[i] / self.rawMultipliers[i] for i in range(3)]
        self.sliderTemp.valueChanged.disconnect()
        self.sliderTint.valueChanged.disconnect()
        # get temp and tint
        temp, tint = RGBMultipliers2TemperatureAndTint(*invMultipliers, self.rgb_xyz_matrix_inverse)
        self.baseTint = tint#
        tint = 1.0
        self.sliderTemp.setValue(self.temp2Slider(temp))
        self.sliderTint.setValue(self.tint2Slider(tint))
        self.tempValue.setText(str("{:.0f}".format(self.slider2Temp(self.sliderTemp.value()))))
        self.tintValue.setText(str("{:.0f}".format(self.sliderTint2User(self.sliderTint.value()))))
        self.sliderTemp.valueChanged.connect(self.tempUpdate)
        self.sliderTint.valueChanged.connect(self.tintUpdate)
        self.sampleMultipliers = sampling
        self.dataChanged.emit(True)

    def updateLayer(self, cacheInvalidate):
        """
        data changed event handler. If cacheInvalidate is True,
        the postprocessing cache is reset to None, to enforce
        a new raw postprocessing.
        @param cacheInvalidate:
        @type cacheInvalidate: boolean
        """
        if cacheInvalidate:
            # force raw postprocessing
            self.layer.postProcessCache = None
        self.enableSliders()
        self.layer.applyToStack()
        self.layer.parentImage.onImageChanged()

    def enableSliders(self):
        useUserWB = self.listWidget2.options["User WB"]
        useUserExp = not self.listWidget1.options["Auto Brightness"]
        self.sliderTemp.setEnabled(useUserWB)
        self.sliderTint.setEnabled(useUserWB)
        self.sliderExp.setEnabled(useUserExp)
        self.sliderHigh.setEnabled(useUserExp)
        self.tempValue.setEnabled(self.sliderTemp.isEnabled())
        self.tintValue.setEnabled(self.sliderTint.isEnabled())
        self.expValue.setEnabled(self.sliderExp.isEnabled())
        self.highValue.setEnabled(self.sliderHigh.isEnabled())
        self.tempLabel.setEnabled(self.sliderTemp.isEnabled())
        self.tintLabel.setEnabled(self.sliderTint.isEnabled())
        self.expLabel.setEnabled(self.sliderExp.isEnabled())
        self.highLabel.setEnabled(self.sliderHigh.isEnabled())

    def setDefaults(self):
        self.listWidget1.unCheckAll()
        self.listWidget2.unCheckAll()
        self.listWidget1.checkOption(self.listWidget1.intNames[0])
        self.listWidget1.checkOption(self.listWidget1.intNames[1])
        self.listWidget2.checkOption(self.listWidget2.intNames[1])
        self.enableSliders()
        self.tempCorrection = self.cameraTemp
        self.tintCorrection = 1.0
        self.expCorrection = 0.0
        self.highCorrection = 0
        self.contCorrection = 5.0
        #self.noiseCorrection = 0
        self.satCorrection = 0.0
        self.brCorrection = 1.0
        self.dataChanged.disconnect()
        self.sliderTemp.setValue(round(self.temp2Slider(self.tempCorrection)))
        self.sliderTint.setValue(round(self.tint2Slider(self.tintCorrection)))
        self.sliderExp.setValue(self.exp2Slider(self.expCorrection))
        self.sliderHigh.setValue(self.expCorrection)
        self.sliderCont.setValue(self.cont2Slider(self.contCorrection))
        self.sliderBrightness.setValue(self.br2Slider(self.brCorrection))
        #self.sliderNoise.setValue(self.noise2Slider(self.noiseCorrection))
        self.sliderSat.setValue(self.sat2Slider(self.satCorrection))
        self.dataChanged.connect(self.updateLayer)
        self.dataChanged.emit(True)

    def writeToStream(self, outStream):
        layer = self.layer
        outStream.writeQString(layer.actionName)
        outStream.writeQString(layer.name)
        outStream.writeQString(self.listWidget1.selectedItems()[0].text())
        outStream.writeInt32(self.sliderExp.value())
        return outStream

    def readFromStream(self, inStream):
        actionName = inStream.readQString()
        name = inStream.readQString()
        sel = inStream.readQString()
        temp = inStream.readInt32()
        for r in range(self.listWidget1.count()):
            currentItem = self.listWidget1.item(r)
            if currentItem.text() == sel:
                self.listWidget.select(currentItem)
        self.sliderExp.setValue(temp)
        self.update()
        return inStream
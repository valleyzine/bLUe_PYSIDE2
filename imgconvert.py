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
from time import time

import numpy as np
from PySide2.QtGui import QImage, QColor
from PIL import Image

QImageFormats = {0:'invalid', 1:'mono', 2:'monoLSB', 3:'indexed8', 4:'RGB32', 5:'ARGB32',6:'ARGB32 Premultiplied',
                 7:'RGB16', 8:'ARGB8565 Premultiplied', 9:'RGB666',10:'ARGB6666 Premultiplied', 11:'RGB555', 12:'ARGB8555 Premultiplied',
                 13: 'RGB888', 14:'RGB444', 15:'ARGB4444 Premultiplied'}

def ndarrayToQImage(ndimg, format=QImage.Format_ARGB32):
    """
    Convert a 3D numpy ndarray to a QImage. No sanity check is
    done concerning the compatibility of the ndarray shape and
    the QImage format. Although the doc is unclear, it seems that the
    buffer is copied when needed.
    @param ndimg: The ndarray to be converted
    @type ndimg: ndarray
    @param format: The QImage format (default ARGB32)
    @tyep format:
    @return: The converted image
    @rtype: QImage
    """
    if ndimg.ndim != 3 or ndimg.dtype != 'uint8':
        raise ValueError("ndarray2QImage : array must be 3D with dtype=uint8, found ndim=%d, dtype=%s" %(ndimg.ndim, ndimg.dtype))

    bytePerLine = ndimg.shape[1] * ndimg.shape[2]
    if len(np.ravel(ndimg).data)!=ndimg.shape[0]*bytePerLine :  # TODO added ravel 5/11/17 needed by vImage.resize
        raise ValueError("ndarrayToQImage : conversion error")
    # build QImage from buffer
    qimg = QImage(ndimg.data, ndimg.shape[1], ndimg.shape[0], bytePerLine, format)
    if qimg.format() == QImage.Format_Invalid:
        raise ValueError("ndarrayToQImage : wrong conversion")
    return qimg

def QImageBuffer(qimg):
    """
    Returns the QImage buffer as a numpy ndarray with dtype uint8. The size of the
    3rd axis (raw pixels) depends on the image type. Pixels are in
    BGRA order (little endian arch. (intel)) or ARGB (big  endian arch.)
    Format 1 bit per pixel is not supported.
    Performance : 20 ms for a 15 Mpx image.
    @param qimg: QImage
    @return: The buffer array
    @rtype: numpy ndarray, shape = (h,w, bytes_per_pixel), dtype = uint8
    """
    # pixel depth
    bpp = qimg.depth()
    if bpp == 1:
        raise ValueError("QImageBuffer : unsupported image format 1 bit per pixel")
    # Bytes per pixel
    Bpp = bpp // 8
    # Get image buffer
    # Calling bits() performs a deep copy of the buffer,
    # suppressing dependencies due to implicit data sharing.
    # To avoid deep copy use constBits() instead,
    # Note that constBits returns a read-only buffer.
    ptr = qimg.bits()  # type memoryview, items are bytes : ptr.itemsize = 1
    #convert buffer to ndarray and reshape
    h,w = qimg.height(), qimg.width()
    return np.asarray(ptr, dtype=np.uint8).reshape(h, w, Bpp)  # specifying dtype may prevent copy of data

def PilImageToQImage(pilimg) :
    """
    Convert a PIL image to a QImage
    @param pilimg: The PIL image, mode RGB
    @type pilimg: PIL image
    @return: QImage object, format QImage.Format_ARGB32
    @rtype: PySide.QtGui.QImage
    """
    w, h = pilimg.width, pilimg.height
    mode = pilimg.mode
    if mode != 'RGB':
        raise ValueError("PilImageToQImage : wrong mode : %s" % mode)
    # get data buffer (type bytes)
    data = pilimg.tobytes('raw', mode)
    if len(data) != w * h * 3:
        raise ValueError("PilImageToQImage : incorrect buffer length : %d, should be %d" % (len(data), w * h * 3))
    qimFormat = QImage.Format_ARGB32
    qimg = QImage(w,h, qimFormat)
    qimg.fill(QColor(0,0,0,255))
    buf = np.fromstring(data, dtype=np.uint8)
    buf = buf.reshape((h,w,3))
    qimgBuf = QImageBuffer(qimg)
    qimgBuf[:,:,:3][:,:,::-1] = buf
    return qimg

def QImageToPilImage(qimg) :
    """
    Convert a QImage to a PIL image
    @param qimg: The Qimage
    @return: PIL image  object, mode RGB
    """
    a = QImageBuffer(qimg)

    if (qimg.format() == QImage.Format_ARGB32) or (qimg.format() == QImage.Format_RGB32):
        # convert pixels from BGRA or BGRX to RGB
        a = a[:,:,:3][:,:,::-1]
        a = np.ascontiguousarray(a)
    else :
        raise ValueError("QImageToPilImage : unrecognized format : %s" %qimg.Format())
    w, h = qimg.width(), qimg.height()
    #return Image.frombytes('RGB', (w,h), a.data) a.data is memorytview (python 3)
    return Image.frombytes('RGB', (w,h), a.tobytes())
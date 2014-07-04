#!/usr/bin/env python
# -*- coding: utf-8 -*-
from os.path import join, getmtime, dirname, basename, isfile
import os
import logging
import zlib
import errno
import subprocess

from DNG import DNG

THUMBDIR = "/tmp/.previewcache"
FNULL = open(os.devnull, 'w')  # Se usa para redirigir a /dev/null


def set_thumbdir(thumbdir):
    global THUMBDIR
    THUMBDIR = thumbdir


def get_thumbdir():
    return THUMBDIR


def get_crc(path):
    return "{0:x}".format(zlib.crc32(path.encode('utf-8')) & 0xffffffff)


def get_preview(origpath, thumbnail=False):
    suffix = '-tn' if thumbnail else ''
    preview = join(THUMBDIR, dirname(origpath)[1:], basename(origpath)+suffix)

    # Comprobar si está construido
    exists = isfile(preview)
    logging.debug(
        "Preview %s from %s, exists %s" % (preview, origpath, exists))
    if exists \
       and getmtime(preview) >= getmtime(origpath):
        return preview
    return build_preview(origpath, preview, thumbnail)


def build_preview(origpath, preview, thumbnail):

    try:
        os.makedirs(dirname(preview))
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

    with open(preview, "w") as out, DNG(origpath) as dng:
        try:
            if thumbnail:
                out.write(dng.read_jpeg_preview(0))  # The smallest available
            else:
                out.write(dng.read_jpeg_preview(-1))  # The largest available
            orientation = dng.Orientation
        except:
            os.unlink(preview)
            raise

        # XBMC no interpreta el exif del tif. Sacamos el JPEG embebido
        try:
            subprocess.call(
                ["exiv2", preview,
                 "-Mset Exif.Image.Orientation %s" % orientation],
                stderr=FNULL)
        except:
            logging.debug("Unable to set Orientation information")

        logging.debug("Built %s preview" % preview)
        return preview

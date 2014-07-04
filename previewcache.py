#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os.path
import logging
import zlib
import errno
import subprocess

import DNG

THUMBDIR = "/tmp/.previewcache"


def set_thumbdir(thumbdir):
    global THUMBDIR
    THUMBDIR = thumbdir


def get_thumbdir():
    return THUMBDIR


def get_preview(origpath):
    crc = "{0:x}".format(zlib.crc32(origpath.encode('utf-8')) & 0xffffffff)
    preview = THUMBDIR+"/"+crc[0]+"/"+crc

    # Comprobar si está construido
    exists = os.path.isfile(preview)
    logging.debug(
        "Preview %s from %s, exists %s" % (preview, origpath, exists))
    if exists \
       and os.path.getmtime(preview) >= os.path.getmtime(origpath):
        return preview
    return build_preview(origpath, preview)


def build_preview(self, origpath, preview):

    try:
        os.makedirs(os.path.dirname(preview))
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise

    with open(preview, "w") as out, DNG(origpath) as dng:
        try:
            jpg = dng.get_jpeg_previews()[-1]
            dng.seek(jpg.StripOffsets)
            out.write(dng.read(jpg.StripByteCounts))
            orientation = dng.get_first_image().Orientation
        except:
            os.unlink(preview)
            raise

        # XBMC no interpreta el exif del tif. Sacamos el JPEG embebido
        try:
            subprocess.call(
                ["exiv2", preview,
                 "-Mset Exif.Image.Orientation %s" % orientation],
                stderr=self.FNULL)
        except:
            logging.debug("Unable to set Orientation information")

        logging.debug("Built %s preview" % preview)
        return preview

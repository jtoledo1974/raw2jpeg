#!/usr/bin/env python
# -*- coding: utf-8 -*-
from os.path import join, getmtime, dirname, basename, isdir, isfile, splitext
import os
import zlib
import errno
import subprocess
import json
import tempfile

from DNG import DNG, JPG, logging

PREVIEWDIR = "/tmp/.previewcache"
FNULL = open(os.devnull, 'w')  # Se usa para redirigir a /dev/null


class Orientations():
    def __init__(self):
        self.o = {}
        filename = join(get_thumbdir(), "orientations.txt")
        try:
            self.o_file = open(filename, "r+")
            self.o = json.loads(self.o_file.read())
        except:
            try:
                self.o_file = open(filename, "w")
            except:
                logging.warning(
                    "Error trying to open orientation file %s for writing"
                    % filename)

    def _save(self):
        self.o_file.seek(0)
        self.o_file.truncate()
        self.o_file.write(json.dumps(self.o))
        self.o_file.flush()

    def set(self, path, orientation):
        logging.debug("Setting orientation %d for %s" % (orientation, path))
        self.o[path] = orientation
        self._save()

    def get(self, path):
        try:
            return self.o[path]
        except:
            logging.warning("Orientation not found for %s" % path)
            return 1


def set_thumbdir(thumbdir):
    global PREVIEWDIR
    PREVIEWDIR = thumbdir
    try:
        tempfile.TemporaryFile(dir=thumbdir)
    except:
        os.makedirs(thumbdir)
    global orientations
    orientations = Orientations()


def get_thumbdir():
    return PREVIEWDIR

orientations = None
set_thumbdir(PREVIEWDIR)


def get_crc(path):
    return "{0:x}".format(zlib.crc32(path.encode('utf-8')) & 0xffffffff)


def get_preview(origpath, thumbnail=False, return_orientation=False):
    # TODO when the rest is working go back to using crcs as the filename
    p_type = 'thumbnails' if thumbnail else 'previews'
    preview = join(
        PREVIEWDIR, p_type, dirname(origpath)[1:], basename(origpath)+'.jpg')

    # Comprobar si está construido
    exists = isfile(preview)
    logging.debug(
        "Preview %s from %s, exists %s" % (preview, origpath, exists))

    if exists and getmtime(preview) >= getmtime(origpath):
        if not return_orientation:
            return preview
        else:
            return (preview, orientations.get(preview))

    (preview, orientation) = build_preview(origpath, preview, thumbnail)
    orientations.set(preview, orientation)

    if not return_orientation:
        return preview
    else:
        return (preview, orientation)


def build_preview(origpath, preview, thumbnail):
    try:
        os.makedirs(dirname(preview))
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    ext = splitext(origpath)[1].lower()
    IMG = {'.dng': DNG, '.jpg': JPG, '.jpeg': JPG}[ext]

    with open(preview, "w") as out, IMG(origpath) as img:
        try:
            if thumbnail:
                out.write(img.read_jpeg_preview(0))  # The smallest available
            else:
                out.write(img.read_jpeg_preview(-1))  # The largest available
            orientation = img.Orientation
        except:
            os.unlink(preview)
            raise

        # XBMC no interpreta el exif del tif. Sacamos el JPEG embebido

        # Commented out because for some reason it is failing in the rspbrry pi
        # try:
        #     subprocess.call(
        #         ["exiv2", preview,
        #          "-Mset Exif.Image.Orientation %s" % orientation],
        #         stderr=FNULL)
        # except:
        #     logging.debug("Unable to set Orientation information")

        logging.debug("Built %s preview" % preview)
        return (preview, orientation)

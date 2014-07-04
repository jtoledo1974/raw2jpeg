#!/usr/bin/env python
# -*- coding: utf-8 -*-
from os.path import join, getmtime, dirname, basename, isfile
import os
import logging
import zlib
import errno
import subprocess
import json

from DNG import DNG

THUMBDIR = "/tmp/.previewcache"
FNULL = open(os.devnull, 'w')  # Se usa para redirigir a /dev/null


def set_thumbdir(thumbdir):
    global THUMBDIR
    THUMBDIR = thumbdir
    global orientations
    orientations = Orientations()


def get_thumbdir():
    return THUMBDIR


class Orientations():
    def __init__(self):
        self.o = {}
        filename = join(get_thumbdir(), "orientations.txt")
        try:
            self.o_file = open(filename, "r+")
        except:
            try:
                self.o_file = open(filename, "w")
            except:
                logging.warning(
                    "Error trying to open orientation file %s for writing"
                    % filename)

        try:
            self.o = json.loads(self.o_file.read())
        except:
            logging.warning("Error loading orientations file")

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

orientations = Orientations()


def get_crc(path):
    return "{0:x}".format(zlib.crc32(path.encode('utf-8')) & 0xffffffff)


def get_preview(origpath, thumbnail=False, return_orientation=False):
    suffix = '-tn' if thumbnail else ''
    preview = join(THUMBDIR, dirname(origpath)[1:], basename(origpath)+suffix)

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
        return (preview, orientation)

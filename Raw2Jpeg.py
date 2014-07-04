#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import with_statement

import os
from os.path import join
import sys
import errno
import logging
import json

from loop import Passthrough
from fuse import FUSE, FuseOSError

from previewcache import get_thumbdir, get_preview, set_thumbdir

set_thumbdir('/srv/tmp/.raw2jpg')
# logging.basicConfig(filename="/srv/tmp/raw2jpeg.log",level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class Blacklist():
    def __init__(self):
        self.bl = {}
        try:
            self.blfile = open(get_thumbdir()+"/blacklist.txt", "r+")
        except:
            self.blfile = open(get_thumbdir()+"/blacklist.txt", "w")
        try:
            self.bl = json.loads(self.blfile.read())
        except:
            logging.warning("Error cargando blacklist")
            pass

    def _save(self):
        self.blfile.seek(0)
        self.blfile.truncate()
        self.blfile.write(json.dumps(self.bl))
        self.blfile.flush()

    def add(self, path):
        logging.debug("Blacklisting %s" % path)
        self.bl[path] = os.path.getmtime(path)
        self._save()

    def match(self, path):
        if path in self.bl and os.path.getmtime(path) == self.bl[path]:
            return True
        elif path in self.bl:
            self.bl.pop(path)
            self._save()
        return False


class Raw2Jpeg(Passthrough):

    MASK = ".maskeddng.jpg"
    FNULL = open(os.devnull, 'w')  # Se usa para redirigir a /dev/null

    # Paths that failed to create a thumbnail. Do not list them
    blacklist = Blacklist()

    # Helpers
    # =======

    def _masked(self, path):
        """Devuelve el nombre falso"""
        return path[:-4]+self.MASK if path[-4:].lower() == ".dng" else path

    def _original(self, path):
        """Devuelve el archivo original"""
        return path[:-14]+".dng" if path[-14:] == self.MASK else path

    def _ismasked(self, path):
        return path[-14:] == self.MASK

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path, uid, gid):
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        logging.debug("getattr %s %s" % (path, fh))
        # TODO olvidarnos de la subclase de loop
        res = super(Raw2Jpeg, self).getattr(self._original(path), fh)
        full_path = self._full_path(path)
        if self._ismasked(path):
            orig = self._original(full_path)
            try:
                size = getattr(os.lstat(get_preview(orig)), 'st_size')
                res['st_size'] = size
            except:
                self.blacklist.add(self._original(full_path))
        return res
        # full_path = self._full_path(path)
        # st = os.lstat(full_path)
        # return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
        #             'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path, fh):
        logging.debug("readdir %s %s" % (path, fh))
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            # logging.debug("Blacklist %s\nFiles %s" % (
            #               self.blacklist.bl, [full_path+'/'+self._masked(f)
            #                                   for f in os.listdir(full_path)]))
            ld = [self._masked(f) for f in os.listdir(full_path)
                  if not self.blacklist.match(join(full_path, f))]
            dirents.extend(ld)
        for r in dirents:
            yield r

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path, mode, dev):
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path, mode):
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key))
                    for key in ('f_bavail', 'f_bfree', 'f_blocks', 'f_bsize',
                                'f_favail', 'f_ffree', 'f_files',
                                'f_flag', 'f_frsize', 'f_namemax'))

    def unlink(self, path):
        return os.unlink(self._full_path(path))

    def symlink(self, target, name):
        return os.symlink(self._full_path(target), self._full_path(name))

    def rename(self, old, new):
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, name):
        return os.link(self._full_path(target), self._full_path(name))

    def utimens(self, path, times=None):
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path, flags):
        logging.debug("open %s %s" % (self._full_path(path), flags))
        full_path = self._full_path(path)
        if self._ismasked(full_path):
                full_path = get_preview(self._original(full_path))
        return os.open(full_path, flags)

    def create(self, path, mode, fi=None):
        full_path = self._full_path(path)
        logging.debug("create %s %s %s" % (full_path, mode, fi))
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        logging.debug("read %s %s %s %s" % (path, length, offset, fh))
        try:
            os.lseek(fh, offset, os.SEEK_SET)
        except:
            logging.warning("failed lseek")
        data = os.read(fh, length)
        return data

    def write(self, path, buf, offset, fh):
        logging.debug("write %s %s %s %s" % (path, buf, offset, fh))
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        logging.debug("truncate %s %s %s" % (path, length, fh))
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        logging.debug("flush %s %s" % (path, fh))
        return os.fsync(fh)

    def release(self, path, fh):
        logging.debug("release %s %s" % (path, fh))
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        logging.debug("fsync %s %s %s" % (path, fdatasync, fh))
        return self.flush(path, fh)


def main(mountpoint, root):
    FUSE(Raw2Jpeg(root), mountpoint, foreground=True,
         ro=True, allow_other=True)

if __name__ == '__main__':
    main(sys.argv[2], sys.argv[1])

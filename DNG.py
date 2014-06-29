#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import errno
from struct import unpack


class Logging:
    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10

    def __init__(self):
        self.level = 0

        def get_log_function(level):
            def f(string):
                if level >= self.level:
                    self.log(string)
            return f

        for levelname in ['critical', 'error', 'warning', 'info', 'debug']:
            level = Logging.__dict__[levelname.upper()]
            f = get_log_function(level)
            setattr(self, levelname, f)

    def basicConfig(self, level):
        self.level = level

    def log(self, string):
        print(string)

logging = Logging()
logging.basicConfig(level=logging.INFO)

BYTE = 1
ASCII = 2
SHORT = 2
LONG = 4


class Tag:

    SubFileType = 254
    ImageWidth = 256
    ImageLength = 257
    BitsPerSample = 258
    Compression = 259
    Photometric = 262
    StripOffsets = 273
    Orientation = 274
    SamplesPerPixel = 277
    RowsPerStrip = 278
    StripByteCounts = 279
    XResolution = 282
    YResolution = 283
    ResolutionUnit = 296
    TileWidth = 322
    TileLength = 323
    TileOffsets = 324
    TileByteCounts = 325
    SubIFD = 330

    types = {BYTE: 1, SHORT: 2, LONG: 4}

    def tag_name(self):
        try:
            return self.tag_dict[self.tag]
        except:
            return str(self.tag)

    def __init__(self, tag, tag_type, count, value):
        self.tag = tag
        self.type = tag_type
        self.count = count
        self.value = value

    def unsupported(self):
        logging.debug(
            "Unsupported type %d for tag %s" % (
                self.type, self.tag_name()))

    def read_value(self, dng):
        try:
            if self.types[self.type]*self.count <= 4:
                return
        except:
            self.unsupported()
            return

        dng.seek(self.value)
        if self.type == SHORT:
            readf = dng.read_short
        elif self.type == LONG:
            readf = dng.read_long
        else:
            self.unsupported()
            return

        if self.count == 1:
            self.value = readf()
            return

        c = self.count
        v = []
        while c:
            v.append(readf())
            c -= 1
        self.value = v
        return

    def __str__(self):
        return "Tag %s: %s" % (self.tag_name(self.tag), self.value)

Tag.tag_dict = {number: tag_name for tag_name, number
                in Tag.__dict__.iteritems()
                if type(number) == int}


class IFD:
    def __init__(self, dng, offset):
        dng.seek(offset)
        self.offset = offset
        n_tags = dng.read_short()
        entries = []
        self.entries = []

        while n_tags:
            tag = dng.read_short()
            type = dng.read_short()
            count = dng.read_long()
            value = dng.read_long()
            entries.append(Tag(tag, type, count, value))
            n_tags -= 1

        self.next = dng.read_long()

        for entry in entries:
            tag_name = entry.tag_name()
            entry.read_value(dng)
            self.__dict__[tag_name] = entry.value
            self.entries.append(tag_name)

    def __str__(self):
        w = self.ImageWidth
        l = self.ImageLength
        t = self.SubFileType
        c = self.Compression
        try:
            s = self.StripByteCounts
        except:
            if type(self.TileByteCounts) == int:
                s = self.TileByteCounts
            else:
                # import pdb; pdb.set_trace()
                s = sum(self.TileByteCounts)
        return "%dx%d, Type %d, compr: %d, size: %d" % (w, l, t, c, s)

    def dump(self):
        res = ""
        for entry in self.entries:
            res += "%s: %s\n" % (entry, self.__dict__[entry])
        return res


class DNG:
    def wrong_format(self):
        logging.error("Invalid file format")
        sys.exit(errno.EPERM)

    def set_endian(self, endian):
        if endian == 'II':
            endianc = '<'
        elif endian == 'MM':
            endianc = '>'
        else:
            self.wrong_format()

        self.longf = endianc + 'L'
        self.shortf = endianc + 'H'

    def seek(self, offset):
        self.f.seek(offset)

    def read_short(self):
        # buf = self.f.read(2)
        # print "Hex buf %s" % buf.encode('hex')
        # n = unpack(self.shortf, buf)
        # print "Unpacked n %d" % n
        # return n[0]
        return unpack(self.shortf, self.f.read(2))[0]

    def read_long(self):
        # buf = self.f.read(4)
        # print "Hex buf %s" % buf.encode('hex')
        # n = unpack(self.longf, buf)
        # print "Unpacked n %d" % n
        # return n[0]
        return unpack(self.longf, self.f.read(4))[0]

    def open(self, path):
        self.f = open(path, "rb")

        endian = self.f.read(2)
        self.set_endian(endian)
        magic = self.read_short()
        if magic != 42:
            print magic
            self.wrong_format()

        self.first_ifdo = self.read_long()
        return self

    def get_images(self):
        res = []
        ifdo_list = [self.first_ifdo]
        while len(ifdo_list):

            ifdo = ifdo_list.pop(0)
            if not ifdo:
                break
            ifd = IFD(self, ifdo)
            res.append(ifd)
            try:
                ifdo_list = ifd.SubIFD + ifdo_list
            except:
                pass
            ifd.next and ifdo_list.append(ifd.next)


if __name__ == '__main__':
    from pprint import pprint

    dng = DNG().open("test2.dng")
    # entries, next_ifdo = dng.read_directory()
    # pprint({k: str(v) for k, v in entries.iteritems()})
    # print next_ifdo
    dng.list_images()

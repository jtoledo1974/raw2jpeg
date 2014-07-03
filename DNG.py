#!/usr/bin/env python
# -*- coding: utf-8 -*-
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


class Tag:

    BYTE = 1
    ASCII = 2
    SHORT = 3
    LONG = 4
    RATIONAL = 5

    SubFileType = 254
    ImageWidth = 256
    ImageLength = 257
    BitsPerSample = 258
    Compression = 259
    Photometric = 262
    Make = 271
    Model = 272
    StripOffsets = 273
    Orientation = 274
    SamplesPerPixel = 277
    RowsPerStrip = 278
    StripByteCounts = 279
    XResolution = 282
    YResolution = 283
    ResolutionUnit = 296
    DateTime = 306
    TileWidth = 322
    TileLength = 323
    TileOffsets = 324
    TileByteCounts = 325
    SubIFD = 330
    JPEGInterchangeFormat = 513
    JPEGInterchangeFormatLength = 514
    ExifTag = 34665

    type_lengths = {BYTE: 1, ASCII: 1, SHORT: 2, LONG: 4, RATIONAL: 8}

    def tag_name(self):
        try:
            return self.tag_dict[self.tag]
        except:
            return str(self.tag)

    def __init__(self, tag, tag_type, count, value, file):
        self.tag = tag
        self.type = tag_type
        self.count = count
        self.value = value
        self.file = file
        self.read_function = {
            self.BYTE: file.read_byte,
            self.ASCII: file.read_ascii,
            self.SHORT: file.read_short,
            self.LONG: file.read_long,
            self.RATIONAL: file.read_rational
        }

    def unsupported(self, c=0):
        logging.debug(
            "Unsupported type %d for tag %s" % (
                self.type, self.tag_name()))
        raise NotImplementedError

    def read_value(self):
        if self.type_lengths[self.type]*self.count <= 4:
            return

        self.file.seek(self.value)

        readf = self.read_function[self.type]

        try:
            if self.count == 1 or self.type == self.ASCII:
                self.value = readf(self.count)
                return

            c = self.count
            v = []
            while c:
                v.append(readf(self.count))
                c -= 1
            self.value = v
        except NotImplementedError:
            return

    def __str__(self):
        return "Tag %s: %s" % (self.tag_name(self.tag), self.value)

Tag.tag_dict = {number: tag_name for tag_name, number
                in Tag.__dict__.iteritems()
                if type(number) == int}


class IFD(object):
    def __init__(self, dng, offset):
        dng.seek(offset)
        self.offset = offset
        self.dng = dng
        n_tags = dng.read_short()
        self.entries = {}
        self.entry_list = []

        buf = dng.read(n_tags*12)
        shortf = dng.shortf
        longf = dng.longf
        n = 0
        while n < n_tags:
            o = n*12
            tag = unpack(shortf, buf[o:o+2])[0]
            type = unpack(shortf, buf[o+2:o+4])[0]
            count = unpack(longf, buf[o+4:o+8])[0]
            value = unpack(longf, buf[o+8:o+12])[0]
            tag_obj = Tag(tag, type, count, value, dng)
            tag_obj.value_is_checked = False
            tag_name = tag_obj.tag_name()
            self.entries[tag_name] = tag_obj
            self.entry_list.append(tag_name)
            n += 1

        self.next = dng.read_long()

    def __getattr__(self, attr):
        try:
            return self.__dict__[attr]
        except:
            pass
        entry = self.entries[attr]
        if entry.value_is_checked is True:
            return entry.value
        else:
            try:
                entry.read_value()
                entry.value_is_checked = True
            except:
                logging.debug("Unable to read value for tag %s" % attr)
                raise NotImplementedError
            return entry.value

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
                s = sum(self.TileByteCounts)
        return "%dx%d, Type %d, compr: %d, size: %d" % (w, l, t, c, s)

    def dump(self):
        res = ""
        for entry in self.entry_list:
            try:
                res += "%s: %s\n" % (entry, str(getattr(self, entry))[:60])
            except NotImplementedError:
                pass
        return res


class DNG:
    def wrong_format(self):
        logging.error("Invalid file format in file %s" % self.f.name)
        raise IOError

    def set_endian(self, endian):
        if endian == 'II':
            endianc = '<'
        elif endian == 'MM':
            endianc = '>'
        else:
            self.wrong_format()

        self.longf = endianc + 'L'
        self.shortf = endianc + 'H'

    def fileno(self):
        return self.f.fileno()

    def seek(self, offset):
        self.f.seek(self.offset + offset)

    def read(self, count):
        return self.f.read(count)

    def read_byte(self, c=0):
        return ord(self.f.read(1))

    def read_ascii(self, count):
        return self.f.read(count)[:-1]

    def read_short(self, c=0):
        return unpack(self.shortf, self.f.read(2))[0]

    def read_long(self, c=0):
        return unpack(self.longf, self.f.read(4))[0]

    def read_rational(self, c=0):
        return float(unpack(self.longf, self.f.read(4))[0]) \
            / unpack(self.longf, self.f.read(4))[0]

    def __init__(self, path='', offset=0, exif=False):
        self.exif = exif  # If True we are opening the exif IFD from a JPEG

        if path:
            self.open(path, offset)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def open(self, source, offset=0):
        try:
            self.close()
        except:
            pass

        self.f = open(source, "rb")
        self.offset = offset
        self.f.seek(offset)

        endian = self.f.read(2)
        self.set_endian(endian)
        magic = self.read_short()
        if magic != 42:
            print magic
            self.wrong_format()

        self.first_ifdo = self.read_long()
        return self

    def close(self):
        self.f.close()
        del self.f

    def __del__(self):
        try:
            self.close()
        except:
            pass

    def get_image(self, offset):
        return IFD(self, offset)

    def get_first_image(self):
        return self.get_image(self.first_ifdo)

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
        try:
            res.sort(cmp=lambda x, y: cmp(x.ImageWidth*x.ImageLength,
                                          y.ImageWidth*y.ImageLength))
        except KeyError:
            pass  # Exif images don't seem to have it

        return res

    def get_previews(self):
        return [i for i in self.get_images()
                if self.exif or i.SubFileType == 1]

    def get_jpeg_previews(self):
        return [i for i in self.get_previews()
                if hasattr(i, 'Compression') and i.Compression in (7, 6)]

    def read_jpeg_preview(self, index=0):
        try:
            jpg = self.get_jpeg_previews()[index]
            if hasattr(jpg, 'StripOffsets') and hasattr(jpg, 'StripByteCounts'):
                self.seek(jpg.StripOffsets)
                return self.read(jpg.StripByteCounts)
            elif hasattr(jpg, 'JPEGInterchangeFormat') \
                    and hasattr(jpg, 'JPEGInterchangeFormatLength'):
                self.seek(jpg.JPEGInterchangeFormat)
                return self.read(jpg.JPEGInterchangeFormatLength)
        except KeyError:
            logging.error("No jpeg preview in %s" % self.f.name)
            raise IOError


def JPG(path):
    return DNG(path, offset=12, exif=True)

if __name__ == '__main__':
    # from pprint import pprint

    jpg = JPG("test2.jpg")
    for p in jpg.get_jpeg_previews():
        print p.offset
        print p.dump()
    print [str(j.dump()) for j in jpg.get_jpeg_previews()]
    f = open("thumb.jpg", "w+b")
    f.write(jpg.read_jpeg_preview())
    # with DNG("test2.dng") as dng:
    #     print "\n".join([str(i) for i in dng.get_jpeg_previews()])
    #     # print dng.get_jpeg_previews()[-1].StripByteCounts
    print "hola"

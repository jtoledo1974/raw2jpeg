#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import errno
import logging
from struct import unpack


logging.basicConfig(level=logging.ERROR)

BYTE = 1
ASCII = 2
SHORT = 2
LONG = 4


class Tag:

    SubFileType = 254
    ImageWidth = 256
    ImageLength = 257
    Compression = 259
    Orientation = 274
    SubIFD = 330

    types = {BYTE: 1, SHORT: 2, LONG: 4}

    def tag_name(self, tag_number):
        if not hasattr(Tag, 'tag_names'):
            Tag.tag_dict = {number: tag_name for tag_name, number
                            in Tag.__dict__.iteritems()
                            if type(number) == int}
        if tag_number not in Tag.tag_dict:
            return str(tag_number)
        else:
            return Tag.tag_dict[tag_number]

    def __init__(self, tag, type, count, value):
        self.tag = tag
        self.type = type
        self.count = count
        self.value = value

    def unsupported(self):
        logging.warning(
            "Unsupported type %d for tag %s" % (
                self.type, self.tag_name(self.tag)))

    def read_value(self, dng):
        # if self.tag == 330:
        #     import pdb; pdb.set_trace()

        if self.type not in self.types:
            self.unsupported()
            return
        if self.types[self.type]*self.count <= 4:
            return

        dng.f.seek(self.value)
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

    def read_directory(self):
        n_tags = self.read_short()
        entries = {}
        while n_tags:
            tag = self.read_short()
            type = self.read_short()
            count = self.read_long()
            value = self.read_long()
            entries[tag] = Tag(tag, type, count, value)
            n_tags -= 1
        for entry in entries.values():
            entry.read_value(self)

        return entries

    def list_images(self):
        self.f.seek(self.first_ifdo)
        entries = self.read_directory()


if __name__ == '__main__':
    from pprint import pprint

    dng = DNG().open("test1.dng")
    pprint({k: str(v) for k, v in dng.read_directory().iteritems()})

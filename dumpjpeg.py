import os
import mmap

tifpreview="t.tif"
tp=os.open(tifpreview, os.O_RDONLY)
mm=mmap.mmap(tp,0,prot=mmap.PROT_READ)
last=0
index=0

while True:
    preview = "t-%d.jpg" % index
    start = mm.find("\xff\xd8",last)
    end = mm.find("\xff\xd9", last)+2
    last = end - 1
    if start < 0 or end < 0:
        break
    open(preview,"wb").write(mm[start:end])
    index +=1

mm.close()
os.close(tp)
                                                            
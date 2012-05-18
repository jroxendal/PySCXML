import os, glob, shutil

try:
    os.mkdir("broken")
except:
    pass




for file in glob.glob("*xml"):
    try:
        txt = open(file).read()
        if "conf:" in txt:
            print "broken: " + file
            shutil.move(file, "broken/" + file)
            sub = file.split(".")[0] + "sub1" + ".xml"
            shutil.move(sub, "broken/" + sub)
    except:
        pass

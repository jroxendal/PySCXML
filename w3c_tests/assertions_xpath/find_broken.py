import os, glob, shutil, sys



files = '''test192.scxml
test207.scxml
test220.scxml
test226.scxml
test229.scxml
test235.scxml
test236.scxml
test239.scxml
test242.scxml
test243.scxml
test247.scxml
test250.scxml
test267.scxml
test268.scxml
test269.scxml
test276.scxml
test318.scxml
test324.scxml
test347.scxml
test360.scxml
test411.scxml
test413.scxml
test426.scxml
test456.scxml
test461.scxml
test467.scxml
test468.scxml
test469.scxml
test470.scxml
test473.scxml
test474.scxml
test475.scxml
test476.scxml
test477.scxml
test478.scxml
test480.scxml
test481.scxml
test483.scxml
test502.scxml
test521.scxml
test537.scxml
test541.scxml
test545.scxml
test547.scxml'''.splitlines()

for file in files:
    shutil.move(file, "failed/" + file)
    try:
        sub = file.split(".")[0] + "sub1" + ".scxml"
        shutil.move(sub, "failed/" + sub)
    except:
        pass









sys.exit()

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
            sub = file.split(".")[0] + "sub1" + ".scxml"
            shutil.move(sub, "broken/" + sub)
    except:
        pass

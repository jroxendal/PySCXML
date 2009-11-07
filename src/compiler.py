from xml.dom import Node
import re


def str_elem(id,type): return "targets['" + id + "'] = " + type + "()\n"

def str_id(id): return "targets['" + id + "'].id = '" + id + "'\n"

def str_parent(id,parentid): return "targets['" + id + "'].parent = targets['" + parentid + "']\n"

def str_n(id,n): return "targets['" + id + "'].n = " + str(n) + "\n"

def str_app_trans(id): return "targets['" + id + "'].transition.append(transition)\n"

def get_sid(node):
    if node.getAttribute('id') != '':
        return node.getAttribute('id')
    else:
        id = gen_id('$')
        node.setAttribute('id',id)
        return id
# not used at the moment
def str_namelist(node):
    ss = node.getAttribute('target').split(" ")
    ss = [s.encode('utf-8') for s in ss if s != ''] 
    return ss        

def gen_event(node):
    if node.getAttribute('event') != '':
        return "transition.event = '" + node.getAttribute('event').strip() +"'\n"
    else:
        return ""

def gen_cond(node):
    if node.getAttribute('cond') != '':
        return "transition.cond = lambda dm: " + node.getAttribute('cond') +"\n"
    else:
        return ""
          
def gen_target(node):
    if node.getAttribute('target') != '':
        ss = node.getAttribute('target').split(" ")
        ss = [str(s) for s in ss if s != ''] 
        return "transition.target = " + str(ss) + "\n"
    else:
        return ""
    
counter = 0
def gen_id(base): 
    global counter
    counter = counter + 1
    return base + str(counter)

def gen_execontent(type,node):
    src = ""
    if node.childNodes != []:
        src += "def f():\n"
        for nd in node.childNodes:
            if nd.nodeName == "log":
                src += "\tprint 'Log: ' + str(" + str(nd.getAttribute('expr')) + ")\n"
            elif nd.nodeName == "assign":
                src += "\t" + nd.getAttribute('name') + " = " + str(nd.getAttribute('expr')) + "\n"
            elif nd.nodeName == "raise":
                src += "\tsend('" + nd.getAttribute('event') + "'," + str(nd.getAttribute('delay')) + ")\n"
            elif nd.nodeName == "script":
                src += "\t" + re.sub("(\t| )+\n(\t| )+","\n\t",nd.childNodes[0].nodeValue.strip()) + "\n"
        src += type + ".exe = f\n"
    return src


from xml.dom import minidom
doc = minidom.parse('pingpong.xml')
src = """f = None
transition = None
onentry = None
onexit = None
targets = {}
targets['root'] = State()
targets["root"].parent = None
targets['root'].id = 'root'
"""

n = 0
for node in doc_order_iter(doc):
    if node.nodeName == "scxml":    
        node.setAttribute('id','main')
        src += str_elem('main','State')
        src += str_id('main')
        src += str_n('main',n)
        src += str_parent('main','root')
    elif node.nodeName == "state":
        sid = get_sid(node)
        pid = node.parentNode.getAttribute('id')
        src += str_elem(sid,'State')
        src += str_id(sid)
        src += str_n(sid,n)
        src += str_parent(sid,pid)
        src += "targets['" + pid + "'].state.append(targets['" + sid + "'])\n"
    elif node.nodeName == "parallel":
        sid = get_sid(node)
        pid = node.parentNode.getAttribute('id')
        src += str_elem(sid,'Parallel')
        src += str_id(sid)
        src += str_n(sid,n)
        src += str_parent(sid,pid)
        src += "targets['" + pid + "'].parallel.append(targets['" + sid + "'])\n"
    elif node.nodeName == "final":
        sid = get_sid(node)
        pid = node.parentNode.getAttribute('id')
        src += str_elem(sid,'Final')
        src += str_id(sid)
        src += str_n(sid,n)
        src += str_parent(sid,pid)
        src += "targets['" + pid + "'].final.append(targets['" + sid + "'])\n"
    elif node.nodeName == "transition":
        src += "transition = Transition()\n"
        src += "transition.source = targets['" + node.parentNode.getAttribute('id') +"']\n"
        src += gen_event(node)
        src += gen_cond(node)
        src += gen_target(node)
        src += str_app_trans(node.parentNode.getAttribute('id'))
        src += gen_execontent("transition",node)
    elif node.nodeName == "onentry":
        src += "onentry = Onentry()\n"
        src += gen_execontent("onentry",node)
        src += "targets['" + node.parentNode.getAttribute('id') +"'].onentry.append(onentry);\n"
    elif node.nodeName == "onexit":
        src += "onexit = Onexit()\n"
        src += gen_execontent("onexit",node)
        src += "targets['" + node.parentNode.getAttribute('id') +"'].onexit.append(onexit);\n"
    elif node.nodeName == "data":
        src += "dm['" + node.getAttribute('id') + "'] = " + node.getAttribute('expr') + "\n"
    elif node.nodeName == "script" and node.parentNode.nodeName in ["state","scxml","parallel"]:
        src += node.childNodes[0].nodeValue.strip() + "\n"
    n=n+1

src += """targets['root'].state.append(targets['main'])
del(f)
del(transition)
del(onentry)
del(onexit)
"""
#print src
from Cheetah.Template import Template

tmpl = """\
f = None
transition = None
onentry = None
onexit = None
targets = {}
targets['root'] = State()
targets["root"].parent = None
targets['root'].id = 'root'
#set n = 0
#for $node in $nodeList

#if node.nodeName == "scxml"
targets['main'] = State()
targets['main'].id = 'main'
targets['main'].n = 0
targets['main'].parent = targets['root']

#elif node.nodeName == "parallel"
#set $sid = $get_sid(node)
#set $pid = node.parentNode.getAttribute('id')
targets['$sid'] = Parallel()
targets['$sid'].id = '$sid'
targets['$sid'].n = $n
targets['$sid'].parent = targets['$pid']
targets['$pid'].parallel.append(targets['$sid'])
#end if
#set $n = $n + 1
#end for

targets['Pinger'] = State()
targets['Pinger'].id = 'Pinger'
targets['Pinger'].n = 2
targets['Pinger'].parent = targets['init']
targets['init'].state.append(targets['Pinger'])
onentry = Onentry()
def f():
    send('ping',)
onentry.exe = f
targets['Pinger'].onentry.append(onentry);
transition = Transition()
transition.source = targets['Pinger']
transition.event = 'pong'
targets['Pinger'].transition.append(transition)
def f():
    send('ping',1)
transition.exe = f
targets['Ponger'] = State()
targets['Ponger'].id = 'Ponger'
targets['Ponger'].n = 7
targets['Ponger'].parent = targets['init']
targets['init'].state.append(targets['Ponger'])
transition = Transition()
transition.source = targets['Ponger']
transition.event = 'ping'
targets['Ponger'].transition.append(transition)
def f():
    send('pong',1)
transition.exe = f
targets['root'].state.append(targets['main'])
del(f)
del(transition)
del(onentry)
del(onexit)
"""

def templateIdea():
    t = Template(tmpl, searchList=[{"nodeList" : doc_order_iter(doc), "get_sid" : get_sid}])
    print t

templateIdea()




import json, sys, os
OI=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "object_info.json")))
def convert(path, overrides=None):
    w=json.load(open(path)); nodes={n["id"]:n for n in w["nodes"]}
    links={l[0]:l for l in w["links"]}   # id, from_node, from_slot, to_node, to_slot, type
    api={}
    SKIP={"Note","MarkdownNote","Reroute"}
    def resolve(nid, slot):
        n=nodes[nid]
        if n["type"]=="Reroute":
            l=links[n["inputs"][0]["link"]]; return resolve(l[1],l[2])
        if n["type"]=="PrimitiveNode": return None
        return [str(nid),slot]
    for nid,n in nodes.items():
        t=n["type"]
        if t in SKIP or t not in OI: 
            if t not in SKIP: print("UNKNOWN",t)
            continue
        info=OI[t]; inp={}
        order=[]
        for sec in ("required","optional"):
            for k,v in (info["input"].get(sec) or {}).items(): order.append((k,v))
        linked={i["name"]:i for i in n.get("inputs",[]) if i.get("link") is not None}
        wv=list(n.get("widgets_values") or []); wi=0
        for k,v in order:
            typ=v[0]; opts=v[1] if len(v)>1 else {}
            is_widget = isinstance(typ,list) or typ in ("INT","FLOAT","STRING","BOOLEAN","COMBO")
            if k in linked:
                l=links[linked[k]["link"]]; r=resolve(l[1],l[2])
                if r: inp[k]=r
                if is_widget and (linked[k].get("widget") is not None) and wi<len(wv): wi+=1   # widget converted to input still has a value slot
                continue
            if is_widget:
                if wi<len(wv):
                    inp[k]=wv[wi]; wi+=1
                    if opts.get("control_after_generate") and wi<len(wv) and isinstance(wv[wi],str): wi+=1
        api[str(nid)]={"class_type":t,"inputs":inp}
    if overrides:
        for (nid,k),v in overrides.items(): api[str(nid)]["inputs"][k]=v
    return api
if __name__=="__main__":
    a=convert(sys.argv[1]); json.dump(a,open(sys.argv[2],"w"),indent=1); print(len(a),"nodes")

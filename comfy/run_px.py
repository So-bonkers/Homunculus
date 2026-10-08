import os, json, sys, time, threading, subprocess, requests, uuid
from pathlib import Path
PIXAL_MODEL="pixal3d_bf16.safetensors"   # full precision: better and ~2x faster than int8 on ROCm (int8 is dequantised every step)
API="http://127.0.0.1:8188"; CARD="/sys/class/drm/card1/device"
used=lambda:int(Path(f"{CARD}/mem_info_vram_used").read_text())/1024**3
def build_single(image, prefix, seed=42):
    a=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_single.json")))
    keep=["122","193","192","248","303","312","55","56","242","15","298","319","199","125","108","87","3","119","117","91","279","126","18","94","23","92"]
    g={k:json.loads(json.dumps(a[k])) for k in keep}
    g["248"]["inputs"]["switch"]=True
    g["319"]["inputs"]["unet_name"]=PIXAL_MODEL
    g["122"]["inputs"]["image"]=image
    for k in ("3","18","23"): g[k]["inputs"]["seed"]=seed
    for k in ("56","298"): g[k]["inputs"]["image"]=["312",0]
    for k in ("199","279"): g[k]["inputs"]["model"]=["319",0]
    g["3"]["inputs"]["positive"]=["298",0]; g["3"]["inputs"]["negative"]=["298",1]
    g["91"]["inputs"]["positive"]=["298",0]; g["91"]["inputs"]["negative"]=["298",1]
    g["312"]["inputs"]["background"]="#000000"; g["56"]["inputs"]["refine_steps"]=0
    g["900"]={"class_type":"SaveGLB","inputs":{"mesh":["92",0],"filename_prefix":prefix}}
    return g
def run(graph, timeout=3600, limit=22.5):
    st={"peak":0.0,"stop":False}
    def w():
        while not st["stop"]:
            u=used(); st["peak"]=max(st["peak"],u)
            if u>limit:
                print(f"!! VRAM {u:.1f} GB > {limit}; interrupting",flush=True); requests.post(API+"/interrupt"); subprocess.run(["systemctl","--user","stop","comfy-px"]); return
            time.sleep(0.5)
    threading.Thread(target=w,daemon=True).start()
    r=requests.post(API+"/prompt",json={"prompt":graph,"client_id":str(uuid.uuid4())}); 
    if r.status_code!=200: print(r.text[:3000]); st["stop"]=True; return None
    pid=r.json()["prompt_id"]; t0=time.time(); print("queued",pid,flush=True)
    while time.time()-t0<timeout:
        h=requests.get(f"{API}/history/{pid}").json()
        if pid in h:
            st["stop"]=True; res=h[pid]; print("status",res["status"]["status_str"],"time",round(time.time()-t0),"s peak VRAM",round(st["peak"],1),"GB",flush=True)
            if res["status"]["status_str"]!="success": print(json.dumps(res["status"]["messages"][-3:])[:3000])
            return res
        time.sleep(3)
    st["stop"]=True; print("timeout"); return None
if __name__=="__main__":
    g=build_single(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv)>3 else 42); run(g)

def build_tex(image, prefix, seed=42, remesh=1024, faces=200000, tex=4096, texture=True, base_color=0x808080, upres=None):
    g=build_single(image, prefix, seed); a=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_single.json")))
    if upres: g["94"]["inputs"]["target_resolution"]=int(upres)      # voxel resolution of the upsampled shape (1024..2048): lower = less VRAM, for parts that fill their whole picture
    del g["900"]
    for k in ("98","12","93","118","147","288","233","224","210","260","238","196","241","186"): g[k]=json.loads(json.dumps(a[k]))
    g["98"]["inputs"].update({"positive":["94",0],"negative":["94",1],"shape_latent":["23",0]})
    g["12"]["inputs"].update({"model":["319",0],"positive":["98",0],"negative":["98",1],"latent_image":["98",2],"seed":seed+1})
    g["93"]["inputs"].update({"samples":["12",0],"vae":["118",0],"shape_subdivides":["92",1]})
    g["241"]["inputs"]={"mesh":["92",0],"resolution":remesh,"sign_mode":"udf","sign_mode.qef":False,"sign_mode.drop_inverted_components":False,"sign_mode.drop_enclosed_components":False,"band":1.0,"project_back":0.0,"fix_poles":False,"smooth_iters":0,"drop_small_components":0.01,"precluster_max_verts":20000000}
    g["186"]["inputs"]={"mesh":["241",0],"target_face_count":faces,"placement_mode":"midpoint"}
    g["238"]["inputs"]={"mesh":["186",0],"crease_angle":180.0}
    g["288"]={"class_type":"PrimitiveInt","inputs":{"value":tex}}
    g["196"]["inputs"]={"mesh":["238",0],"segmenter":"pec","resolution":["288",0],"padding":1,"weld_distance":0.0002}
    g["147"]["inputs"]={"mesh":["196",0],"voxel_colors":["93",0],"texture_size":["288",0],"reference_mesh":["92",0]}
    g["233"]["inputs"]={"low_poly":["196",0],"high_poly":["241",0],"resolution":1024,"samples":64,"max_distance":0.71,"strength":1.0,"bias":0.01}
    g["224"]["inputs"]={"low_poly":["196",0],"high_poly":["241",0],"resolution":2048,"cage_distance":0.05,"ignore_backfaces":True}
    g["210"]["inputs"]={"mesh":["196",0],"base_color":["147",0],"metallic":["147",1],"roughness":["147",2],"occlusion":["233",0],"normal_map":["224",0]}
    g["260"]["inputs"]={"mesh":["210",0],"crease_angle":180.0}
    if not texture:      # no texture sampling and no colour bake: the mesh gets a flat base colour (the colours come from projected pictures later). Saves the 12-step texture sampler and the bake
        for k in ("98","12","93","118","147"): g.pop(k,None)
        g["291"]={"class_type":"EmptyImage","inputs":{"width":256,"height":256,"batch_size":1,"color":int(base_color)}}
        g["292"]={"class_type":"EmptyImage","inputs":{"width":256,"height":256,"batch_size":1,"color":0x000000}}      # metallic: none
        g["293"]={"class_type":"EmptyImage","inputs":{"width":256,"height":256,"batch_size":1,"color":0x999999}}      # roughness: 0.6
        g["210"]["inputs"].update({"base_color":["291",0],"metallic":["292",0],"roughness":["293",0]})
    g["901"]={"class_type":"SaveGLB","inputs":{"mesh":["260",0],"filename_prefix":prefix}}
    g["902"]={"class_type":"SaveGLB","inputs":{"mesh":["241",0],"filename_prefix":prefix+"_hi"}}
    return g


PIXAL_MV_MODEL = "pixal3d_multiview_bf16.safetensors"   # the multiview checkpoint; int8 variant: pixal3d_multiview_int8_convrot.safetensors
def to_multiview(g, files, model=None):
    """Turn a single-image graph (build_single / build_tex) into a multiview one: files = {"front": name, "left": ..., "back": ..., "right": ...} (1024 px squares in ComfyUI's input folder,
    object on black, one shared scale). The multiview conditioning replaces the background removal, crop and MoGe fov of the single-image path."""
    for k in ("122", "193", "192", "248", "303", "312", "55", "56", "242"): g.pop(k, None)
    for i, n in enumerate(files): g[f"mv{i}"] = {"class_type": "LoadImage", "inputs": {"image": files[n]}}
    g["298"] = {"class_type": "Pixal3DMultiViewConditioning", "inputs": {"clip_vision_model": ["15", 0], "fov": 20.0, **{n: [f"mv{i}", 0] for i, n in enumerate(files)}}}
    g["319"]["inputs"]["unet_name"] = model or PIXAL_MV_MODEL
    return g
def build_single_mv(files, prefix, seed=42, model=None): return to_multiview(build_single("x.png", prefix, seed), files, model)
def build_tex_mv(files, prefix, seed=42, model=None, **kw): return to_multiview(build_tex("x.png", prefix, seed, **kw), files, model)

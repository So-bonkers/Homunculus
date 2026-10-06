import sys, os, shutil, time
MIA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(MIA_DIR, "vendor")); sys.path.insert(0, os.getcwd())
os.environ["GRADIO_ANALYTICS_ENABLED"]="False"
import app as A
for _n in ("Info","Warning","Success"): setattr(A.gr,_n,lambda m,*a,**k: print("[gr]",m,flush=True))
for k in ("state","output_rest_vis","output_anim","output_anim_vis","output_joints_coarse","output_normed_input","output_sample","output_joints","output_bw","output_rest_lbs"): setattr(A,k,k)
inp=sys.argv[1]; reset=("--reset" in sys.argv)
work=os.path.join(MIA_DIR, "work"); os.makedirs(work,exist_ok=True)
name=sys.argv[2] if len(sys.argv)>2 and not sys.argv[2].startswith("--") else "character"
if "--normal" in sys.argv: name+="_n"
dst=os.path.join(work,name+".glb"); shutil.copy(inp,dst)
t0=time.time(); A.init_models(); print("models loaded",round(time.time()-t0,1),"s",flush=True)

def sanitize_weights(db, thr=0.25, log=print):
    """Reassign vertices whose dominant bone is physically far away (MIA occasionally binds stray parts to the hands)."""
    import numpy as np
    import torch
    def arr(x): return x.detach().cpu().numpy() if hasattr(x,"detach") else np.asarray(x)
    shape=tuple(db.bw.shape); bw=arr(db.bw).astype(np.float32).reshape(-1,shape[-1]); V=arr(db.verts).astype(np.float32).reshape(-1,3)
    jj=arr(db.joints).astype(np.float32)
    if db.joints_tail is None and jj.shape[-1]==6: J=jj.reshape(-1,6)[:,:3]; T=jj.reshape(-1,6)[:,3:]   # right after infer(): head|tail packed
    else: J=jj.reshape(-1,3); T=arr(db.joints_tail).astype(np.float32).reshape(-1,3)
    def segd(P,a,b):
        ab=b-a; t=np.clip(((P-a)*ab).sum(-1)/np.maximum((ab*ab).sum(-1),1e-9),0,1); return np.linalg.norm(P-(a+t[...,None]*ab),axis=-1)
    dom=bw.argmax(-1); d=segd(V,J[dom],T[dom]); far=np.nonzero(d>thr)[0]
    log(f"weight sanity: {len(far)} of {len(V)} vertices bound to a bone farther than {thr}")
    if len(far):
        P=V[far][:,None,:]; D=segd(P,J[None],T[None])                    # (n_far, 52)
        w=np.exp(-(D-D.min(1,keepdims=True))/0.03); w[D>D.min(1,keepdims=True)+0.08]=0
        bw[far]=w/w.sum(1,keepdims=True)
        out=bw.reshape(shape); db.bw=db.bw.new_tensor(out) if hasattr(db.bw,"new_tensor") else out
    return len(far)

def refine_joints(db, tol=0.15, log=print):
    """Move each joint to where its bone's skin region meets its parent's (the weight model is more reliable than the
    joint model for unusual arm poses). Only joints that are off by more than `tol` are moved; children follow."""
    import numpy as np, torch
    def arr(x): return x.detach().cpu().numpy() if hasattr(x,"detach") else np.asarray(x)
    bw=arr(db.bw).astype(np.float32).reshape(-1,arr(db.bw).shape[-1]); V=arr(db.verts).astype(np.float32).reshape(-1,3)
    jj=arr(db.joints).astype(np.float32); shape=jj.shape; jj=jj.reshape(-1,6).copy()
    parents=list(A.KINEMATIC_TREE.parent_indices); names=list(A.bones_idx_dict_joints.keys())
    top2=np.argsort(-bw,1)[:,:2]; w1=np.take_along_axis(bw,top2[:,:1],1)[:,0]; w2=np.take_along_axis(bw,top2[:,1:],1)[:,0]
    moved=[]
    order=list(range(len(parents)))                       # parents come before children in the Mixamo tree
    for b in order:
        p=parents[b]
        if p is None or p<0: continue
        pair=((top2[:,0]==b)&(top2[:,1]==p))|((top2[:,0]==p)&(top2[:,1]==b))
        sel=pair&(np.abs(w1-w2)<0.35)
        if sel.sum()<20: continue
        c=V[sel].mean(0); off=c-jj[b,:3]
        if np.linalg.norm(off)>tol:
            jj[b,:3]+=off; moved.append((names[b].split(":")[-1],round(float(np.linalg.norm(off)),3)))
            # translate the whole sub-tree so bone lengths stay sensible
            stack=[k for k in order if parents[k]==b]
            while stack:
                k=stack.pop(); jj[k,:3]+=off; jj[k,3:]+=off; stack+=[m for m in order if parents[m]==k]
            jj[b,3:]+=off
    # parent tails follow child heads
    for b in order:
        kids=[k for k in order if parents[k]==b]
        if len(kids)==1: jj[b,3:]=jj[kids[0],:3]
    log(f"joint refinement: moved {len(moved)} joints {moved[:12]}")
    db.joints=db.joints.new_tensor(jj.reshape(shape)) if hasattr(db.joints,"new_tensor") else jj.reshape(shape)
db=A.DB()
A.prepare_input(dst,False,0.0,db); print("prepared; verts",db.verts.shape,flush=True)
A.preprocess(db); print("preprocessed",flush=True)
A.infer(("--normal" in sys.argv),db); print("inferred",flush=True)
if "--refine" in sys.argv: refine_joints(db)   # experimental: off by default (breaks MIA rest-pose transfer)
A.vis(True,"LeftArm",False,db); print("weights post-processed",flush=True)
sanitize_weights(db)
A.vis_blender(reset,False,None,[],None,True,True,db); print("exported",db.anim_path,db.anim_vis_path,flush=True)

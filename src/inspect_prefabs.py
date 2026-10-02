import os,sys
os.environ['CIM2_RUNTIME_DATA_DIR']=os.environ.get('CIM2_RUNTIME_DATA_DIR',r'.\data'); os.environ['CIM2_PAYLOAD_DIR']=os.environ.get('CIM2_PAYLOAD_DIR',r'.\jobs'); os.environ['CIM2_MANAGED_ROOT']=os.environ.get('CIM2_MANAGED_ROOT',''); sys.argv=['x',os.environ.get('CIM2_SAVE_PATH','save.safe-copy')]; sys.path.insert(0,r'.\src')
import extract_runtime_data as e
root,_=e.load_root(False); om=e.field(root,'m_objectManagerData'); div=e.field(om,'m_divisions')
counts={}; total=0; types={}
for ix in range(div.GetLength(0)):
 for iy in range(div.GetLength(1)):
  d=div.GetValue(ix,iy)
  for obj in e.array_values(e.field(d,'m_largeObjects')):
   if obj is not None: types[str(obj.GetType())]=types.get(str(obj.GetType()),0)+1
print('object types',sorted(types.items(),key=lambda x:-x[1])[:20])
lines=[]
counts={}; total=0
for obj in lines:
    try:
        stops=e.array_values(e.field(obj,'m_stops'))
    except Exception: continue
    for stop in stops:
        sd=e.field(stop,'m_stopData') or e.field(stop,'m_data')
        if sd is None: continue
        p=e.field(sd,'m_prefabObject'); total+=1; key='null' if p is None else str(e.field(p,'m_id')); counts[key]=counts.get(key,0)+1
print('stop refs',total,'unique',len(counts)); print(sorted(counts.items(),key=lambda x:-x[1])[:20])

import sys,csv,math
from pathlib import Path
sys.argv=[sys.argv[0],sys.argv[1] if len(sys.argv)>1 else r'data\quicksave.76561198362520556-76561198845688243.save']
import extract_runtime_data as e
PARAMS={'公交':(3300,12),'无轨电车':(3400,8),'有轨电车':(3500,8),'地铁':(8000,15),'单轨列车':(8000,15),'水上巴士':(5000,30)}
SLOT=3e9; SPAN=350000
root,_=e.load_root(); t=e.field(root,'m_transportManagerData'); l=e.field(t,'m_firstLine'); seen=set(); out=[]
while l is not None:
 oid=int(e.field(l,'m_objectID') or 0)
 if oid in seen:break
 seen.add(oid); n=int(e.field(l,'m_number') or 0); mode=e.line_mode(l); stops=e.array_values(e.field(l,'m_stops')); dist=0
 for i,ls in enumerate(stops):
  path=e.array_values(e.field(ls,'m_path'))
  for p in path[:-1]:
   road=e.field(p,'m_road')
   if road is not None:dist+=int(e.field(road,'m_length') or 0)
  a=e.field(stops[(i+1)%len(stops)],'m_stop') if stops else None; b=e.field(ls,'m_stop') if ls else None
  try:
   pa=e.field(a,'m_position');pb=e.field(b,'m_position'); d=math.sqrt(sum((int(e.field(pa,k))-int(e.field(pb,k)))**2 for k in ('x','y','z')));dist+=max(0,d)
  except: pass
 speed,st=PARAMS[mode]; raw=((int(dist)*16)//speed+st*60*len(stops))*SPAN; dur=max(6e9,((raw+SLOT-1)//SLOT)*SLOT)
 out.append((n,mode,dist/1024000,dur/600e6,int(e.field(l,'m_estimatedDuration') or 0)/600e6,int(e.field(l,'m_lineLength') or 0)/1024000))
 l=e.field(l,'m_nextLine')
print('line mode panel_km panel_min cache_min cache_km')
for r in out:
 if r[0] in {201,301,302,309,310,313,317,327,111,112,101,102,107,901,204,501,209,505}:print(r)

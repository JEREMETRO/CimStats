import sys
sys.argv=[sys.argv[0],sys.argv[1] if len(sys.argv)>1 else r'data\quicksave.76561198362520556-76561198845688243.save']
import extract_runtime_data as e
SPAN=350000; SLOT_TICKS=3_000_000_000; SLOTS=2016
def exact_top(line, duration):
 buf=[0]*SLOTS
 tables=e.array_values(e.field(line,'m_timeTables'))
 for day in range(7):
  for tt in tables:
   mask=int(e.field(tt,'m_activeDays') or 0)
   if not (mask & (1<<day)): continue
   for rr in e.array_values(e.field(tt,'m_rows')):
    dep=int(e.field(rr,'m_departure') or 0)
    start=(day*288 + dep//SLOT_TICKS)%SLOTS
    end=(day*288 + (dep+duration)//SLOT_TICKS)%SLOTS
    k=start
    while k<end:
     buf[k]+=1; k+=1
 return max(buf),sum(buf)/SLOTS
root,_=e.load_root(); t=e.field(root,'m_transportManagerData'); l=e.field(t,'m_firstLine'); seen=set(); rows=[]
while l is not None:
 oid=int(e.field(l,'m_objectID') or 0)
 if oid in seen: break
 seen.add(oid); n=int(e.field(l,'m_number') or 0); mode=e.line_mode(l)
 dur=int(e.field(l,'m_estimatedDuration') or 0); top=int(e.field(l,'m_vehiclesNeededTop') or 0)
 et,avg=exact_top(l,dur) if dur>0 else (0,0)
 rebuilt=exact_top(l,57_000_000_000) if n==327 else None
 rows.append((n,mode,dur/1e9,top,et,avg,rebuilt))
 l=e.field(l,'m_nextLine')
print('total',len(rows),'top mismatches',sum(r[3]!=r[4] for r in rows if r[2]>0))
for r in rows:
 if r[3]!=r[4] and r[2]>0: print('MISMATCH',r)
for r in rows:
 if r[0]==327: print('327 at 95 minutes',r[6])

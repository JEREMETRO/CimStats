import sys
sys.argv=[sys.argv[0],sys.argv[1] if len(sys.argv)>1 else r'data\quicksave.76561198362520556-76561198845688243.save']
import extract_runtime_data as e
root,_=e.load_root(); players,companies,types=e.company_rows(root)
for r in types:
 print(r)
print('line sums by owner/mode')
t=e.field(root,'m_transportManagerData'); l=e.field(t,'m_firstLine'); seen=set(); sums={}
while l is not None:
 oid=int(e.field(l,'m_objectID') or 0)
 if oid in seen:break
 seen.add(oid); depot=e.field(l,'m_depot'); owner=e.field(depot,'m_owner') if depot else None; idx=next((i for i,p in enumerate(players) if owner is not None and e.System.Object.ReferenceEquals(owner,e.field(p,'m_companyData'))),None); mode=e.line_mode(l); prev=sums.get((idx,mode),[0,0]); prev[0]+=int(e.field(l,'m_income') or 0); prev[1]+=int(e.field(l,'m_expenses') or 0); sums[(idx,mode)]=prev
 l=e.field(l,'m_nextLine')
for k,v in sums.items():print(k,v)

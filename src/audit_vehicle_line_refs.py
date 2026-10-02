import sys;sys.argv=[sys.argv[0],r'data\quicksave.76561198362520556-76561198845688243.save'];sys.path.insert(0,'src');import extract_runtime_data as e
root,_=e.load_root();t=e.field(root,'m_transportManagerData');l=e.field(t,'m_firstLine');seen=set()
while l:
 oid=int(e.field(l,'m_objectID') or 0)
 if oid in seen:break
 seen.add(oid);n=int(e.field(l,'m_number') or 0)
 if n in (327,301,309,310,111,112):
  print('LINE',n,'id',oid,'cache',int(e.field(l,'m_lineLength') or 0),int(e.field(l,'m_estimatedDuration') or 0),int(e.field(l,'m_vehiclesNeededTop') or 0),'vehicles',len(e.array_values(e.field(l,'m_vehicles'))))
  for i,lv in enumerate(e.array_values(e.field(l,'m_vehicles'))):
   dv=e.field(lv,'m_depotVehicle'); dline=e.field(e.field(dv,'m_lineVehicle'),'m_line') if dv else None
   print('  V',i,'line?',int(e.field(dline,'m_number') or 0) if dline else None,'cache',int(e.field(dline,'m_lineLength') or 0) if dline else None)
 l=e.field(l,'m_nextLine')

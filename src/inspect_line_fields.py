import os,sys
os.environ['CIM2_RUNTIME_DATA_DIR']=os.environ.get('CIM2_RUNTIME_DATA_DIR',r'.\data');os.environ['CIM2_PAYLOAD_DIR']=os.environ.get('CIM2_PAYLOAD_DIR',r'.\jobs');os.environ['CIM2_MANAGED_ROOT']=os.environ.get('CIM2_MANAGED_ROOT','');sys.argv=['x',os.environ.get('CIM2_SAVE_PATH','save.safe-copy')];sys.path.insert(0,r'.\src')
import extract_runtime_data as e
root,_=e.load_root(False); om=e.field(root,'m_objectManagerData'); div=e.field(om,'m_divisions')
for ix in range(128):
 for iy in range(128):
  for obj in e.array_values(e.field(div.GetValue(ix,iy),'m_largeObjects')):
   if obj is not None and str(obj.GetType().Name)=='LineData':
    print('LineData fields:')
    for f in obj.GetType().GetFields(e.FLAGS): print(f.Name, f.FieldType)
    st=obj.GetType().GetNestedType('Stop', e.FLAGS)
    print('STOP TYPE',st)
    for f in st.GetFields(e.FLAGS): print('stop',f.Name,f.FieldType)
    raise SystemExit

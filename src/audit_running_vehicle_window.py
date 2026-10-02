from __future__ import annotations
import csv, sys
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[1]
SAVE=Path(sys.argv[1]) if len(sys.argv)>1 else PROJECT/'data/quicksave.76561198362520556-76561198845688243.save'
if not SAVE.is_absolute(): SAVE=(PROJECT/SAVE).resolve()
sys.argv=[sys.argv[0],str(SAVE)]
import extract_runtime_data as e

root,_=e.load_root()
history_rows, _, _ = e.history_rows(root)
history_running = {
    (r.get('公司名称',''), r.get('分组','')): int(r.get('值',0) or 0)
    for r in history_rows
    if r.get('指标') == 'vehicles-running' and bool(r.get('当前槽位')) and r.get('公司名称')
}
start=e.field(root,'m_simulationStart'); now=e.field(root,'m_simulationTime'); frame=int(e.field(root,'m_simulationFrame') or 0)
span=max(1,int(round((now-start).Ticks/frame)))
hour=36_000_000_000
step_ticks=span*64
transport=e.field(root,'m_transportManagerData')
line=e.field(transport,'m_firstLine'); seen=set(); line_counts={}
while line:
 oid=int(e.field(line,'m_objectID') or 0)
 if oid in seen: break
 seen.add(oid); depot=e.field(line,'m_depot'); owner=e.field(depot,'m_owner') if depot else None
 owner_name = str(e.field(owner, 'm_name') or '') if owner else ''
 type_obj = e.field(line, 'm_type')
 type_id = str(e.field(type_obj, 'm_id') or '') if type_obj else ''
 line_counts[(owner_name, type_id)] = line_counts.get((owner_name, type_id), 0) + len(e.array_values(e.field(line,'m_vehicles')))
 line=e.field(line,'m_nextLine')
players=e.array_values(e.field(root,'m_players'))
rows=[]
for pi,p in enumerate(players):
 c=e.field(p,'m_companyData'); name=str(e.field(c,'m_name') or '')
 for item in e.array_values(e.field(c,'m_vehicleTypeData')):
  typ=str(e.field(item,'m_type') or ''); raw=int(e.field(item,'m_vehiclesRunning') or 0)
  # SimulationTick accumulates one m_tempRunning per simulation tick and
  # flushes it at an hour boundary.  This is therefore an hourly integral.
  avg=raw*step_ticks/hour
  hist_raw = history_running.get((name, typ), None)
  rows.append({'公司序号':pi,'公司名称':name,'车型类型':typ,'m_vehiclesRunning原值':raw,'frameTimeSpan':span,'每帧游戏Tick':step_ticks,'最近未结算累计换算平均车辆':round(avg,6),'最后完整小时历史原值':hist_raw if hist_raw is not None else '','最后完整小时平均车辆':round(hist_raw/1024,6) if hist_raw is not None else '','当前线路车辆数':line_counts.get((name,typ),0)})
out=PROJECT/'exports'/f'CIM2_运行车辆窗口审计_{SAVE.stem}.csv'
with out.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('span',span,'step_ticks',step_ticks,'output',out)
for r in rows: print(r)

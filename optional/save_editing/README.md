# CIM2 Unity save-editing bridge

This directory is optional and is not imported by the normal statistics
application. It documents the only supported write-back boundary.

The v1.6.3 managed layout is:

```text
LineData.Serialize
  ObjectData
  vehicle type, number, name
  stops object array
  vehicles object array
  active flags and position
  timeTables object array
    TimeTable: activeDays, startTime, endTime, interval,
               preferSize, trainConfiguration, rows[]
    TimeTableRow: departure
  departure state, depot reference, finance and cached metrics
```

`RulesetData` can be edited in place because its records are fixed-size. A
line timetable cannot be treated that way: changing row counts changes object
array content and the serializer's reference table. A write helper therefore
must run inside the Unity process, load the save through the game's own loader,
mutate `LineData.m_timeTables`, and call the game's save service.

The Python side only launches an explicitly supplied helper and enforces the
safe-copy and output checks. It never injects code, patches the installation,
or emits a candidate file without the helper's success status.

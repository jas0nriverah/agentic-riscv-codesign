# Synthetic V10d timing preflight

This package contains one native nextpnr route of the retained literal XOR toy, not any of the 32 study pairs. No new synthesis, model fitting, candidate selection, or study timing collection ran.

Fixed HX8K/CT256, four declared pins,12 MHz,seed1,one thread,180-second limit. The single route passed. All132 mapped boundary FFs remain identifiable in the packed design; the reported synchronous critical path is wrapper-limited (capture sampling to output serializer). Its frequency is a synthetic harness timing-model result, not arithmetic-only or physical-board evidence.

`raw-evidence.zip` retains untouched copied inputs,commands/environment,native report/packed/ASC/log outputs,execution record,all preflight-failure notes and the later path-classification review. `raw-evidence.json` lists every member SHA256 and byte length. The classification review binds the exact shared helper and tests; universal candidate proof remains outside this toy check.

# In D:\IN-TELLUS, create run_agent3.ps1
$env:PYTHONPATH = "D:\IN-TELLUS;D:\IN-TELLUS\Agents\agent3_advisory"
uvicorn Agents.agent3_advisory.app:app --port 8003 --reload
$env:PYTHONPATH = "C:\Users\USer\Downloads\kfueit-unibot\kfueit-unibot-main"
Set-Location "C:\Users\USer\Downloads\kfueit-unibot\kfueit-unibot-main"
uv run uvicorn --factory unibot.api.app:create_app --host 0.0.0.0 --port 8000 --log-level debug 2>&1 | Out-File "C:\Users\USer\Downloads\kfueit-unibot\kfueit-unibot-main\debug.log" -Encoding utf8

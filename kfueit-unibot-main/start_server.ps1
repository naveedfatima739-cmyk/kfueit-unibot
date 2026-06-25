$env:PYTHONPATH = "C:\Users\USer\Downloads\kfueit-unibot\kfueit-unibot-main"
Set-Location "C:\Users\USer\Downloads\kfueit-unibot\kfueit-unibot-main"
$log = "C:\Users\USer\Downloads\kfueit-unibot\kfueit-unibot-main\server_output.log"
uv run uvicorn --factory unibot.api.app:create_app --host 0.0.0.0 --port 8000 *>&1 | Out-File $log -Encoding utf8

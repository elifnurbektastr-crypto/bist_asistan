# Admin sayfasını SADECE bu bilgisayarda açar (127.0.0.1:8502).
# Kullanım: proje klasöründe  powershell -ExecutionPolicy Bypass -File admin_baslat.ps1
$proje = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:BIST_ADMIN_YEREL = "1"
Set-Location $proje
& "$proje\.venv\Scripts\python.exe" -m streamlit run app\admin_app.py --server.address 127.0.0.1 --server.port 8502

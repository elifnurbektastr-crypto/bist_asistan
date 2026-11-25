# Kullanıcı uygulamasını yerelde açar (127.0.0.1:8501). Yayında Streamlit Cloud kullanılır.
# Kullanım: proje klasöründe  powershell -ExecutionPolicy Bypass -File uygulama_baslat.ps1
$proje = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proje
& "$proje\.venv\Scripts\python.exe" -m streamlit run app\streamlit_app.py --server.address 127.0.0.1 --server.port 8501

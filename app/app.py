from flask import Flask, Response, render_template_string
import socket
import time
import random
# Prometheus kütüphanesini ekliyoruz (Sayım yapmak için)
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# --- METRİKLER (SAYAÇLAR) ---
# Siteye gelen toplam istek sayısını tutan sayaç
REQUEST_COUNT = Counter('http_requests_total', 'Toplam HTTP istek sayisi', ['method', 'endpoint'])

# --- HTML TASARIMI (Basit Bir E-Ticaret Sayfası) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoScaleOps Shop</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; color: #333; text-align: center; padding: 50px; }
        .container { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }
        h1 { color: #e63946; font-size: 3em; margin-bottom: 10px; }
        p { font-size: 1.2em; color: #555; }
        .server-info { margin-top: 30px; padding: 15px; background: #e9ecef; border-radius: 8px; font-size: 0.9em; color: #666; }
        .btn { display: inline-block; background: #e63946; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 20px; transition: 0.3s; }
        .btn:hover { background: #d62828; transform: scale(1.05); }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 CI/CD BAŞARILI! 🔥</h1>
        <p>Otomasyon hattımız çalışıyor! İndirimler başladı!</p>
        <a href="/hesapla" class="btn">Alışverişe Başla (CPU Yükle)</a>
        
        <div class="server-info">
            <p>Bu sayfa şu sunucuda çalışıyor:</p>
            <code>{{ hostname }}</code>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def hello():
    # Ana sayfaya her girildiğinde sayacı artır
    REQUEST_COUNT.labels(method='GET', endpoint='/').inc()
    
    hostname = socket.gethostname()
    return render_template_string(HTML_TEMPLATE, hostname=hostname)

@app.route('/hesapla')
def hesapla():
    # Hesapla sayfasına girildiğinde de sayacı artır
    REQUEST_COUNT.labels(method='GET', endpoint='/hesapla').inc()
    
    # CPU Yorma İşlemi (Simülasyon)
    start_time = time.time()
    # Döngüyü biraz küçülttüm ki hemen çökmesin, ama yine de yorsun
    for i in range(5000000): 
        _ = i * i
    
    duration = time.time() - start_time
    hostname = socket.gethostname()
    
    return f"""
    <div style="text-align:center; padding:50px; font-family:sans-serif;">
        <h1 style="color:green;">✅ İşlem Tamamlandı!</h1>
        <p>Sunucu bu işlem için <strong>{duration:.2f} saniye</strong> harcadı.</p>
        <p>Hizmet veren sunucu: <code>{hostname}</code></p>
        <a href="/">Ana Sayfaya Dön</a>
    </div>
    """

# --- PROMETHEUS İÇİN VERİ KAPISI ---
@app.route('/metrics')
def metrics():
    # Prometheus gelip bu adrese baktığında, topladığımız verileri ona veriyoruz
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

@app.route('/health')
def health():
    return {"status": "healthy"}, 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
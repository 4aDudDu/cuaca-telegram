import os
import requests
from datetime import datetime, timezone, timedelta

# Ambil Token & Chat ID dari GitHub Secrets
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

LOKASI = [
    {
        "nama": "Kateman, Indragiri Hilir",
        "lat": 0.3125,
        "lon": 103.6067,
        "tz": "Asia/Jakarta",     # WIB (UTC+7)
        "kode_waktu": "WIB",
        "offset_jam": 7
    },
    {
        "nama": "Jl. HKSN Permai, Banjarmasin",
        "lat": -3.2845,
        "lon": 114.5828,
        "tz": "Asia/Makassar",    # WITA (UTC+8)
        "kode_waktu": "WITA",
        "offset_jam": 8
    }
]

def kirim_telegram(pesan):
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: BOT_TOKEN atau CHAT_ID belum diset!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": pesan,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload, timeout=15)

def main():
    for lok in LOKASI:
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lok['lat']}&longitude={lok['lon']}"
                f"&hourly=precipitation,precipitation_probability"
                f"&timezone={lok['tz']}&forecast_days=2"
            )
            res = requests.get(url, timeout=15).json()
            
            hourly_times = res["hourly"]["time"]
            hourly_precip = res["hourly"]["precipitation"]
            hourly_prob = res["hourly"]["precipitation_probability"]

            tz_lokal = timezone(timedelta(hours=lok["offset_jam"]))
            sekarang = datetime.now(tz_lokal)
            
            # Cek prakiraan 1 jam ke depan
            satu_jam_lagi = (sekarang + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")

            if satu_jam_lagi in hourly_times:
                idx = hourly_times.index(satu_jam_lagi)
                curah_hujan = hourly_precip[idx]
                peluang = hourly_prob[idx] if hourly_prob[idx] is not None else 0

                print(f"[{lok['nama']}] Jam {satu_jam_lagi}: Hujan={curah_hujan}mm, Peluang={peluang}%")

                # Kirim notif jika curah hujan > 0.2 mm atau peluang hujan >= 60%
                if curah_hujan > 0.2 or peluang >= 60:
                    jam_tampil = satu_jam_lagi.split("T")[1]
                    pesan = (
                        f"⚠️ *PERINGATAN DINI HUJAN (1 JAM LAGI)*\n\n"
                        f"📍 *Lokasi:* {lok['nama']}\n"
                        f"⏰ *Perkiraan Hujan:* Pukul {jam_tampil} {lok['kode_waktu']}\n"
                        f"🌧️ *Intensitas:* {curah_hujan} mm\n"
                        f"📊 *Peluang Hujan:* {peluang}%\n\n"
                        f"_Siapkan payung/jas hujan atau amankan jemuran!_"
                    )
                    kirim_telegram(pesan)
        except Exception as e:
            print(f"Error pada {lok['nama']}: {e}")

if __name__ == "__main__":
    main()
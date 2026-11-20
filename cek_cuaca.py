import os
import requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
# Mendeteksi apakah dijalankan lewat tombol manual (workflow_dispatch)
IS_MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

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
        print("ERROR: BOT_TOKEN atau CHAT_ID kosong!")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Memecah beberapa Chat ID yang dipisahkan tanda koma
    daftar_chat_id = [cid.strip() for cid in CHAT_ID.split(",") if cid.strip()]
    print(f"Mengirim ke {len(daftar_chat_id)} tujuan...")
    
    for target_id in daftar_chat_id:
        payload = {
            "chat_id": target_id,
            "text": pesan,
            "parse_mode": "Markdown"
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            print(f"Status Telegram ({target_id}):", resp.status_code, resp.text)
        except Exception as e:
            print(f"Gagal kirim ke {target_id}: {e}")

def main():
    ada_hujan = False
    laporan_cerah = []

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
            satu_jam_lagi = (sekarang + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")

            if satu_jam_lagi in hourly_times:
                idx = hourly_times.index(satu_jam_lagi)
                curah_hujan = hourly_precip[idx]
                peluang = hourly_prob[idx] if hourly_prob[idx] is not None else 0

                # Cek apakah 1 jam lagi akan hujan
                if curah_hujan > 0.2 or peluang >= 60:
                    ada_hujan = True
                    jam_mulai = satu_jam_lagi.split("T")[1]
                    
                    # Cari perkiraan sampai jam berapa hujan berlangsung
                    idx_selesai = idx + 1
                    max_curah = curah_hujan
                    max_peluang = peluang

                    while idx_selesai < len(hourly_times):
                        c_next = hourly_precip[idx_selesai]
                        p_next = hourly_prob[idx_selesai] if hourly_prob[idx_selesai] is not None else 0
                        if c_next > 0.2 or p_next >= 50:
                            if c_next > max_curah:
                                max_curah = c_next
                            if p_next > max_peluang:
                                max_peluang = p_next
                            idx_selesai += 1
                        else:
                            break

                    jam_selesai = hourly_times[idx_selesai].split("T")[1] if idx_selesai < len(hourly_times) else "beberapa jam ke depan"

                    pesan = (
                        f"🌧️ *Hai, sebentar lagi mau hujan loh!*\n\n"
                        f"📍 *Lokasi:* {lok['nama']}\n"
                        f"⏰ *Perkiraan Hujan:* Pukul *{jam_mulai}* sampai *{jam_selesai} {lok['kode_waktu']}*\n"
                        f"💧 *Curah Hujan:* ±{max_curah} mm\n"
                        f"📊 *Peluang Hujan:* {max_peluang}%\n\n"
                        f"Jangan lupa bawa payung/jas hujan kalau mau keluar, atau buruan angkat jemuran ya! ☂️"
                    )
                    kirim_telegram(pesan)
                else:
                    laporan_cerah.append(f"• *{lok['nama']}*: Aman/cerah (peluang hujan {peluang}%)")

        except Exception as e:
            print(f"Error pada {lok['nama']}: {e}")

    # Jika dijalankan manual lewat tombol GitHub & cuaca sedang cerah, tetap kirim info tes
    if IS_MANUAL and not ada_hujan:
        pesan_tes = (
            f"☀️ *Hai! Bot Cuaca berhasil terhubung ke grup ini.*\n\n"
            f"Untuk 1 jam ke depan belum ada tanda-tanda hujan:\n" +
            "\n".join(laporan_cerah)
        )
        kirim_telegram(pesan_tes)

if __name__ == "__main__":
    main()

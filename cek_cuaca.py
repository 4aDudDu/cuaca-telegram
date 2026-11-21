import os
import requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
IS_MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"

# ID Grup Tujuan
GRUP_UTAMA = "-5321034844"     # Kateman & Banjarmasin
GRUP_KATEMAN = "-5471550817"   # Khusus Kateman saja

LOKASI = [
    {
        "nama": "Kateman, Indragiri Hilir",
        "lat": 0.3125,
        "lon": 103.6067,
        "tz": "Asia/Jakarta",     # WIB (UTC+7)
        "kode_waktu": "WIB",
        "offset_jam": 7,
        "tujuan": [GRUP_UTAMA, GRUP_KATEMAN]
    },
    {
        "nama": "Jl. HKSN Permai, Banjarmasin",
        "lat": -3.2845,
        "lon": 114.5828,
        "tz": "Asia/Makassar",    # WITA (UTC+8)
        "kode_waktu": "WITA",
        "offset_jam": 8,
        "tujuan": [GRUP_UTAMA]
    }
]

def kirim_telegram(chat_id, pesan):
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN belum diset!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for target_id in [str(chat_id), f"-100{str(chat_id).lstrip('-')}"]:
        payload = {
            "chat_id": target_id,
            "text": pesan,
            "parse_mode": "Markdown"
        }
        try:
            resp = requests.post(url, json=payload, timeout=15)
            data = resp.json()
            if data.get("ok"):
                print(f"Berhasil kirim ke {target_id}")
                return
            else:
                print(f"Gagal ke {target_id}: {data.get('description')}")
        except Exception as e:
            print(f"Error kirim ke {target_id}: {e}")

def ambil_status_cuaca_hari_ini(lok):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lok['lat']}&longitude={lok['lon']}"
        f"&hourly=temperature_2m,precipitation,precipitation_probability"
        f"&timezone={lok['tz']}&forecast_days=1"
    )
    res = requests.get(url, timeout=15).json()
    times = res["hourly"]["time"]
    temps = res["hourly"]["temperature_2m"]
    precips = res["hourly"]["precipitation"]
    probs = res["hourly"]["precipitation_probability"]

    tz_lokal = timezone(timedelta(hours=lok["offset_jam"]))
    sekarang = datetime.now(tz_lokal)
    jam_now = sekarang.hour

    suhu_now = temps[jam_now]
    curah_now = precips[jam_now]
    prob_now = probs[jam_now] or 0

    if curah_now > 0.2 or prob_now >= 60:
        status_now = f"🌧️ Hujan ({prob_now}%)"
    elif prob_now >= 30:
        status_now = f"⛅ Berawan Tebal ({prob_now}%)"
    else:
        status_now = f"☀️ Cerah / Berawan ({prob_now}%)"

    jadwal_hujan = []
    for i in range(jam_now, 24):
        p = probs[i] or 0
        c = precips[i]
        if c > 0.2 or p >= 60:
            jam_str = times[i].split("T")[1]
            jadwal_hujan.append(f"{jam_str} ({p}%)")

    info_hujan = ", ".join(jadwal_hujan) if jadwal_hujan else "Aman, tidak ada perkiraan hujan hingga malam"

    return (
        f"📍 *{lok['nama']}*\n"
        f"• Kondisi ({jam_now:02d}:00 {lok['kode_waktu']}): {status_now}, Suhu {suhu_now}°C\n"
        f"• Perkiraan Hujan Hari Ini: {info_hujan}"
    )

def kirim_laporan_per_grup(target_grup_list, judul_header):
    for gid in target_grup_list:
        laporan_grup = []
        for lok in LOKASI:
            if gid in lok["tujuan"]:
                try:
                    laporan_grup.append(ambil_status_cuaca_hari_ini(lok))
                except Exception as e:
                    print(f"Error ambil status {lok['nama']}: {e}")
        
        if laporan_grup:
            pesan = f"{judul_header}\n\n" + "\n\n".join(laporan_grup)
            kirim_telegram(gid, pesan)

def cek_perintah_cuaca():
    if not BOT_TOKEN:
        return
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook", timeout=10)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        res = requests.get(url, timeout=15).json()
        
        updates = res.get("result", [])
        if not updates:
            return

        last_update_id = 0
        grup_peminta = set()

        for item in updates:
            last_update_id = item["update_id"]
            msg = item.get("message", {}) or item.get("edited_message", {})
            text = msg.get("text", "").strip().lower()
            chat_id = str(msg.get("chat", {}).get("id", ""))

            if "/cuaca" in text:
                if chat_id in [GRUP_UTAMA, f"-100{GRUP_UTAMA.lstrip('-')}"]:
                    grup_peminta.add(GRUP_UTAMA)
                elif chat_id in [GRUP_KATEMAN, f"-100{GRUP_KATEMAN.lstrip('-')}"]:
                    grup_peminta.add(GRUP_KATEMAN)

        if last_update_id > 0:
            requests.get(f"{url}?offset={last_update_id + 1}", timeout=10)

        if grup_peminta:
            kirim_laporan_per_grup(list(grup_peminta), "🌤️ *Status Cuaca Hari Ini*")

    except Exception as e:
        print(f"Error cek perintah /cuaca: {e}")

def cek_sapaan_pagi():
    tz_wib = timezone(timedelta(hours=7))
    sekarang_wib = datetime.now(tz_wib)

    if sekarang_wib.hour == 5 and sekarang_wib.minute < 15:
        kirim_laporan_per_grup(
            [GRUP_UTAMA, GRUP_KATEMAN],
            "🌅 *Selamat pagi!* Berikut kondisi cuaca saat ini & prakiraan hari ini:"
        )

def cek_notif_hujan_otomatis():
    for lok in LOKASI:
        try:
            tz_lokal = timezone(timedelta(hours=lok["offset_jam"]))
            sekarang = datetime.now(tz_lokal)

            if sekarang.minute >= 15:
                continue

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

            satu_jam_lagi = (sekarang + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")

            if satu_jam_lagi in hourly_times:
                idx = hourly_times.index(satu_jam_lagi)
                curah_hujan = hourly_precip[idx]
                peluang = hourly_prob[idx] if hourly_prob[idx] is not None else 0

                if curah_hujan > 0.2 or peluang >= 60:
                    jam_mulai = satu_jam_lagi.split("T")[1]
                    
                    idx_selesai = idx + 1
                    max_curah = curah_hujan
                    max_peluang = peluang

                    while idx_selesai < len(hourly_times):
                        c_next = hourly_precip[idx_selesai]
                        p_next = hourly_prob[idx_selesai] if hourly_prob[idx_selesai] is not None else 0
                        if c_next > 0.2 or p_next >= 50:
                            max_curah = max(max_curah, c_next)
                            max_peluang = max(max_peluang, p_next)
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
                    for gid in lok["tujuan"]:
                        kirim_telegram(gid, pesan)

        except Exception as e:
            print(f"Error cek hujan {lok['nama']}: {e}")

if __name__ == "__main__":
    cek_perintah_cuaca()
    
    if IS_MANUAL:
        kirim_laporan_per_grup(
            [GRUP_UTAMA, GRUP_KATEMAN],
            "✅ *Bot Cuaca Aktif!* Berikut status cuaca hari ini:"
        )
    else:
        cek_sapaan_pagi()
        cek_notif_hujan_otomatis()

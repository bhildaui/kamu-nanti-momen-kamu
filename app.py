"""Demo MVP wondr: WondrCast & WondrSaver. Jalankan: streamlit run app.py"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import data_input as D
import engine as E
import llm as L

ASSETS = Path(__file__).parent / "assets"
HALAMAN = ["Beranda", "WondrCast", "WondrSaver", "Data Nasabah"]
WARNA_LEVEL = {"Kritis": "red", "Waktu": "blue", "Peringatan": "orange", "Peluang": "green"}
WARNA_STATUS = {"Aman": "green", "Waspada": "orange", "Berisiko": "red"}

st.set_page_config(page_title="wondr | WondrCast", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 2rem;}
.kecil {font-size: 0.85rem; color: #6b7280;}
.angka {font-size: 1.6rem; font-weight: 700; margin: 0;}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data dan state
@st.cache_data(show_spinner="Memuat data nasabah...")
def muat():
    nas, tr, mer, pro = E.load_data()
    return nas, dict(tuple(tr.groupby("user_id"))), mer, pro


nasabah, trx_per_user, merchant, promo = muat()

DEFAULT_STATE = {
    "page": "Beranda", "sumber": "Nasabah dummy", "klaim": {}, "events": [],
    "popup_shown": set(), "hide_until": {}, "popup_idx": 0, "popup_aktif": None, "chat": {}, "insight": {},
    "advice_teks": {}, "as_r": 4, "as_g": 5, "as_inf": 3, "as_hemat": 20,
    "as_basis": "pendapatan",
}
for k, v in DEFAULT_STATE.items():
    st.session_state.setdefault(k, v)
for k, v in D.DEFAULT.items():
    st.session_state.setdefault(f"f_{k}", v)

# navigasi dari tombol (harus diproses sebelum widget menu dibuat)
if "nav_to" in st.session_state:
    st.session_state.page = st.session_state.pop("nav_to")
if "toast" in st.session_state:
    st.toast(st.session_state.pop("toast"))
if "sumber_to" in st.session_state:
    st.session_state.sumber = st.session_state.pop("sumber_to")


def pindah(halaman):
    if halaman not in HALAMAN:            # fitur wondr di luar prototipe
        st.session_state.toast = f"Membuka {halaman} di wondr (simulasi)."
        halaman = "WondrSaver"
    st.session_state.nav_to = halaman
    st.session_state.popup_aktif = None
    st.rerun()


def jaga_state(*kunci_state):
    """Tulis ulang nilai state tepat sebelum widget dibuat.
    Tanpa ini, widget yang baru pertama muncul menampilkan nilai minimum (perilaku Streamlit)."""
    for k in kunci_state:
        st.session_state[k] = st.session_state[k]


def catat(momen_id, kejadian):
    st.session_state.events.append({
        "waktu": datetime.now().strftime("%H:%M:%S"), "nasabah": st.session_state.get("kunci", ""),
        "momen": momen_id, "event": kejadian})


def avatar(gender, senang):
    return str(ASSETS / f"{gender}_{'senang' if senang else 'sedih'}.png")


def bar_gauge(nilai):
    """Bar gaya wondr: pill oranye, badge bulat berisi persen di ujung isian,
    bulatan emas tetap di ujung kanan sebagai penanda batas maksimum."""
    nilai = max(0, min(100, nilai))
    return f"""
    <div style="position:relative;height:34px;margin:6px 0 2px;
                background:#FBEBD3;border-radius:17px;">
      <div style="position:absolute;left:0;top:0;height:34px;width:{nilai}%;
                  background:linear-gradient(90deg,#F2994A,#F7C08A);border-radius:17px;"></div>
      <div style="position:absolute;left:{nilai}%;top:50%;transform:translate(-50%,-50%);
                  width:38px;height:38px;border-radius:50%;background:#E8763C;color:white;
                  display:flex;align-items:center;justify-content:center;font-weight:700;
                  font-size:11px;box-shadow:0 2px 4px rgba(0,0,0,.18);">{nilai}%</div>
      <div style="position:absolute;right:2px;top:50%;transform:translate(0,-50%);
                  width:24px;height:24px;border-radius:50%;background:#F4B740;
                  box-shadow:0 1px 3px rgba(0,0,0,.18);"></div>
    </div>"""


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## wondr")
    st.caption("Prototipe WondrCast & WondrSaver")
    st.radio("Menu", HALAMAN, key="page")
    st.divider()
    st.radio("Sumber data", ["Nasabah dummy", "Input manual"], key="sumber")

    if st.session_state.sumber == "Nasabah dummy":
        utama = nasabah.head(5)
        opsi = [f"{r.user_id} · {r.nama} ({r.persona})" for r in utama.itertuples()]
        opsi += [f"{r.user_id} · {r.nama} ({r.persona})" for r in nasabah.iloc[5:].itertuples()]
        pilihan = st.selectbox("Pilih nasabah", opsi, key="pilih_nasabah")
        uid = pilihan.split(" · ")[0]
    else:
        uid = "INPUT"
        if "input_data" not in st.session_state:
            st.info("Isi form di menu Data Nasabah > Input manual.")

    st.text_input("API key Gemini (opsional)", type="password", key="api_key",
                  help="Tanpa key, insight dan pesan memakai template.")
    st.caption("Semua nasabah, transaksi, merchant, dan promo adalah data dummy. "
               "Hasil adalah simulasi, bukan nasihat keuangan profesional.")

api_key = st.session_state.api_key or None
try:
    api_key = api_key or st.secrets.get("GEMINI_API_KEY")
except Exception:
    pass

# ---------------------------------------------------------------- nasabah aktif
if uid == "INPUT":
    if "input_data" not in st.session_state:
        st.session_state.input_data = D.buat_transaksi(D.DEFAULT, merchant)
    profil, transaksi = st.session_state.input_data
    kunci = "INPUT-" + hashlib.md5(transaksi.to_csv().encode()).hexdigest()[:8]
else:
    profil = nasabah[nasabah.user_id == uid].iloc[0]
    transaksi = trx_per_user[uid]
    kunci = uid
st.session_state.kunci = kunci
gender = profil["gender"]

asumsi = {"r": st.session_state.as_r / 100, "g": st.session_state.as_g / 100,
          "inflasi": st.session_state.as_inf / 100, "hemat": st.session_state.as_hemat / 100,
          "basis_kebutuhan": st.session_state.as_basis}
hasil = E.analisis(transaksi, profil, promo, merchant, asumsi, st.session_state.klaim)
m, pr, label = hasil["metrik"], hasil["proyeksi"], hasil["label"]
payload = E.payload_llm(profil, hasil)
nama = payload["nama"]


def teks_momen(momen):
    """Teks advice dari LLM (C5) dengan cache per nasabah; promo memakai teks engine."""
    advice = [x for x in hasil["advice"]]
    sidik = kunci + json.dumps([a["angka"] for a in advice], ensure_ascii=False)
    if sidik not in st.session_state.advice_teks:
        with st.spinner("Menyiapkan pesan..."):
            st.session_state.advice_teks[sidik] = L.teks_advice(advice, label, nama, api_key)
    teks, sumber = st.session_state.advice_teks[sidik]
    if momen["jenis"] == "advice" and momen["id"] in teks:
        return {**momen, **teks[momen["id"]]}, sumber
    return momen, "Engine"


# ---------------------------------------------------------------- pop-up WondrSaver
def tutup_x():
    st.session_state.popup_aktif = None
    daftar = E.pilih_popup(hasil["momen"])
    if daftar:
        catat(daftar[min(st.session_state.popup_idx, len(daftar) - 1)]["id"], "tutup")


@st.dialog("WondrSaver", width="medium", on_dismiss=tutup_x)
def popup():
    daftar = E.pilih_popup(hasil["momen"])
    i = min(st.session_state.popup_idx, len(daftar) - 1)
    momen, sumber = teks_momen(daftar[i])
    senang = momen["level"] in ("Waktu", "Peluang")

    kiri, kanan = st.columns([1, 2.4])
    kiri.image(avatar(gender, senang), width=130)
    with kanan:
        st.badge(momen["level"], color=WARNA_LEVEL[momen["level"]])
        st.subheader(momen["judul"])
        st.write(momen["pesan"])
        st.caption(f"Pesan dari {nama} usia 60 · momen {i + 1} dari {len(daftar)} · teks: {sumber}")

    if st.button(momen["label_tombol"], type="primary", width="stretch"):
        catat(momen["id"], "klik")
        pindah(momen["halaman"])
    b1, b2, b3 = st.columns(3)
    if i < len(daftar) - 1 and b1.button("Berikutnya", width="stretch"):
        st.session_state.popup_idx = i + 1
        catat(daftar[i + 1]["id"], "tampil")
        st.rerun()
    if b2.button("Tutup", width="stretch"):
        st.session_state.popup_aktif = None
        catat(momen["id"], "tutup")
        st.rerun()
    if b3.button("Jangan tampilkan hari ini", width="stretch"):
        st.session_state.popup_aktif = None
        st.session_state.hide_until[kunci] = datetime.now() + timedelta(hours=24)
        catat(momen["id"], "sembunyikan 24 jam")
        st.rerun()


def reset_momen():
    st.session_state.popup_shown = set()
    st.session_state.hide_until = {}
    st.session_state.popup_idx = 0
    st.session_state.popup_aktif = None
    st.session_state.klaim = {}
    catat("-", "reset momen")


def buka_popup_jika_perlu():
    """MK-01: tampil sekali per sesi. Dialog dibuka ulang selama masih aktif."""
    daftar = E.pilih_popup(hasil["momen"])
    if daftar and st.session_state.popup_aktif == kunci:
        popup()
        return
    tersembunyi = st.session_state.hide_until.get(kunci, datetime.min) > datetime.now()
    if daftar and kunci not in st.session_state.popup_shown and not tersembunyi:
        st.session_state.popup_shown.add(kunci)
        st.session_state.popup_aktif = kunci
        st.session_state.popup_idx = 0
        catat(daftar[0]["id"], "tampil")
        popup()


# ---------------------------------------------------------------- halaman: Beranda
def halaman_beranda():
    st.title(f"Hai, {nama}")
    st.caption(f"{profil['kota']} · {profil['pekerjaan']} · data per 27 September 2026")

    a, b, c = st.columns(3)
    a.metric("Saldo", E.rupiah(m["saldo"]))
    b.metric("Pemasukan 30 hari", E.rupiah(m["masuk_30"]))
    c.metric("Pengeluaran 30 hari", E.rupiah(m["keluar_30"]),
             delta=E.rupiah(m["masuk_30"] - m["keluar_30"]), delta_color="normal")

    menu = st.columns(4)
    for kol, teks in zip(menu, ["Transfer", "QRIS", "Life Goals", "Bayar Tagihan"]):
        kol.button(teks, width="stretch", disabled=True)

    kiri, kanan = st.columns(2)
    with kiri.container(border=True):
        st.markdown("#### WondrCast")
        x, y = st.columns([1, 2])
        x.image(avatar(gender, pr["a"]["status"] == "Aman"), width=110)
        y.badge(f"Status usia 60: {pr['a']['status']}", color=WARNA_STATUS[pr["a"]["status"]])
        y.write(f"Pola keuanganmu: **{label}**")
        y.write(f"Proyeksi kebiasaan sekarang: **{E.rupiah(pr['a']['nominal'])}**")
        if st.button("Lihat WondrCast", width="stretch"):
            pindah("WondrCast")

    with kanan.container(border=True):
        st.markdown("#### WondrSaver")
        if not hasil["momen"]:
            st.write("Belum ada momen penting.")
        for momen in hasil["momen"][:4]:
            st.markdown(f":{WARNA_LEVEL[momen['level']]}-badge[{momen['level']}] {momen['judul']}")
        if st.button("Lihat semua momen", width="stretch"):
            pindah("WondrSaver")

    st.divider()
    d1, d2 = st.columns(2)
    if d1.button("Tampilkan pop-up lagi (demo)", width="stretch"):
        st.session_state.popup_shown.discard(kunci)
        st.session_state.hide_until.pop(kunci, None)
        st.rerun()
    if d2.button("Reset momen (demo)", width="stretch"):
        reset_momen()
        st.rerun()
    if st.session_state.hide_until.get(kunci, datetime.min) > datetime.now():
        st.caption("Pop-up disembunyikan sampai besok untuk nasabah ini.")

    buka_popup_jika_perlu()


# ---------------------------------------------------------------- halaman: WondrCast
def kartu_skenario(kolom, judul, s, setoran):
    with kolom.container(border=True):
        st.markdown(f"**{judul}**")
        st.image(avatar(gender, s["status"] == "Aman"), width=150)
        st.badge(s["status"], color=WARNA_STATUS[s["status"]])
        st.markdown(f"<p class='angka'>{E.rupiah(s['nominal'])}</p>", unsafe_allow_html=True)
        st.markdown(f"<span class='kecil'>Nilai riil hari ini {E.rupiah(s['riil'])} · "
                    f"kecukupan {E.persen_bawah(s['kecukupan'])}</span>", unsafe_allow_html=True)
        st.caption(f"Setoran awal {E.rupiah(setoran)} per bulan")
        if s["catatan"]:
            st.error(s["catatan"])


def halaman_wondrcast():
    st.title("WondrCast")
    st.write(f"Gambaran keuangan **{nama}** di usia 60 berdasarkan transaksi 90 hari terakhir.")
    st.badge(f"Pola: {label}", color="violet")
    if pr["data_terbatas"]:
        st.warning("Pengeluaran yang tercatat kurang dari 20% pemasukan. Kemungkinan sebagian transaksi "
                   "terjadi di luar wondr, sehingga proyeksi bisa terlalu optimistis.")
    if int(profil["usia"]) >= 60:
        st.info("Usia nasabah sudah 60 tahun atau lebih. Proyeksi menampilkan saldo saat ini.")

    k1, k2, k3 = st.columns([1, 1, 1.2])
    kartu_skenario(k1, "A. Kebiasaan tetap", pr["a"], pr["setoran_a"])
    kartu_skenario(k2, "B. Kebiasaan diperbaiki", pr["b"], pr["setoran_b"])
    with k3.container(border=True):
        st.markdown("**Atur asumsi**")
        jaga_state("as_hemat", "as_r", "as_g", "as_inf", "as_basis")
        st.slider("Porsi hemat pengeluaran konsumtif (%)", 0, 50, key="as_hemat")
        st.slider("Imbal hasil tabungan per tahun (%)", 0, 10, key="as_r")
        st.slider("Kenaikan pendapatan per tahun (%)", 0, 10, key="as_g")
        st.slider("Inflasi per tahun (%)", 0, 10, key="as_inf")
        st.selectbox("Dasar kebutuhan pensiun", ["pendapatan", "pengeluaran"], key="as_basis",
                     help="Dokumen requirement memakai pengeluaran. Default pendapatan agar nasabah "
                          "yang jarang bertransaksi tidak terlihat terlalu aman.")

    st.line_chart(pr["seri"], x_label="Usia", y_label="Saldo (Rp)")
    st.caption(f"Kebutuhan dana pensiun: {E.rupiah(pr['kebutuhan'])} (nilai hari ini). "
               "Simulasi, bukan nasihat keuangan profesional. Asumsi adalah angka ilustratif tim, bukan angka resmi BNI.")

    with st.expander("Asumsi dan metrik perilaku"):
        a, b = st.columns(2)
        a.dataframe(E.tabel_asumsi(pr["asumsi"]), hide_index=True, width="stretch")
        b.dataframe(E.tabel_metrik(m), hide_index=True, width="stretch")

    # indikator & metrik risiko
    st.subheader("Indikator & Metrik Risiko")
    for ind in hasil["indikator"]:
        with st.container(border=True):
            kiri, kanan = st.columns([1, 2.2])
            kiri.markdown(f"**{ind['judul']}**")
            kiri.caption(ind["sub"])
            kanan.markdown(bar_gauge(ind["nilai"]), unsafe_allow_html=True)
            kanan.caption(f"{ind['label_rendah']} → {ind['label_tinggi']} · {ind['posisi']}")
            kanan.write(ind["keterangan"])

    # insight LLM (B6)
    st.subheader("Insight keuangan")
    teks_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    simpan = st.session_state.insight.get(kunci)
    perlu_baru = simpan is None
    kol_a, kol_b = st.columns([3, 1])
    if simpan and simpan[0] != teks_payload:
        kol_a.info("Asumsi berubah. Klik Perbarui insight untuk menyesuaikan penjelasan.")
    if kol_b.button("Perbarui insight", width="stretch"):
        perlu_baru = True
    if perlu_baru:
        with st.spinner("AI sedang menyusun insight..."):
            isi, sumber = L.buat_insight(payload, api_key)
        st.session_state.insight[kunci] = (teks_payload, isi, sumber)
    _, isi, sumber = st.session_state.insight[kunci]

    st.caption(f"Sumber teks: {'AI (Gemini)' if sumber == 'AI' else 'Template (AI tidak aktif atau gagal)'}")
    st.markdown(f"**{isi['ringkasan']}**")
    for kol, item in zip(st.columns(3), isi["insight"]):
        with kol.container(border=True):
            st.markdown(f"**{item['judul']}**")
            st.write(item["penjelasan"])
            st.caption(item["data"])
    for kol, item in zip(st.columns(3), isi["saran"]):
        with kol.container(border=True):
            st.badge(item["fitur_wondr"], color="blue")
            st.markdown(f"**{item['aksi']}**")
            st.caption(item["alasan"])
    x, y = st.columns([1, 6])
    x.image(avatar(gender, pr["b"]["status"] == "Aman"), width=90)
    y.info(f"**Pesan dari {nama} usia 60:** {isi['pesan_diri_60']}")

    # chat lanjutan (KN-10)
    st.subheader(f"Ngobrol dengan {nama} usia 60")
    riwayat = st.session_state.chat.setdefault(kunci, [])
    ava_60 = avatar(gender, pr["a"]["status"] == "Aman")
    for pesan in riwayat:
        with st.chat_message(pesan["role"], avatar=ava_60 if pesan["role"] == "assistant" else None):
            st.write(pesan["content"])
    tanya = st.chat_input("Tanya dirimu di usia 60...")
    if tanya:
        riwayat.append({"role": "user", "content": tanya})
        with st.spinner("Mengetik..."):
            jawab, _ = L.chat(payload, riwayat, api_key)
        riwayat.append({"role": "assistant", "content": jawab})
        st.rerun()


# ---------------------------------------------------------------- halaman: WondrSaver
def halaman_momen():
    st.title("WondrSaver")
    st.caption("Semua momen dan promo untuk nasabah ini, termasuk yang tidak masuk pop-up.")

    st.subheader("Momen dan saran")
    if not hasil["momen"]:
        st.write("Belum ada momen penting.")
    for momen in hasil["momen"]:
        momen, _ = teks_momen(momen)
        with st.container(border=True):
            a, b = st.columns([5, 1])
            a.markdown(f":{WARNA_LEVEL[momen['level']]}-badge[{momen['level']}] "
                       f":gray-badge[{momen['id']}] **{momen['judul']}**")
            a.write(momen["pesan"])
            if b.button(momen["label_tombol"], key=f"aksi_{momen['id']}", width="stretch"):
                catat(momen["id"], "klik")
                st.toast(f"Aksi '{momen['label_tombol']}' dicatat (simulasi).")

    st.subheader("Promo untukmu")
    if hasil["kritis"]:
        st.warning("Ada kondisi keuangan kritis. Hanya promo yang membantu menabung yang ditampilkan.")
    if not hasil["promo"]:
        st.write("Belum ada promo yang relevan.")
    for p in hasil["promo"]:
        with st.container(border=True):
            a, b = st.columns([4, 1.3])
            a.markdown(f"**{p['judul']}** · {p['merchant']}")
            a.write(p["alasan"])
            a.caption(f"{p['mekanisme']} · {p['metode_bayar']} · kuota {p['kuota']}x per bulan"
                      + (f" · {p['syarat']}" if p["syarat"] else ""))
            b.metric("Estimasi hemat/bulan", E.rupiah(p["estimasi_hemat"]))
            dipakai = st.session_state.klaim.get(p["promo_id"], 0)
            if b.button(f"Klaim ({dipakai}/{p['kuota']})", key=f"klaim_{p['promo_id']}", width="stretch"):
                st.session_state.klaim[p["promo_id"]] = dipakai + 1
                catat(p["promo_id"], "klaim promo")
                st.rerun()

    with st.expander("Perhitungan skor promo (C7.1)"):
        if hasil["promo"]:
            kolom = ["promo_id", "judul", "skor_merchant", "skor_kategori", "skor_umum",
                     "skor_metode", "skor_nabung", "skor", "frekuensi", "estimasi_hemat"]
            st.dataframe(pd.DataFrame(hasil["promo"])[kolom], hide_index=True, width="stretch")
    a, b = st.columns(2)
    with a.expander(f"Promo ditahan ({len(hasil['promo_ditahan'])})"):
        st.dataframe(pd.DataFrame(hasil["promo_ditahan"], columns=["promo_id", "judul", "alasan"]),
                     hide_index=True, width="stretch")
    with b.expander(f"Promo tidak aktif ({len(hasil['promo_tidak_aktif'])})"):
        st.dataframe(pd.DataFrame(hasil["promo_tidak_aktif"], columns=["promo_id", "judul", "alasan"]),
                     hide_index=True, width="stretch")

    st.subheader("Riwayat event (MK-10)")
    ev = pd.DataFrame(st.session_state.events, columns=["waktu", "nasabah", "momen", "event"])
    st.dataframe(ev.iloc[::-1], hide_index=True, width="stretch", height=220)
    a, b = st.columns(2)
    a.download_button("Unduh riwayat event", ev.to_csv(index=False), "event_momen.csv",
                      width="stretch")
    if b.button("Reset momen (demo)", width="stretch"):
        reset_momen()
        st.rerun()


# ---------------------------------------------------------------- halaman: Data Nasabah
def isi_skenario(nama_skenario):
    for k, v in D.SKENARIO[nama_skenario].items():
        st.session_state[f"f_{k}"] = v


def form_input():
    st.write("Pilih skenario cepat untuk mengisi form otomatis, atau isi sendiri.")
    for kol, nama_s in zip(st.columns(4), D.SKENARIO):
        kol.button(nama_s, on_click=isi_skenario, args=(nama_s,), width="stretch")

    jaga_state(*[f"f_{k}" for k in D.DEFAULT])
    with st.form("form_input"):
        a, b, c = st.columns(3)
        a.text_input("Nama", key="f_nama", max_chars=20)
        a.number_input("Usia", 18, 45, key="f_usia")
        a.selectbox("Jenis kelamin avatar", ["pria", "wanita"], key="f_jenis_kelamin")
        a.number_input("Pendapatan bulanan (Rp)", 0, 200_000_000, step=500_000, key="f_pendapatan")
        a.number_input("Saldo saat ini (Rp)", 0, 2_000_000_000, step=500_000, key="f_saldo")
        a.text_input("Tujuan hidup", key="f_tujuan")
        a.number_input("Usia target tujuan", 19, 80, key="f_usia_target")

        b.markdown("**Pengeluaran per bulan (Rp)**")
        for kat in D.KATEGORI_FORM:
            b.number_input(kat, 0, 100_000_000, step=50_000, key=f"f_{kat}")

        c.number_input("Frekuensi kopi per bulan", 0, 60, key="f_frek_kopi")
        c.selectbox("Merchant kopi favorit",
                    merchant[merchant.kategori == "Kopi"].merchant_nama.tolist(), key="f_merchant_kopi")
        c.slider("Porsi gaji ke e-wallet (%)", 0, 100, key="f_porsi_ewallet")
        c.number_input("Setoran tabungan per bulan (Rp)", 0, 100_000_000, step=100_000, key="f_setoran")
        c.number_input("Cicilan per bulan (Rp)", 0, 100_000_000, step=100_000, key="f_cicilan")
        c.toggle("Lonjakan minggu ini", key="f_lonjakan")
        c.selectbox("Kategori lonjakan", E.KAT_MERCHANT, key="f_kategori_lonjakan")
        kirim = st.form_submit_button("Proses data", type="primary", width="stretch")

    if kirim:
        nilai = {k: st.session_state[f"f_{k}"] for k in D.DEFAULT}
        error = D.validasi(nilai)
        if error:
            for e in error:
                st.error(e)
            return
        st.session_state.input_data = D.buat_transaksi(nilai, merchant)
        st.session_state.sumber_to = "Input manual"
        st.session_state.nav_to = "Beranda"
        st.rerun()


def halaman_data():
    st.title("Data Nasabah")
    tab1, tab2, tab3 = st.tabs(["Profil dan transaksi", "Input manual (demo)", "Daftar nasabah"])
    with tab1:
        st.caption(f"Nasabah aktif: {kunci}")
        a, b = st.columns([1, 2])
        tampil = profil.rename({"persona": "persona (data)"}).to_frame("nilai").astype(str)
        tampil.loc["label hasil hitung"] = label
        a.dataframe(tampil, width="stretch")
        if len(m["kategori"]):
            kat = m["kategori"][["kategori", "frekuensi", "nominal", "porsi", "merchant_favorit"]].copy()
            kat["nominal"] = kat.nominal.map(E.rupiah)
            kat["porsi"] = kat.porsi.map(E.persen)
            b.markdown("**Ringkasan 30 hari terakhir**")
            b.dataframe(kat, hide_index=True, width="stretch")
        st.markdown("**Transaksi 90 hari**")
        st.dataframe(transaksi.sort_values("tanggal_waktu", ascending=False),
                     hide_index=True, width="stretch", height=320)
        st.download_button("Unduh transaksi (CSV)", transaksi.to_csv(index=False),
                           f"transaksi_{kunci}.csv")
    with tab2:
        form_input()
    with tab3:
        persona = st.multiselect("Filter persona (kolom data)", sorted(nasabah.persona.unique()))
        daftar = nasabah[nasabah.persona.isin(persona)] if persona else nasabah
        st.dataframe(daftar, hide_index=True, width="stretch", height=420)
        st.caption("Pilih nasabah lewat panel kiri. Label di aplikasi dihitung ulang dari transaksi.")


{"Beranda": halaman_beranda, "WondrCast": halaman_wondrcast,
 "WondrSaver": halaman_momen, "Data Nasabah": halaman_data}[st.session_state.page]()

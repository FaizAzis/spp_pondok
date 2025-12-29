import streamlit as st
import pandas as pd
import altair as alt
import database_helper as db
import ai_engine
import os
import time
from datetime import datetime
from ai_engine import AIEngine

# --- 1. KONFIGURASI HALAMAN & UI ---
st.set_page_config(page_title="SIM SPP Daarul Hikmah", layout="wide")

# CSS Modern Minimalis (Aturan: Tanpa Emoji)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: #1e293b; }
    
    /* Role Tag Style */
    .role-tag {
        background-color: #f1f5f9; color: #475569; padding: 4px 12px;
        border-radius: 6px; font-size: 0.75rem; font-weight: 600;
        text-transform: uppercase; border: 1px solid #e2e8f0; display: inline-block;
    }
    
    /* Section Border Style */
    .section-border {
        border: 1px solid #e2e8f0; padding: 25px; border-radius: 12px;
        background-color: #ffffff; margin-top: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# Helper Format Nominal
def format_rp(angka):
    return f"Rp {int(angka):,.0f}".replace(",", ".")

# --- 2. PERSISTENT LOGIN ---
if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.title("Sign In System")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk"):
            # Cek ke MySQL
            user_data = db.fetch_data(f"SELECT * FROM database_users WHERE username='{u}' AND password='{p}'")
            if not user_data.empty:
                st.session_state.update({
                    "auth": True, 
                    "u_full": user_data.iloc[0]['nama_user'], 
                    "u_role": user_data.iloc[0]['role']
                })
                st.rerun()
            else:
                st.error("Username atau Password salah")
    st.stop()

# --- 3. SIDEBAR ---
with st.sidebar:
    # Logo PNG
    if os.path.exists("logo.png"):
        st.image("logo.png", width=120)
    
    st.markdown("### SIM SPP Daarul Hikmah")
    st.write(st.session_state["u_full"])
    st.markdown(f'<div class="role-tag">{st.session_state["u_role"]}</div>', unsafe_allow_html=True)
    st.divider()
    
    # Navigasi
    menu = st.radio("Navigasi", [
        "Dashboard", 
        "Master Santri", 
        "Form Pembayaran", 
        "Histori Transaksi", 
        "Laporan Keuangan", 
        "Manajemen User",
        "Analisis AI"
    ])
    
    # Tombol Logout
    if st.button("Keluar Akun", use_container_width=True):
        st.session_state["auth"] = False
        st.rerun()

# Global Data (Dipanggil setiap menu agar selalu update)
df_master = db.fetch_data("SELECT * FROM master_santri")
df_payment = db.fetch_data("SELECT * FROM pembayaran_spp")
bulan_ind = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

# --- 4. MODUL DASHBOARD (Fix Grafik Sesuai Data) ---
if menu == "Dashboard":
    st.header("Dashboard Statistik Keuangan")

    # 1. Setup Waktu Default
    # Menggunakan tahun 2025 sesuai mayoritas data di CSV Anda
    current_year = 2025 
    current_month_idx = datetime.now().month - 1
    
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        # Pilihan tahun statis agar ringan dan pasti muncul
        list_tahun = [2024, 2025, 2026]
        sel_thn = st.selectbox("Pilih Tahun Analisis", list_tahun, index=1) # Default 2025
    with col_filter2:
        sel_bln = st.selectbox("Pilih Bulan Analisis", bulan_ind, index=current_month_idx)
    
    # --- LOGIKA PERHITUNGAN DATA ---
    jumlah_santri = len(df_master)
    total_tagihan_global = df_master['spp_tetap'].sum() if not df_master.empty else 0
    
    terbayar_periode = 0
    if not df_payment.empty:
        # Pastikan kolom tanggal menjadi tipe datetime
        df_payment['tanggal_bayar'] = pd.to_datetime(df_payment['tanggal_bayar'], errors='coerce')
        
        # FILTER: Berdasarkan jatah bulan (untuk_bulan) dan TAHUN dari tanggal transaksi
        mask = (df_payment['untuk_bulan'] == sel_bln) & \
               (df_payment['tanggal_bayar'].dt.year == int(sel_thn))
        data_filtered = df_payment[mask]
        terbayar_periode = data_filtered['nominal_bayar'].sum()
        
    sisa_tagihan_periode = max(0, total_tagihan_global - terbayar_periode)

    # --- TAMPILAN METRIK ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Jumlah Santri", f"{jumlah_santri}")
    m2.metric("Target Kas", format_rp(total_tagihan_global))
    m3.metric(f"Realisasi ({sel_bln})", format_rp(terbayar_periode))
    m4.metric("Sisa Piutang", format_rp(sisa_tagihan_periode))

    st.divider()

    # --- LAYOUT 2 PANEL ---
    col_grafik, col_status = st.columns([3, 2], gap="large")

    with col_grafik:
        st.subheader(f"📊 Progress Pemenuhan SPP {sel_thn}")
        
        annual_data = []
        for bln in bulan_ind:
            terbayar_bln = 0
            if not df_payment.empty:
                # Filter grafik tahunan berdasarkan tahun transaksi di data Anda
                mask_bln = (df_payment['untuk_bulan'] == bln) & \
                           (df_payment['tanggal_bayar'].dt.year == int(sel_thn))
                terbayar_bln = df_payment[mask_bln]['nominal_bayar'].sum()
            
            # Label status untuk warna grafik
            status_bulanan = "Lunas" if (terbayar_bln >= total_tagihan_global and total_tagihan_global > 0) else "Tunggakan"
            
            annual_data.append({
                "Bulan": bln,
                "Total Terbayar": terbayar_bln,
                "Keterangan": status_bulanan
            })
        
        df_annual = pd.DataFrame(annual_data)
        
        # Render Grafik Altair
        chart = alt.Chart(df_annual).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
            x=alt.X('Bulan', sort=bulan_ind, title=None),
            y=alt.Y('Total Terbayar', title="Total (Rp)"),
            color=alt.Color('Keterangan', scale=alt.Scale(domain=['Lunas', 'Tunggakan'], range=['#10b981', '#f59e0b'])),
            tooltip=['Bulan', alt.Tooltip('Total Terbayar', format=',.0f'), 'Keterangan']
        ).properties(height=400)
        
        st.altair_chart(chart, use_container_width=True)

    with col_status:
        st.subheader(f"📋 Status: {sel_bln}")
        f_stat = st.segmented_control("Filter:", ["Semua", "Lunas", "Belum"], default="Semua")
        
        dash_list = []
        for _, s in df_master.iterrows():
            is_lunas = False
            if not df_payment.empty:
                # Cek per santri sesuai data di database Anda
                mask_cek = (df_payment['nis'] == s['nis']) & \
                           (df_payment['untuk_bulan'] == sel_bln) & \
                           (df_payment['tanggal_bayar'].dt.year == int(sel_thn))
                cek_bayar = df_payment[mask_cek]
                # Menggunakan sisa_tagihan = 0 sesuai screenshot database Anda
                is_lunas = not cek_bayar.empty and cek_bayar.iloc[-1]['sisa_tagihan'] == 0
            
            if f_stat == "Lunas" and not is_lunas: continue
            if f_stat == "Belum" and is_lunas: continue
            
            status_text = "Lunas" if is_lunas else "Belum"
            color_hex = "#10b981" if is_lunas else "#ef4444"
            
            dash_list.append({
                "Nama": s['nama'],
                "Status": f'<span style="color:white; background:{color_hex}; padding:2px 8px; border-radius:10px; font-size:11px;">{status_text}</span>'
            })

        if dash_list:
            st.markdown(pd.DataFrame(dash_list).to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("Data tidak ditemukan.")

# --- 5. MODUL MASTER SANTRI ---
elif menu == "Master Santri":
    st.header("Manajemen Data Master Santri")

    # --- COMPACT IMPORT CSV (3 KOLOM) ---
    with st.expander("📥 Import Santri (CSV)", expanded=False):
        c_up, c_info = st.columns([2, 1])
        with c_up:
            up_master = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed", key="up_master_simple")
        with c_info:
            st.markdown("<p style='font-size:0.75rem; color:gray;'>Format Kolom: <b>NIS, Nama, SPP_Tetap</b></p>", unsafe_allow_html=True)
        
        if up_master:
            try:
                df_imp = pd.read_csv(up_master)
                st.caption(f"📊 Terdeteksi {len(df_imp)} data santri.")
                
                if st.button("Konfirmasi Import", use_container_width=True, type="primary"):
                    for _, r in df_imp.iterrows():
                        # Menggunakan ON DUPLICATE KEY agar jika NIS sudah ada, data Nama/SPP diperbarui
                        q = """INSERT INTO master_santri (nis, nama, spp_tetap) 
                               VALUES (%s, %s, %s) 
                               ON DUPLICATE KEY UPDATE nama=%s, spp_tetap=%s"""
                        db.execute_query(q, (
                            r['NIS'], r['Nama'], r['SPP_Tetap'],
                            r['Nama'], r['SPP_Tetap']
                        ))
                    st.toast("✅ Data Master Berhasil Diupdate!")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"Error: Pastikan header CSV adalah NIS, Nama, SPP_Tetap")

    # Form Registrasi Santri Baru
    with st.expander("Registrasi Santri Baru"):
        with st.form("form_tambah_santri", clear_on_submit=True):
            col_in1, col_in2, col_in3 = st.columns([2, 4, 2])
            new_nis = col_in1.text_input("NIS")
            new_nama = col_in2.text_input("Nama Lengkap")
            new_spp = col_in3.number_input("SPP Tetap", min_value=0, step=10000)
            
            if st.form_submit_button("Simpan Data Santri"):
                if new_nis and new_nama:
                    cek_nis = db.fetch_data(f"SELECT nis FROM master_santri WHERE nis='{new_nis}'")
                    if cek_nis.empty:
                        query_add = "INSERT INTO master_santri (nis, nama, spp_tetap) VALUES (%s, %s, %s)"
                        if db.execute_query(query_add, (new_nis, new_nama, new_spp)):
                            st.toast("Data santri berhasil disimpan", icon="✅")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error("NIS sudah terdaftar di database.")
                else:
                    st.warning("Mohon lengkapi NIS dan Nama.")

    st.divider()

    # Tampilan Tabel Data Santri
    if df_master.empty:
        st.info("Belum ada data santri.")
    else:
        # Header Tabel (Menggunakan Caption agar modern dan minimalis)
        h_col1, h_col2, h_col3, h_col4 = st.columns([2, 4, 2, 2])
        h_col1.caption("NIS")
        h_col2.caption("NAMA LENGKAP")
        h_col3.caption("SPP TETAP")
        h_col4.caption("")

        for i, row in df_master.iterrows():
            with st.container():
                r_col1, r_col2, r_col3, r_col4 = st.columns([2, 4, 2, 2])
                
                r_col1.write(row['nis'])
                r_col2.write(row['nama'])
                r_col3.write(format_rp(row['spp_tetap']))
                
                # Kolom Aksi di sebelah kanan
                btn_edit, btn_del = r_col4.columns(2)
                
                state_key = f"edit_state_{row['nis']}"
                if state_key not in st.session_state:
                    st.session_state[state_key] = False
                
                if btn_edit.button("Ubah", key=f"btn_u_{row['nis']}"):
                    st.session_state[state_key] = not st.session_state[state_key]
                    st.rerun()
                
                if btn_del.button("Hapus", key=f"btn_h_{row['nis']}"):
                    query_del = "DELETE FROM master_santri WHERE nis = %s"
                    if db.execute_query(query_del, (row['nis'],)):
                        st.toast(f"Data {row['nama']} dihapus", icon="🗑️")
                        time.sleep(1)
                        st.rerun()

                # Form Edit Toggle
                if st.session_state[state_key]:
                    with st.form(key=f"form_edit_{row['nis']}"):
                        st.write(f"Edit Data: {row['nama']}")
                        e_nama = st.text_input("Nama Lengkap", value=row['nama'])
                        e_spp = st.number_input("SPP Tetap", value=int(row['spp_tetap']), step=10000)
                        
                        col_e1, col_e2 = st.columns([1, 4])
                        if col_e1.form_submit_button("Update"):
                            query_upd = "UPDATE master_santri SET nama=%s, spp_tetap=%s WHERE nis=%s"
                            if db.execute_query(query_upd, (e_nama, e_spp, row['nis'])):
                                st.session_state[state_key] = False
                                st.toast("Perubahan berhasil disimpan")
                                time.sleep(1)
                                st.rerun()
                
                st.markdown("<hr style='margin: 0.5em 0; opacity: 0.1;'>", unsafe_allow_html=True)

# --- 6. MODUL FORM PEMBAYARAN ---
elif menu == "Form Pembayaran":
    st.header("Pencatatan Transaksi Pembayaran")

    # --- SECTION PERTAMA: INPUT IDENTITAS ---
    c1, c2, c3 = st.columns(3) # Diubah menjadi 3 kolom
    with c1:
        s_nama = st.selectbox("Nama Santri", ["-- Pilih --"] + df_master['nama'].tolist(), key="sb_nama_input")
    with c2:
        s_bulan = st.selectbox("SPP Bulan-", bulan_ind, key="sb_bulan_input")
    with c3:
        # Menambahkan pilihan tahun target (Tahun sekarang s/d 2 tahun ke depan)
        now = datetime.now()
        current_year = now.year  # Otomatis 2025
        current_month_idx = now.month - 1

        tahun_pilihan = list(range(current_year - 3, current_year + 3))

        s_tahun_tagihan = st.selectbox("Tahun Periode", tahun_pilihan, index=tahun_pilihan.index(current_year), key="sb_tahun_input")

    st.markdown("---")

    # --- FUNGSI DIALOG KONFIRMASI (Logika Tahun Dinamis) ---
    @st.dialog("Konfirmasi Pembayaran")
    def konfirmasi_pembayaran_dialog(data_utama, lebihan):
        st.write("### Konfirmasi Transaksi")
        st.markdown(f"""
            **Nama:** {data_utama['nama_santri']}  
            **Periode:** {data_utama['untuk_bulan']} {s_tahun_tagihan}  
            **Nominal Utama:** {format_rp(data_utama['nominal_bayar'])}
        """)
        
        opsi_lebih = None
        target_bulan_lebih = ""

        if lebihan > 0:
            st.warning(f"Lebihan Pembayaran: **{format_rp(lebihan)}**")
            idx_sekarang = bulan_ind.index(data_utama['untuk_bulan'])
            sisa_bulan = bulan_ind[idx_sekarang + 1:]
            
            # Pencarian alokasi bulan berikutnya tetap menggunakan tahun yang dipilih
            for b in sisa_bulan:
                # Perbaikan Filter: Tambahkan filter tahun agar tidak bentrok dengan jatah SPP tahun lalu
                mask_cek = (df_payment['nis'] == data_utama['nis']) & \
                           (df_payment['untuk_bulan'] == b) & \
                           (df_payment['jatuh_tempo'].str.contains(str(s_tahun_tagihan)))
                
                cek_next = df_payment[mask_cek]
                if cek_next.empty or cek_next.iloc[-1]['sisa_tagihan'] > 0:
                    target_bulan_lebih = b
                    break
            
            if target_bulan_lebih:
                st.write(f"Alokasikan lebihan ke bulan **{target_bulan_lebih}** {s_tahun_tagihan}?")
                opsi_lebih = st.radio("Pilihan:", ["Ya, Alokasikan", "Kembalikan Tunai"], horizontal=True)

        if st.button("Simpan Transaksi", use_container_width=True, type="primary"):
            nis_f = str(data_utama['nis'])
            tagihan_f = int(data_utama['tagihan_wajib'])
            nominal_f = int(data_utama['nominal_bayar'])
            sisa_f = int(data_utama['sisa_tagihan'])

            query_ins = """INSERT INTO pembayaran_spp 
                           (nis, nama_santri, tagihan_wajib, untuk_bulan, jatuh_tempo, tanggal_bayar, nominal_bayar, sisa_tagihan, status, keterangan) 
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            
            db.execute_query(query_ins, (nis_f, data_utama['nama_santri'], tagihan_f, 
                                        data_utama['untuk_bulan'], data_utama['jatuh_tempo'], data_utama['tanggal_bayar'], 
                                        nominal_f, sisa_f, data_utama['status'], data_utama['keterangan']))

            # LOGIKA ALOKASI (Menggunakan s_tahun_tagihan)
            if lebihan > 0 and opsi_lebih == "Ya, Alokasikan" and target_bulan_lebih:
                d_m = df_master[df_master['nis'] == data_utama['nis']].iloc[0]
                spp_next = int(d_m['spp_tetap'])
                
                # Cek sisa tagihan bulan depan di tahun yang sama
                q_cek = f"SELECT sisa_tagihan FROM pembayaran_spp WHERE nis='{nis_f}' AND untuk_bulan='{target_bulan_lebih}' AND jatuh_tempo LIKE '%{s_tahun_tagihan}%' ORDER BY id DESC LIMIT 1"
                cek_next_db = db.fetch_data(q_cek)
                sisa_tujuan = int(cek_next_db.iloc[0]['sisa_tagihan']) if not cek_next_db.empty else spp_next
                
                alokasi_n = min(lebihan, sisa_tujuan)
                sisa_akhir_n = max(0, sisa_tujuan - alokasi_n)
                
                # Logika Keterangan Konsisten
                idx_t = bulan_ind.index(target_bulan_lebih)
                jt_limit_n = datetime(s_tahun_tagihan, idx_t + 1, 4).date()
                tgl_bayar_dt = datetime.strptime(data_utama['tanggal_bayar'], '%Y-%m-%d').date()
                ket_n = "Tepat Waktu" if tgl_bayar_dt <= jt_limit_n else "Telat Bayar"
                
                jt_next_str = f"04 {target_bulan_lebih} {s_tahun_tagihan}"
                
                db.execute_query(query_ins, (
                    nis_f, data_utama['nama_santri'], sisa_tujuan,
                    target_bulan_lebih, jt_next_str, data_utama['tanggal_bayar'],
                    alokasi_n, sisa_akhir_n, 
                    "Lunas" if sisa_akhir_n == 0 else "Cicilan", ket_n
                ))

            st.success("Transaksi Berhasil Dicatat!")
            time.sleep(1)
            st.rerun()

    # --- SECTION KEDUA: TAMPILAN COMPACT NOTA ---
    if s_nama != "-- Pilih --":
        d = df_master[df_master['nama'] == s_nama].iloc[0]
        v_nis, v_spp_dasar = d['nis'], int(d['spp_tetap'])
        
        # Filter pencarian sisa tagihan sekarang menggunakan tahun periode yang dipilih
        q_sisa = f"SELECT sisa_tagihan FROM pembayaran_spp WHERE nis='{v_nis}' AND untuk_bulan='{s_bulan}' AND jatuh_tempo LIKE '%{s_tahun_tagihan}%' ORDER BY id DESC LIMIT 1"
        last_pay = db.fetch_data(q_sisa)
        
        v_sisa_sekarang = int(last_pay.iloc[0]['sisa_tagihan']) if not last_pay.empty else v_spp_dasar
        v_jt = f"04 {s_bulan} {s_tahun_tagihan}"

        # (Bagian CSS tetap sama...)
        st.markdown(f"""
            <div class="compact-nota">
                <p style="font-size: 0.9rem; font-weight: 700; margin-bottom: 8px;">DETAIL TAGIHAN PERIODE: {s_tahun_tagihan}</p>
                <div class="nota-grid">
                    <div>
                        <p class="nota-label">NAMA SANTRI</p>
                        <p class="nota-data">{s_nama}</p>
                        <p class="nota-label">JATUH TEMPO</p>
                        <p class="nota-data">{v_jt}</p>
                    </div>
                    <div>
                        <p class="nota-label">TAGIHAN DASAR</p>
                        <p class="nota-data">{format_rp(v_spp_dasar)}</p>
                        <p class="nota-label">SISA TAGIHAN ({s_bulan})</p>
                        <p class="nota-data" style="color:#f87171;">{format_rp(v_sisa_sekarang)}</p>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Form Input
        if v_sisa_sekarang > 0:
            with st.form("form_bayar_compact"):
                f1, f2 = st.columns(2)
                t_bayar = f1.date_input("Tanggal Bayar", datetime.now())
                n_bayar = f2.number_input("Nominal Pembayaran", min_value=0, step=10000)
                
                if st.form_submit_button("Proses Pembayaran", use_container_width=True):
                    if n_bayar <= 0:
                        st.error("Nominal tidak valid")
                    else:
                        f_bayar = min(n_bayar, v_sisa_sekarang)
                        f_lebih = max(0, n_bayar - v_sisa_sekarang)
                        f_sisa = max(0, v_sisa_sekarang - n_bayar)
                        
                        # Penentuan keterangan menggunakan tahun periode yang dipilih
                        jt_dt = datetime(s_tahun_tagihan, bulan_ind.index(s_bulan) + 1, 4).date()
                        
                        data_payload = {
                            'nis': v_nis, 'nama_santri': s_nama, 'tagihan_wajib': int(v_sisa_sekarang),
                            'untuk_bulan': s_bulan, 'jatuh_tempo': v_jt, 'tanggal_bayar': t_bayar.strftime('%Y-%m-%d'),
                            'nominal_bayar': int(f_bayar), 'sisa_tagihan': int(f_sisa),
                            'status': "Lunas" if f_sisa == 0 else "Cicilan",
                            'keterangan': "Tepat Waktu" if t_bayar <= jt_dt else "Telat Bayar"
                        }
                        konfirmasi_pembayaran_dialog(data_payload, int(f_lebih))
        else:
            st.success(f"Pembayaran {s_bulan} {s_tahun_tagihan} sudah Lunas.")

# --- 10. MODUL HISTORI TRANSAKSI (Filter Berdasarkan Waktu Pembayaran) ---
if menu == "Histori Transaksi":
    st.markdown("### 📜 Histori Transaksi Keseluruhan")
    st.markdown("<p style='font-size:0.9rem; color:#64748b;'>Menampilkan aliran kas berdasarkan <b>waktu pembayaran</b>.</p>", unsafe_allow_html=True)

    # Filter Periode Berdasarkan Tanggal Bayar
    current_year = datetime.now().year
    current_month_num = datetime.now().month 
    
    c1, c2, _ = st.columns([2, 1, 3])
    with c1:
        sel_bln_g = st.selectbox("Pilih Bulan Transaksi", bulan_ind, index=current_month_num - 1)
        bln_target = bulan_ind.index(sel_bln_g) + 1
    with c2:
        if not df_payment.empty:
            df_payment['tanggal_bayar'] = pd.to_datetime(df_payment['tanggal_bayar'], errors='coerce')
            list_tahun = sorted(df_payment['tanggal_bayar'].dt.year.dropna().unique().astype(int).tolist(), reverse=True)
            if current_year not in list_tahun: list_tahun.insert(0, current_year)
        else:
            list_tahun = [current_year, current_year + 1, current_year + 2]
        sel_thn_g = st.selectbox("Tahun", list_tahun)

    st.divider()

    if not df_payment.empty:
        # PEMICU FILTER: Berdasarkan tanggal asli uang masuk
        mask_g = (df_payment['tanggal_bayar'].dt.month == bln_target) & \
                 (df_payment['tanggal_bayar'].dt.year == sel_thn_g)
        
        df_display = df_payment[mask_g].copy().sort_values('tanggal_bayar', ascending=False)

        if not df_display.empty:
            # --- LOGIKA EKSTRAKSI TAHUN JATAH SPP ---
            # Mengambil tahun dari string jatuh_tempo (contoh: "04 Januari 2026" diambil "2026")
            df_display['periode_lengkap'] = df_display['untuk_bulan'] + " " + \
                                            df_display['jatuh_tempo'].str.split().str[-1]

            st.data_editor(
                df_display[["nama_santri", "tagihan_wajib", "tanggal_bayar", "nominal_bayar", "sisa_tagihan", "status", "keterangan"]],
                column_config={
                    "nama_santri": st.column_config.TextColumn("Nama Santri", width=200),
                    "periode_lengkap": st.column_config.TextColumn("tagihan_wajib", width=130), # Sekarang tampil: "Januari 2026"
                    "tanggal_bayar": st.column_config.DateColumn("Tgl Transaksi", format="DD/MM/YYYY", width=110),
                    "nominal_bayar": st.column_config.NumberColumn("Kas Masuk", format="Rp %d", width=120),
                    "sisa_tagihan": st.column_config.NumberColumn("Sisa Tagihan", format="Rp %d", width=120),
                    "status": "Status",
                    "keterangan": "Keterangan"
                },
                disabled=True,
                hide_index=True,
                use_container_width=True,
                key=f"global_history_v4_{bln_target}_{sel_thn_g}"
            )
            
            total_cash_in = df_display['nominal_bayar'].sum()
            st.success(f"💰 **Total Uang Masuk di {sel_bln_g} {sel_thn_g}: {format_rp(total_cash_in)}**")
        else:
            st.info(f"Tidak ada transaksi pada bulan {sel_bln_g} {sel_thn_g}.")
    else:
        st.warning("Database transaksi masih kosong.")

# --- 7. MODUL LAPORAN KEUANGAN ---
elif menu == "Laporan Keuangan":
    st.markdown("### Laporan & Monitoring Keuangan")
    st.markdown("<p style='font-size:0.9rem; color:#64748b;'>Pantau status kepatuhan tahunan dan kelola riwayat transaksi.</p>", unsafe_allow_html=True)
    
    # --- FITUR IMPORT CSV (Baru) ---
    with st.expander("📥 Import Data Transaksi dari CSV"):
        st.info("Pastikan kolom CSV Anda urut: NIS, Nama_Santri, Tagihan_Wajib, Untuk_Bulan, Tanggal_Bayar, Nominal_Bayar, Sisa_Tagihan, Status, Keterangan")
        uploaded_file = st.file_uploader("Pilih file CSV", type=["csv"])
        
        if uploaded_file is not None:
            try:
                df_import = pd.read_csv(uploaded_file)
                st.write("Preview Data:", df_import.head(3))
                
                if st.button("Konfirmasi Import Data"):
                    # Masukkan data ke MySQL
                    for _, row in df_import.iterrows():
                        query = """INSERT INTO pembayaran_spp 
                                   (nis, nama_santri, tagihan_wajib, untuk_bulan, tanggal_bayar, nominal_bayar, sisa_tagihan, status, keterangan) 
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                        db.execute_query(query, (
                            row['NIS'], row['Nama_Santri'], row['Tagihan_Wajib'], 
                            row['Untuk_Bulan'], row['Tanggal_Bayar'], row['Nominal_Bayar'], 
                            row['Sisa_Tagihan'], row['Status'], row['Keterangan']
                        ))
                    st.success(f"Berhasil mengimpor {len(df_import)} transaksi!")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"Gagal memproses file: {e}")


    # Konversi tanggal di awal agar aman dari AttributeError
    if not df_payment.empty:
        df_payment['tanggal_bayar'] = pd.to_datetime(df_payment['tanggal_bayar'], errors='coerce')
    
    # --- TOP CONTROL BAR ---
    with st.container():
        c_search, c_year, c_spacer = st.columns([3, 1, 2])
        with c_search:
            search_nama = st.selectbox("Pencarian Nama Santri", ["-- Pilih Nama Santri --"] + df_master['nama'].tolist(), label_visibility="collapsed")
        with c_year:
            current_year = datetime.now().year
            if not df_payment.empty:
                list_thn = sorted(df_payment['tanggal_bayar'].dt.year.dropna().unique().astype(int).tolist(), reverse=True)
                if current_year not in list_thn: list_thn.insert(0, current_year)
            else:
                list_thn = [current_year]
            sel_thn_lap = st.selectbox("Tahun", list_thn, label_visibility="collapsed")

    st.divider()

    if search_nama != "-- Pilih Nama Santri --":
        # Layout Two-Panel (1.5 : 3.5)
        col_monitor, col_history = st.columns([1.5, 3.5], gap="large")

        # --- PANEL KIRI: MONITORING CHECKLIST (TAMPILAN RAMPING) ---
        with col_monitor:
            st.markdown("##### Status Tahunan")
            d_s = df_master[df_master['nama'] == search_nama].iloc[0]
            v_nis_lap = d_s['nis']
            limit_bulan = datetime.now().month if sel_thn_lap == current_year else 12
            
            with st.container(border=True):
                for b in bulan_ind[:limit_bulan]:
                    if not df_payment.empty:
                        mask = (df_payment['nis'] == v_nis_lap) & \
                               (df_payment['untuk_bulan'] == b) & \
                               (df_payment['tanggal_bayar'].dt.year == sel_thn_lap)
                        cek_bayar = df_payment[mask]
                    else:
                        cek_bayar = pd.DataFrame()
                    
                    if cek_bayar.empty:
                        st_label, st_color = "Belum", "red"
                    else:
                        s_akhir = int(cek_bayar.iloc[-1]['sisa_tagihan'])
                        st_label, st_color = ("Lunas", "green") if s_akhir == 0 else ("Cicil", "orange")

                    m1, m2 = st.columns([2, 1.2])
                    m1.markdown(f"<p style='font-size:0.8rem; margin:0;'>{b}</p>", unsafe_allow_html=True)
                    m2.markdown(f"<div style='background-color:{st_color}; border-radius:4px; text-align:center; font-size:0.65rem; font-weight:700; padding:2px;'>{st_label}</div>", unsafe_allow_html=True)
                    st.markdown("<div style='margin:3px 0; border-bottom:1px solid #f8fafc;'></div>", unsafe_allow_html=True)

        # --- PANEL KANAN: RIWAYAT & AKSI (TERMASUK KOLOM KETERANGAN) ---
        with col_history:
            st.markdown(f"##### Riwayat Transaksi: {search_nama}")
            df_indiv = df_payment[df_payment['nama_santri'] == search_nama].sort_values('id', ascending=False)
            
            if not df_indiv.empty:
                df_indiv.insert(0, "Sel", False)
                # Menambahkan 'keterangan' ke dalam kolom yang ditampilkan
                cols_to_show = ["Sel", "untuk_bulan", "tanggal_bayar", "nominal_bayar", "sisa_tagihan", "status", "keterangan"]
                
                edited_df = st.data_editor(
                    df_indiv[cols_to_show],
                    column_config={
                        "Sel": st.column_config.CheckboxColumn("", width="small"),
                        "untuk_bulan": "Bulan",
                        "tanggal_bayar": st.column_config.DateColumn("Tgl"),
                        "nominal_bayar": st.column_config.NumberColumn("Nominal", format="Rp %d"),
                        "sisa_tagihan": st.column_config.NumberColumn("Sisa", format="Rp %d"),
                        "status": "Status",
                        "keterangan": "Keterangan" # Menampilkan Tepat Waktu / Telat Bayar
                    },
                    disabled=[c for c in cols_to_show if c != "Sel"],
                    hide_index=True,
                    use_container_width=True,
                    key=f"editor_final_{search_nama}"
                )

                selected_indices = edited_df[edited_df["Sel"] == True].index
                
                if not selected_indices.empty:
                    c_act1, c_act2 = st.columns([1, 4])
                    if c_act1.button("Hapus", type="primary", use_container_width=True):
                        for idx in selected_indices:
                            real_id = int(df_indiv.loc[idx, 'id'])
                            db.execute_query("DELETE FROM pembayaran_spp WHERE id=%s", (real_id,))
                        st.toast("Data Berhasil Dihapus")
                        time.sleep(0.5)
                        st.rerun()

                    if len(selected_indices) == 1:
                        st.markdown("<br>", unsafe_allow_html=True)
                        with st.container(border=True):
                            st.markdown("<p style='font-size:0.8rem; font-weight:600;'>Mode Edit Transaksi</p>", unsafe_allow_html=True)
                            r_edit = df_indiv.loc[selected_indices[0]]
                            with st.form("edit_form_final_v2"):
                                e1, e2 = st.columns(2)
                                n_n = e1.number_input("Nominal Baru", value=int(r_edit['nominal_bayar']), step=10000)
                                n_t = e2.date_input("Tanggal Baru", r_edit['tanggal_bayar'])
                                if st.form_submit_button("Update Data", use_container_width=True):
                                    # Hitung ulang sisa, status, dan keterangan
                                    sisa_n = max(0, int(r_edit['tagihan_wajib']) - n_n)
                                    stat_n = "Lunas" if sisa_n == 0 else "Cicilan"
                                    
                                    # Logika Keterangan: Batas Tanggal 4
                                    jt_bln = r_edit['untuk_bulan']
                                    jt_limit = datetime(n_t.year, bulan_ind.index(jt_bln)+1, 4).date()
                                    ket_n = "Tepat Waktu" if n_t <= jt_limit else "Telat Bayar"
                                    
                                    db.execute_query("UPDATE pembayaran_spp SET nominal_bayar=%s, tanggal_bayar=%s, sisa_tagihan=%s, status=%s, keterangan=%s WHERE id=%s", 
                                                   (int(n_n), n_t.strftime('%Y-%m-%d'), int(sisa_n), stat_n, ket_n, int(r_edit['id'])))
                                    st.toast("Data Berhasil Diperbarui")
                                    time.sleep(0.5)
                                    st.rerun()
            else:
                st.info("Belum ada riwayat transaksi.")
    else:
        st.info("Silakan pilih nama santri untuk melihat laporan.")    

# --- 8. MODUL MANAJEMEN USER ---
elif menu == "Manajemen User":
    st.markdown("### Manajemen Otoritas Pengguna")
    st.markdown("<p style='font-size:0.9rem; color:#64748b;'>Kelola otoritas akses sistem untuk Administrator, Bendahara, dan Pimpinan.</p>", unsafe_allow_html=True)

    # List Role sesuai permintaan terbaru
    LIST_ROLE = ["Administrator", "Bendahara", "Pimpinan"]

    # --- BAGIAN 1: FORM TAMBAH USER (TOGGLE) ---
    if "show_add_user" not in st.session_state:
        st.session_state.show_add_user = False

    c_btn, c_sp = st.columns([1.5, 4.5])
    if c_btn.button("+ Registrasi User" if not st.session_state.show_add_user else "Batalkan", use_container_width=True):
        st.session_state.show_add_user = not st.session_state.show_add_user
        st.rerun()

    if st.session_state.show_add_user:
        with st.container(border=True):
            st.markdown("<p style='font-size:0.85rem; font-weight:600;'>Registrasi Akun Baru</p>", unsafe_allow_html=True)
            with st.form("form_tambah_user_final", clear_on_submit=True):
                ca1, ca2 = st.columns(2)
                n_user = ca1.text_input("Username")
                n_nama = ca2.text_input("Nama Lengkap")
                n_pass = ca1.text_input("Password", type="password")
                n_role = ca2.selectbox("Tingkat Akses (Role)", LIST_ROLE)
                
                if st.form_submit_button("Simpan Pengguna", use_container_width=True):
                    if n_user and n_nama and n_pass:
                        q_user = "INSERT INTO database_users (username, password, role, nama_user) VALUES (%s, %s, %s, %s)"
                        if db.execute_query(q_user, (n_user, n_pass, n_role, n_nama)):
                            st.success(f"Akun {n_user} berhasil dibuat!")
                            st.session_state.show_add_user = False
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("Mohon lengkapi semua kolom input.")

    st.divider()

    df_u = db.fetch_data("SELECT * FROM database_users")
    
    if not df_u.empty:
        df_u.insert(0, "Pilih", False)
        display_cols = ["Pilih", "username", "nama_user", "role"]
        
        # PENGATURAN LEBAR KOLOM (width dalam pixel atau label)
        edited_u = st.data_editor(
            df_u[display_cols],
            column_config={
                # Kolom checkbox paling ramping (hanya kotak centang)
                "Pilih": st.column_config.CheckboxColumn("", width=40), 
                
                # Username dibuat mepet (misal 100px)
                "username": st.column_config.TextColumn("Username", width=100), 
                
                # Nama Pengguna diberikan sisa ruang lebih banyak
                "nama_user": st.column_config.TextColumn("Nama Pengguna", width=250),
                
                # Role dibuat pas dengan panjang kata
                "role": st.column_config.SelectboxColumn("Akses", options=LIST_ROLE, width=120) 
            },
            disabled=["username", "nama_user", "role"],
            hide_index=True,
            use_container_width=False, # Matikan ini jika ingin lebar kustom murni (tidak melar)
            key="user_table_v5"
        )

        selected_indices = edited_u[edited_u["Pilih"] == True].index

        if not selected_indices.empty:
            st.markdown("<br>", unsafe_allow_html=True)
            col_del, col_ed, col_fill = st.columns([1, 1, 4])
            
            # FITUR HAPUS
            if col_del.button("Hapus Akun", type="primary", use_container_width=True):
                for idx in selected_indices:
                    u_data = df_u.loc[idx]
                    # Proteksi sederhana agar tidak menghapus admin utama
                    if u_data['username'] == "admin": 
                        st.error("Akun Master Admin tidak dapat dihapus!")
                    else:
                        db.execute_query("DELETE FROM database_users WHERE id=%s", (int(u_data['id']),))
                st.rerun()

            # FITUR EDIT (PANEL DETIL)
            if len(selected_indices) == 1:
                st.markdown("---")
                idx_u = selected_indices[0]
                r_u = df_u.loc[idx_u]
                
                with st.container(border=True):
                    st.markdown(f"##### ✏️ Update Akun: {r_u['username']}")
                    with st.form("edit_user_final_v3"):
                        e_u1, e_u2 = st.columns(2)
                        up_u = e_u1.text_input("Username", value=r_u['username'])
                        up_n = e_u2.text_input("Nama Lengkap", value=r_u['nama_user'])
                        up_p = e_u1.text_input("Password Baru", value=r_u['password'], type="password")
                        up_r = e_u2.selectbox("Role", LIST_ROLE, index=LIST_ROLE.index(r_u['role']))
                        
                        if st.form_submit_button("Simpan Perubahan", use_container_width=True):
                            q_up = "UPDATE database_users SET username=%s, nama_user=%s, password=%s, role=%s WHERE id=%s"
                            db.execute_query(q_up, (up_u, up_n, up_p, up_r, int(r_u['id'])))
                            st.success("Perubahan kredensial berhasil disimpan!")
                            time.sleep(1)
                            st.rerun()
    else:
        st.info("Database user kosong.")

# --- 9. MODUL ANALISIS AI (Final Security Patch) ---
elif menu == "Analisis AI":
    st.markdown("### 🤖 ML-Powered Financial Analysis")
    
    # Inisialisasi Engine
    engine = AIEngine(df_payment, df_master)
    metrics = engine.get_financial_metrics()

    # TAHAP 1: Validasi Metrics
    if metrics is None:
        st.info("💡 **Informasi:** Data transaksi belum mencukupi untuk dianalisis oleh AI. Silakan lakukan input data pembayaran terlebih dahulu.")
    else:
        # TAHAP 2: Jika metrics ada, baru tampilkan Dashboard Utama
        m1, m2, m3 = st.columns(3)
        m1.metric("Collection Rate", f"{metrics['rate']}%")
        m2.metric("Total Outstanding", format_rp(metrics['tunggakan']))
        m3.metric("Indeks Telat", f"{metrics['telat_count']} Transaksi")

        st.divider()
        
        # TAHAP 3: Jalankan Analisis Random Forest
        analysis_result = engine.run_random_forest_analysis()
        
        if analysis_result is not None:
            col_tabel, col_config = st.columns([3, 2], gap="medium")
            
            with col_tabel:
                st.markdown("##### 🚩 Prediksi Profil Risiko")
                st.data_editor(
                    analysis_result[['nama', 'risk_score', 'risk_level']].sort_values('risk_score', ascending=False),
                    column_config={
                        "nama": st.column_config.TextColumn("Nama Santri", width=220),
                        "risk_score": st.column_config.ProgressColumn("Skor Risiko", min_value=0, max_value=1, format="%.2f"),
                        "risk_level": st.column_config.TextColumn("Level", width=80)
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="ml_risk_table_final_v2"
                )

            with col_config:
                st.markdown("##### ⚙️ Parameter & Manfaat")
                new_threshold = st.slider("Ambang Batas (Threshold)", 0.0, 1.0, 0.6, 0.05)
                engine.threshold = new_threshold
                
                high_risk_count = len(analysis_result[analysis_result['risk_score'] >= new_threshold])
                st.warning(f"Terdeteksi **{high_risk_count}** santri di atas ambang batas.")
                
                # --- INFORMASI MANFAAT HASIL ANALISIS ---
            with st.expander("❓ Manfaat Analisis Ini", expanded=True):
                st.markdown("""
                Hasil analisis **Random Forest** ini memberikan wawasan strategis:
                * **Early Warning System**: Mendeteksi potensi gagal bayar berdasarkan pola historis.
                * **Prioritas Kerja**: Bendahara fokus pada santri dengan Skor Risiko tertinggi.
                * **Simulasi Kebijakan**: Pimpinan dapat mengatur ambang batas toleransi piutang.
                * **Stabilitas Kas**: Proyeksi dana operasional melalui Collection Rate yang akurat.
                """)

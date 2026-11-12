# ============================================================
# INTERNAL AUDIT AI
# Aplikasi Audit Internal Berbantuan Google Gemini
# Politeknik Negeri Bengkalis
# ============================================================

import io
import json
import re
from datetime import datetime

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# 1. KONFIGURASI HALAMAN
# ------------------------------------------------------------

st.set_page_config(
    page_title="Internal Audit AI",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------
# 2. TEMA DAN CSS
# ------------------------------------------------------------

st.markdown(
    """
    <style>
        .stApp {
            background-color: #f4f7fb;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #102a43 0%, #163f63 100%);
        }
        [data-testid="stSidebar"] * {
            color: #ffffff !important;
        }
        .main-title {
            color: #123653;
            font-size: 2rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
        }
        .main-subtitle {
            color: #58738a;
            font-size: 1rem;
            margin-bottom: 1.2rem;
        }
        .section-card {
            background: #ffffff;
            border: 1px solid #dce6ef;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 12px;
        }
        div.stButton > button,
        div.stDownloadButton > button {
            border-radius: 8px;
            font-weight: 600;
        }
        div.stButton > button[kind="primary"] {
            background-color: #1677b8;
            border-color: #1677b8;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# 3. KONSTANTA DAN MENU
# ------------------------------------------------------------

APP_NAME = "Internal Audit AI"
MODEL_NAME = "gemini-2.5-flash"

MENU_ITEMS = [
    "Dashboard",
    "Audit Transaksi",
    "Audit Pengendalian Internal",
    "Audit SOP",
    "Audit Persediaan",
    "Laporan Audit",
    "Data & Dokumen",
    "Analisis Data",
    "Pengaturan",
]

# ------------------------------------------------------------
# 4. SESSION STATE
# ------------------------------------------------------------

if "latest_report" not in st.session_state:
    st.session_state.latest_report = ""

if "history" not in st.session_state:
    st.session_state.history = []

if "report_review" not in st.session_state:
    st.session_state.report_review = "Belum Direview"

if "last_dataframe" not in st.session_state:
    st.session_state.last_dataframe = None

if "last_dataframe_name" not in st.session_state:
    st.session_state.last_dataframe_name = ""

if "audit_count" not in st.session_state:
    st.session_state.audit_count = 0

# ------------------------------------------------------------
# 5. FUNGSI KONFIGURASI GEMINI
# ------------------------------------------------------------

def get_api_key():
    """Mengambil API key dari Streamlit Secrets tanpa menampilkannya."""
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


def ask_gemini(prompt):
    """Mengirim prompt ke Google Gemini dan mengembalikan teks jawaban."""
    api_key = get_api_key()

    if not api_key:
        return (
            "GEMINI_API_KEY belum ditemukan.\n\n"
            "Silakan tambahkan API key melalui Streamlit Cloud: "
            "App Settings → Secrets dengan format:\n\n"
            'GEMINI_API_KEY = "API_KEY_ANDA"\n\n'
            "Jangan menuliskan API key di dalam app.py atau membagikannya "
            "kepada orang lain."
        )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )

        result = getattr(response, "text", None)
        if result:
            return result

        return "Gemini tidak memberikan teks jawaban. Silakan coba kembali."

    except ImportError:
        return (
            "Library google-genai belum terpasang. Tambahkan "
            "'google-genai' pada requirements.txt lalu deploy ulang."
        )
    except Exception as error:
        return (
            "Terjadi kendala saat menghubungi Google Gemini.\n\n"
            f"Detail kendala: {error}\n\n"
            "Periksa API key, kuota API, koneksi, dan nama model."
        )


# ------------------------------------------------------------
# 6. FUNGSI PENGOLAHAN FILE
# ------------------------------------------------------------

def read_table_file(uploaded_file):
    """Membaca file CSV atau Excel menjadi DataFrame."""
    file_name = uploaded_file.name.lower()

    try:
        if file_name.endswith(".csv"):
            try:
                return pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding="latin-1")

        if file_name.endswith((".xlsx", ".xls")):
            return pd.read_excel(uploaded_file)

        raise ValueError("Format file harus CSV, XLSX, atau XLS.")

    except Exception as error:
        st.error(f"File gagal dibaca: {error}")
        return None


def dataframe_summary(df):
    """Membuat ringkasan data untuk ditampilkan dan dianalisis."""
    if df is None or df.empty:
        return "Data kosong atau tidak dapat dibaca."

    buffer = io.StringIO()
    df.head(30).to_csv(buffer, index=False)

    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    missing = df.isna().sum()
    missing = missing[missing > 0].to_dict()

    summary = {
        "jumlah_baris": int(len(df)),
        "jumlah_kolom": int(len(df.columns)),
        "nama_kolom": [str(col) for col in df.columns],
        "kolom_numerik": [str(col) for col in numeric_columns],
        "nilai_kosong_per_kolom": {
            str(key): int(value) for key, value in missing.items()
        },
        "contoh_data_maksimal_30_baris": buffer.getvalue(),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


def extract_document_text(uploaded_file):
    """Mengambil teks dari TXT, PDF, atau DOCX."""
    file_name = uploaded_file.name.lower()

    try:
        if file_name.endswith(".txt"):
            raw = uploaded_file.getvalue()
            for encoding in ("utf-8", "latin-1"):
                try:
                    return raw.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")

        if file_name.endswith(".pdf"):
            from pypdf import PdfReader

            reader = PdfReader(uploaded_file)
            pages = []
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                pages.append(f"[Halaman {page_number}]\n{text}")
            return "\n\n".join(pages)

        if file_name.endswith(".docx"):
            from docx import Document

            document = Document(uploaded_file)
            return "\n".join(
                paragraph.text
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            )

        raise ValueError("Format dokumen harus PDF, DOCX, atau TXT.")

    except ImportError as error:
        return (
            "Library untuk membaca dokumen belum tersedia. "
            f"Periksa requirements.txt. Detail: {error}"
        )
    except Exception as error:
        return f"Dokumen gagal dibaca: {error}"


def add_history(file_name, category, status="Diproses"):
    """Mencatat file yang diproses pada sesi aplikasi."""
    st.session_state.history.append(
        {
            "Waktu": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "Nama File": file_name,
            "Jenis Pemeriksaan": category,
            "Status": status,
        }
    )


def save_report(report, file_name=""):
    """Menyimpan hasil pemeriksaan terakhir pada session state."""
    st.session_state.latest_report = report
    st.session_state.audit_count += 1
    if file_name:
        st.session_state.last_dataframe_name = file_name


# ------------------------------------------------------------
# 7. FUNGSI PROMPT AUDIT
# ------------------------------------------------------------

def build_data_audit_prompt(category, df, additional_instruction=""):
    summary = dataframe_summary(df)

    return f"""
Anda berperan sebagai asisten auditor internal untuk membantu pemeriksaan awal.
Lakukan analisis secara objektif, hati-hati, dan berbasis data yang diberikan.

JENIS PEMERIKSAAN:
{category}

DATA:
{summary}

INSTRUKSI TAMBAHAN:
{additional_instruction if additional_instruction else "Tidak ada."}

SUSUN HASIL DENGAN FORMAT:
1. Ringkasan pemeriksaan
2. Gambaran data yang diperiksa
3. Indikasi anomali atau red flags
4. Temuan awal dan bukti data yang mendukung
5. Risiko yang mungkin timbul
6. Rekomendasi prosedur pemeriksaan lanjutan
7. Keterbatasan analisis

Ketentuan:
- Jangan mengarang angka, transaksi, dokumen, atau bukti.
- Jika data tidak cukup, nyatakan data yang masih diperlukan.
- Bedakan indikasi risiko dengan bukti kecurangan.
- Jangan menyimpulkan seseorang melakukan kecurangan tanpa bukti memadai.
- Hasil AI adalah pemeriksaan awal dan wajib divalidasi auditor.
"""


# ------------------------------------------------------------
# 8. HEADER DAN SIDEBAR
# ------------------------------------------------------------

with st.sidebar:
    st.markdown("## 🔎 Internal Audit AI")
    st.caption("Sistem Pemeriksaan Internal Berbantuan AI")
    st.divider()

    menu = st.radio(
        "Navigasi Menu",
        MENU_ITEMS,
        key="main_menu",
    )

    st.divider()
    st.caption("Politeknik Negeri Bengkalis")
    st.caption("Versi aplikasi 1.1")


# ------------------------------------------------------------
# 9. DASHBOARD
# ------------------------------------------------------------

if menu == "Dashboard":
    st.markdown(
        '<div class="main-title">Dashboard Internal Audit AI</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="main-subtitle">'
        "Platform pemeriksaan awal untuk membantu proses audit internal."
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Pemeriksaan Dilakukan", st.session_state.audit_count)
    with col2:
        st.metric("Dokumen Diproses", len(st.session_state.history))
    with col3:
        report_status = (
            "Tersedia" if st.session_state.latest_report else "Belum tersedia"
        )
        st.metric("Laporan Terakhir", report_status)

    st.subheader("Fitur Sistem")
    feature_columns = st.columns(2)

    with feature_columns[0]:
        st.markdown(
            """
            **📊 Audit Transaksi**

            Memeriksa data transaksi dari file Excel atau CSV untuk
            menemukan pola tidak wajar dan potensi red flags.

            **🛡️ Audit Pengendalian Internal**

            Mengevaluasi jawaban checklist pengendalian internal dan
            memberikan rekomendasi perbaikan.

            **📄 Audit SOP**

            Membantu menelaah dokumen SOP dan mengidentifikasi
            ketidaksesuaian atau bagian yang perlu diperjelas.
            """
        )

    with feature_columns[1]:
        st.markdown(
            """
            **📦 Audit Persediaan**

            Membantu menganalisis data persediaan, saldo, pergerakan,
            dan indikasi ketidakwajaran.

            **📑 Laporan Audit**

            Menampilkan, meninjau, dan mengunduh hasil pemeriksaan.

            **📁 Data & Dokumen**

            Menampilkan riwayat file yang telah diproses selama sesi.
            """
        )

    st.info(
        "Catatan: Internal Audit AI merupakan alat bantu pemeriksaan awal. "
        "Keputusan dan kesimpulan audit tetap menjadi tanggung jawab auditor."
    )


# ------------------------------------------------------------
# 10. AUDIT TRANSAKSI
# ------------------------------------------------------------

elif menu == "Audit Transaksi":
    st.title("💳 Audit Transaksi")
    st.write(
        "Unggah data transaksi dalam format Excel atau CSV untuk "
        "diperiksa menggunakan analisis data dan AI."
    )

    uploaded_file = st.file_uploader(
        "Pilih file transaksi",
        type=["csv", "xlsx", "xls"],
        key="transaction_upload",
    )

    if uploaded_file is not None:
        df = read_table_file(uploaded_file)

        if df is not None:
            st.session_state.last_dataframe = df
            st.session_state.last_dataframe_name = uploaded_file.name

            st.subheader("Pratinjau Data Transaksi")
            st.dataframe(df.head(100), use_container_width=True)

            col1, col2, col3 = st.columns(3)
            col1.metric("Jumlah Baris", len(df))
            col2.metric("Jumlah Kolom", len(df.columns))
            col3.metric("Nilai Kosong", int(df.isna().sum().sum()))

            additional_instruction = st.text_area(
                "Fokus pemeriksaan (opsional)",
                placeholder=(
                    "Contoh: periksa transaksi bernilai besar, "
                    "tanggal ganda, nilai negatif, atau pola tidak wajar."
                ),
                key="transaction_instruction",
            )

            if st.button(
                "🤖 Mulai Audit Transaksi",
                type="primary",
                key="run_transaction_audit",
            ):
                with st.spinner("Gemini sedang menganalisis data transaksi..."):
                    prompt = build_data_audit_prompt(
                        "Audit Transaksi",
                        df,
                        additional_instruction,
                    )
                    result = ask_gemini(prompt)
                    save_report(result, uploaded_file.name)
                    add_history(uploaded_file.name, "Audit Transaksi")
                st.success("Pemeriksaan transaksi selesai.")
                st.rerun()


# ------------------------------------------------------------
# 11. AUDIT PENGENDALIAN INTERNAL
# ------------------------------------------------------------

elif menu == "Audit Pengendalian Internal":
    st.title("🛡️ Audit Pengendalian Internal")
    st.write(
        "Isi checklist berikut sesuai kondisi pengendalian internal "
        "yang ditemukan. Jawaban digunakan sebagai bahan evaluasi awal."
    )

    control_questions = [
        (
            "Apakah perusahaan memiliki struktur organisasi dan pembagian "
            "wewenang yang jelas?"
        ),
        (
            "Apakah setiap transaksi memperoleh persetujuan dari pihak "
            "yang berwenang?"
        ),
        (
            "Apakah tugas pencatatan, penyimpanan aset, dan otorisasi "
            "dipisahkan?"
        ),
        (
            "Apakah dokumen transaksi disimpan secara tertib dan mudah "
            "ditelusuri?"
        ),
        (
            "Apakah rekonsiliasi kas dan bank dilakukan secara berkala?"
        ),
        (
            "Apakah persediaan diperiksa secara fisik dan dibandingkan "
            "dengan catatan?"
        ),
        (
            "Apakah akses terhadap sistem dan data dibatasi sesuai "
            "kewenangan?"
        ),
        (
            "Apakah terdapat mekanisme pelaporan penyimpangan atau "
            "kecurangan?"
        ),
        (
            "Apakah evaluasi dan pemantauan pengendalian dilakukan "
            "secara berkala?"
        ),
    ]

    with st.form("internal_control_form"):
        answers = {}
        for index, question in enumerate(control_questions, start=1):
            answers[question] = st.radio(
                f"{index}. {question}",
                ["Ya", "Tidak", "Tidak Diketahui"],
                horizontal=True,
                key=f"control_{index}",
            )

        notes = st.text_area(
            "Catatan atau bukti pendukung",
            placeholder="Tuliskan kondisi, dokumen, atau bukti yang ditemukan.",
        )
        submitted = st.form_submit_button(
            "🤖 Evaluasi Pengendalian Internal",
            type="primary",
        )

    if submitted:
        answer_text = "\n".join(
            f"- {question}: {answer}"
            for question, answer in answers.items()
        )

        prompt = f"""
Anda berperan sebagai asisten auditor internal.
Evaluasi checklist pengendalian internal berikut secara objektif.

JAWABAN CHECKLIST:
{answer_text}

CATATAN / BUKTI PENDUKUNG:
{notes if notes.strip() else "Tidak ada catatan tambahan."}

Buat hasil dengan susunan:
1. Ringkasan kondisi pengendalian internal
2. Area pengendalian yang telah berjalan
3. Kelemahan atau area yang perlu diperbaiki
4. Risiko yang mungkin timbul
5. Rekomendasi perbaikan
6. Bukti tambahan yang perlu diminta auditor

Jangan menganggap jawaban "Ya" sebagai bukti yang cukup tanpa verifikasi.
Bedakan antara jawaban responden dan bukti audit. Jangan mengarang fakta.
Hasil ini merupakan evaluasi awal dan wajib divalidasi auditor.
"""
        with st.spinner("Gemini sedang mengevaluasi checklist..."):
            result = ask_gemini(prompt)
            save_report(result)
            add_history("Checklist Pengendalian Internal", "Audit Pengendalian Internal")
        st.success("Evaluasi pengendalian internal selesai.")
        st.rerun()


# ------------------------------------------------------------
# 12. AUDIT SOP
# ------------------------------------------------------------

elif menu == "Audit SOP":
    st.title("📄 Audit SOP")
    st.write(
        "Unggah dokumen SOP untuk ditelaah. Sistem akan membantu "
        "mengidentifikasi kejelasan prosedur, tanggung jawab, dan risiko."
    )

    sop_file = st.file_uploader(
        "Unggah dokumen SOP",
        type=["pdf", "docx", "txt"],
        key="sop_upload",
    )

    if sop_file is not None:
        document_text = extract_document_text(sop_file)

        if document_text.startswith("Dokumen gagal dibaca:") or document_text.startswith(
            "Library untuk membaca"
        ):
            st.error(document_text)
        else:
            st.subheader("Pratinjau Isi Dokumen")
            st.text_area(
                "Teks dokumen (pratinjau)",
                value=document_text[:12000],
                height=250,
                disabled=True,
            )

            sop_focus = st.text_area(
                "Fokus telaah (opsional)",
                placeholder=(
                    "Contoh: kesesuaian tahapan, pembagian tugas, "
                    "otorisasi, dan dokumentasi."
                ),
                key="sop_focus",
            )

            if st.button(
                "🤖 Mulai Audit SOP",
                type="primary",
                key="run_sop_audit",
            ):
                prompt = f"""
Anda adalah asisten auditor internal yang membantu menelaah SOP.

ISI DOKUMEN SOP:
{document_text[:25000]}

FOKUS TAMBAHAN:
{sop_focus if sop_focus.strip() else "Telaah secara umum."}

Susun hasil:
1. Ringkasan SOP
2. Tujuan dan ruang lingkup yang dapat diidentifikasi
3. Kejelasan peran dan tanggung jawab
4. Kejelasan tahapan prosedur
5. Pengendalian dan dokumentasi
6. Potensi kelemahan atau risiko
7. Rekomendasi perbaikan
8. Bagian yang perlu dikonfirmasi kepada pemilik proses

Jangan mengarang isi dokumen. Jika informasi tidak tercantum,
nyatakan bahwa informasi tersebut tidak ditemukan dalam dokumen.
Hasil merupakan telaah awal, bukan pengesahan kepatuhan.
"""
                with st.spinner("Gemini sedang menelaah dokumen SOP..."):
                    result = ask_gemini(prompt)
                    save_report(result, sop_file.name)
                    add_history(sop_file.name, "Audit SOP")
                st.success("Telaah SOP selesai.")
                st.rerun()


# ------------------------------------------------------------
# 13. AUDIT PERSEDIAAN
# ------------------------------------------------------------

elif menu == "Audit Persediaan":
    st.title("📦 Audit Persediaan")
    st.write(
        "Unggah data persediaan untuk membantu pemeriksaan saldo, "
        "pergerakan barang, dan indikasi ketidakwajaran."
    )

    inventory_file = st.file_uploader(
        "Pilih file persediaan",
        type=["csv", "xlsx", "xls"],
        key="inventory_upload",
    )

    if inventory_file is not None:
        inventory_df = read_table_file(inventory_file)

        if inventory_df is not None:
            st.session_state.last_dataframe = inventory_df
            st.session_state.last_dataframe_name = inventory_file.name

            st.subheader("Pratinjau Data Persediaan")
            st.dataframe(inventory_df.head(100), use_container_width=True)

            col1, col2, col3 = st.columns(3)
            col1.metric("Jumlah Baris", len(inventory_df))
            col2.metric("Jumlah Kolom", len(inventory_df.columns))
            col3.metric(
                "Nilai Kosong",
                int(inventory_df.isna().sum().sum()),
            )

            inventory_focus = st.text_area(
                "Fokus pemeriksaan (opsional)",
                placeholder=(
                    "Contoh: stok negatif, barang tidak bergerak, "
                    "selisih kuantitas, atau nilai persediaan tidak wajar."
                ),
                key="inventory_focus",
            )

            if st.button(
                "🤖 Mulai Audit Persediaan",
                type="primary",
                key="run_inventory_audit",
            ):
                with st.spinner("Gemini sedang menganalisis persediaan..."):
                    prompt = build_data_audit_prompt(
                        "Audit Persediaan",
                        inventory_df,
                        inventory_focus,
                    )
                    result = ask_gemini(prompt)
                    save_report(result, inventory_file.name)
                    add_history(inventory_file.name, "Audit Persediaan")
                st.success("Pemeriksaan persediaan selesai.")
                st.rerun()


# ------------------------------------------------------------
# 14. LAPORAN AUDIT
# ------------------------------------------------------------

elif menu == "Laporan Audit":
    st.title("📑 Laporan Audit")
    st.write(
        "Berikut merupakan hasil pemeriksaan awal yang dihasilkan "
        "oleh AI Agent dan perlu ditinjau auditor."
    )

    if st.session_state.latest_report:
        st.subheader("Hasil Pemeriksaan")
        st.markdown(st.session_state.latest_report)
        st.divider()

        st.subheader("Review Auditor")
        persetujuan = st.radio(
            "Status Review",
            [
                "Belum Direview",
                "Disetujui Auditor",
                "Perlu Revisi",
            ],
            key="report_review",
        )
        st.write("Status:", persetujuan)

        st.download_button(
            "⬇️ Download Laporan Audit",
            data=st.session_state.latest_report,
            file_name="laporan_audit.txt",
            mime="text/plain",
        )
    else:
        st.info(
            "Belum ada hasil pemeriksaan. Silakan lakukan audit "
            "terlebih dahulu."
        )


# ------------------------------------------------------------
# 15. DATA & DOKUMEN
# ------------------------------------------------------------

elif menu == "Data & Dokumen":
    st.title("📁 Data & Dokumen")
    st.write("Riwayat file yang diproses selama sesi aplikasi ini.")

    if st.session_state.history:
        history_df = pd.DataFrame(st.session_state.history).iloc[::-1]
        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Belum terdapat dokumen atau pemeriksaan yang diproses.")


# ------------------------------------------------------------
# 16. ANALISIS DATA
# ------------------------------------------------------------

elif menu == "Analisis Data":
    st.title("📊 Analisis Data")

    if st.session_state.last_dataframe is not None:
        df = st.session_state.last_dataframe

        st.write(
            f"Data terakhir yang diproses: "
            f"**{st.session_state.last_dataframe_name or 'Data'}**"
        )
        st.dataframe(df.head(100), use_container_width=True)

        st.subheader("Statistik Deskriptif")
        numeric_df = df.select_dtypes(include="number")

        if not numeric_df.empty:
            st.dataframe(
                numeric_df.describe().T,
                use_container_width=True,
            )
        else:
            st.info("Tidak ditemukan kolom numerik pada data terakhir.")

        st.subheader("Informasi Data")
        info_col1, info_col2, info_col3 = st.columns(3)
        info_col1.metric("Jumlah Baris", len(df))
        info_col2.metric("Jumlah Kolom", len(df.columns))
        info_col3.metric("Sel Kosong", int(df.isna().sum().sum()))

        st.subheader("Hasil Pemeriksaan AI Terakhir")
        if st.session_state.latest_report:
            st.markdown(st.session_state.latest_report)
        else:
            st.info("Belum tersedia hasil analisis AI.")
    else:
        st.info(
            "Belum ada data yang diproses. Silakan unggah file melalui "
            "menu Audit Transaksi atau Audit Persediaan."
        )


# ------------------------------------------------------------
# 17. PENGATURAN
# ------------------------------------------------------------

elif menu == "Pengaturan":
    st.title("⚙️ Pengaturan")
    st.subheader("Informasi Sistem")

    st.info(APP_NAME)
    st.write("Versi: 1.1")
    st.write("AI Engine: Google Gemini")
    st.write("Model: Gemini 2.5 Flash")
    st.write("Framework: Streamlit")
    st.write("Institusi: Politeknik Negeri Bengkalis")

    if get_api_key():
        st.success("Konfigurasi Gemini API Key terdeteksi.")
    else:
        st.warning(
            "Gemini API Key belum ditemukan. Atur GEMINI_API_KEY "
            "melalui Streamlit Cloud → App settings → Secrets."
        )

    st.markdown("**Format Secrets:**")
    st.code('GEMINI_API_KEY = "MASUKKAN_API_KEY_ANDA"', language="toml")

    st.caption(
        "Jangan memasukkan API key ke dalam app.py atau mengunggahnya "
        "ke repositori GitHub."
    )
    st.caption(
        "Sistem ini dikembangkan untuk project akademik. Seluruh hasil "
        "AI merupakan analisis awal dan wajib divalidasi auditor."
    )


# ------------------------------------------------------------
# 18. FOOTER
# ------------------------------------------------------------

st.divider()
st.caption(
    "Internal Audit AI | Politeknik Negeri Bengkalis | "
    "Hasil AI wajib ditinjau dan divalidasi auditor."
)

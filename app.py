import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from ytmusicapi import YTMusic
import pandas as pd
import time
import json
import re

# ==========================================
# 1. KONFIGURASI HALAMAN & LAYOUT STREAMLIT
# ==========================================
st.set_page_config(
    page_title="Spotify to YouTube Music Converter",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# 2. PROTEKSI AKSES (PASSWORD GATEKEEPER)
# ==========================================
def check_password():
    """
    Sistem autentikasi sederhana menggunakan st.session_state dan st.secrets["APP_PASSWORD"].
    Mengembalikan True jika pengguna telah berhasil login.
    """
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    # Jika sudah terautentikasi dalam sesi ini, langsung lewati
    if st.session_state["authenticated"]:
        return True

    # Mengambil password dari st.secrets jika tersedia
    app_password = st.secrets.get("APP_PASSWORD", None)

    # Tampilan UI Login Gatekeeper
    st.markdown("<h2 style='text-align: center;'>🔒 Akses Terbatas (Password Gatekeeper)</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888;'>Masukkan password untuk mengakses aplikasi konversi playlist.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not app_password:
            st.warning("⚠️ `APP_PASSWORD` belum diset di `.streamlit/secrets.toml`. Silakan masukkan password sementara di bawah ini untuk masuk.")
            user_input = st.text_input("Password Sementara", type="password", key="login_pass_input")
            if st.button("Masuk Aplikasi", use_container_width=True):
                if user_input.strip() != "":
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Password tidak boleh kosong.")
        else:
            user_input = st.text_input("Password Aplikasi", type="password", key="login_pass_input")
            if st.button("Masuk Aplikasi", use_container_width=True):
                if user_input == app_password:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("❌ Password salah! Silakan periksa kembali.")

    return False

# Jalankan pemeriksa password. Jika belum terautentikasi, hentikan eksekusi skrip di sini.
if not check_password():
    st.stop()


# ==========================================
# 3. FUNGSI HELPER & LOGIKA IN-MEMORY
# ==========================================

def extract_spotify_playlist_id(url_or_id: str) -> str:
    """
    Mengekstrak Playlist ID dari URL Spotify, URI, atau string biasa.
    Contoh URL: https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=xxx
    """
    url_or_id = url_or_id.strip()
    match = re.search(r"playlist[/:]([a-zA-Z0-9]{22})", url_or_id)
    if match:
        return match.group(1)
    if len(url_or_id) == 22 and url_or_id.isalnum():
        return url_or_id
    return url_or_id


def fetch_all_spotify_tracks(sp: spotipy.Spotify, playlist_id: str):
    """
    Mengambil SELURUH lagu dari playlist Spotify (termasuk pagination untuk 2.000+ lagu).
    Mengembalikan metadata playlist dan daftar lagu terstruktur.
    """
    # Ambil info dasar playlist
    playlist_info = sp.playlist(playlist_id, fields="name,description,tracks.total")
    
    tracks_data = []
    results = sp.playlist_items(playlist_id, additional_types=['track'])
    
    while results:
        for item in results.get('items', []):
            track = item.get('track')
            if track and track.get('name'):
                track_name = track['name']
                # Gabungkan nama-nama artis
                artists = ", ".join([artist['name'] for artist in track.get('artists', []) if 'name' in artist])
                album_name = track.get('album', {}).get('name', '')
                
                # Query pencarian YouTube Music yang dioptimalkan
                search_query = f"{track_name} {artists}".strip()
                
                tracks_data.append({
                    "title": track_name,
                    "artist": artists,
                    "album": album_name,
                    "query": search_query
                })
        
        # Penanganan pagination (jika ada halaman berikutnya)
        if results.get('next'):
            results = sp.next(results)
        else:
            results = None
            
    return playlist_info, tracks_data


def init_ytmusic_from_string(auth_json_str: str) -> YTMusic:
    """
    Inisialisasi instance YTMusic dari string JSON autentikasi tanpa menyimpan file ke disk.
    Mendukung format headers_auth.json maupun oauth.json.
    """
    auth_data = json.loads(auth_json_str)
    # ytmusicapi dapat menerima string JSON atau dictionary langsung untuk autentikasi in-memory
    if isinstance(auth_data, dict):
        return YTMusic(auth=json.dumps(auth_data))
    return YTMusic(auth=auth_json_str)


# ==========================================
# 4. SIDEBAR & INFORMASI SESI
# ==========================================
with st.sidebar:
    st.title("🎵 Settings & Sesi")
    st.success("🔓 Terautentikasi (Pass Gatekeeper)")
    
    if st.button("🚪 Logout / Keluar Sesi", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state.clear()
        st.rerun()
        
    st.divider()
    st.markdown("### ℹ️ Petunjuk ytmusicapi")
    st.markdown(
        "Untuk mendapatkan kredensial YouTube Music (`headers_auth.json` atau `oauth.json`):\n"
        "1. Jalankan `ytmusicapi setup` di terminal lokal Anda, ATAU\n"
        "2. Ambil Request Headers dari browser (Developer Tools -> Network tab -> request ke music.youtube.com -> Copy Request Headers).\n"
        "3. Unggah file JSON atau tempel (paste) isinya di kolom yang disediakan."
    )


# ==========================================
# 5. ANTARMUKA UTAMA APLIKASI
# ==========================================
st.title("🚀 Spotify to YouTube Music Converter")
st.caption("Pindahkan playlist Spotify favorit Anda ke YouTube Music dengan aman, cepat, dan terisolasi per sesi pengguna.")

# Tab antarmuka
tab_setup, tab_convert = st.tabs(["1. Konfigurasi Input & Autentikasi", "2. Eksekusi Pemindahan Playlist"])

# --- TAB 1: KONFIGURASI INPUT & AUTENTIKASI ---
with tab_setup:
    st.subheader("🔑 1. Spotify API Credentials")
    
    # Ambil credentials dari secrets jika ada
    secret_client_id = st.secrets.get("SPOTIPY_CLIENT_ID", "")
    secret_client_secret = st.secrets.get("SPOTIPY_CLIENT_SECRET", "")
    
    col_sp1, col_sp2 = st.columns(2)
    with col_sp1:
        client_id = st.text_input(
            "Spotify Client ID", 
            value=secret_client_id, 
            type="password" if secret_client_id else "default",
            help="Diambil otomatis dari secrets.toml jika tersedia."
        )
    with col_sp2:
        client_secret = st.text_input(
            "Spotify Client Secret", 
            value=secret_client_secret, 
            type="password" if secret_client_secret else "default",
            help="Diambil otomatis dari secrets.toml jika tersedia."
        )

    st.divider()
    st.subheader("🔴 2. Autentikasi YouTube Music (In-Memory)")
    st.info("Kredensial YouTube Music Anda diproses secara langsung di sesi ini (`st.session_state`) dan TIDAK disimpan di disk server.")

    auth_method = st.radio(
        "Pilih Metode Input Autentikasi YT Music:",
        ["Unggah File (headers_auth.json / oauth.json)", "Tempel (Paste) String JSON"],
        horizontal=True
    )

    yt_auth_json_content = None

    if auth_method == "Unggah File (headers_auth.json / oauth.json)":
        uploaded_file = st.file_uploader("Pilih file JSON autentikasi YT Music", type=["json"])
        if uploaded_file is not None:
            try:
                yt_auth_json_content = uploaded_file.getvalue().decode("utf-8")
            except Exception as e:
                st.error(f"Gagal membaca file uploaded: {e}")
    else:
        json_pasted = st.text_area(
            "Tempelkan isi file JSON auth di sini:",
            height=180,
            placeholder='{\n  "User-Agent": "...",\n  "Accept": "*/*",\n  "Accept-Language": "...",\n  "Authorization": "SAPISIDHASH ...",\n  "Cookie": "..."\n}'
        )
        if json_pasted.strip():
            yt_auth_json_content = json_pasted.strip()

    # Tombol Verifikasi YouTube Music Auth
    if yt_auth_json_content:
        try:
            ytmusic_instance = init_ytmusic_from_string(yt_auth_json_content)
            st.session_state["ytmusic"] = ytmusic_instance
            st.success("✅ Autentikasi YouTube Music Berhasil Ditautkan ke Sesi!")
        except Exception as e:
            st.session_state["ytmusic"] = None
            st.error(f"❌ Autentikasi YouTube Music Gagal: {e}")

    st.divider()
    st.subheader("📋 3. Input Playlist Spotify")
    spotify_url_input = st.text_input(
        "Link / URL Playlist Spotify", 
        placeholder="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    )

    if st.button("🔍 Muat Data Playlist Spotify", type="primary"):
        if not client_id or not client_secret:
            st.error("Masukkan Spotify Client ID dan Client Secret terlebih dahulu.")
        elif not spotify_url_input:
            st.error("Masukkan URL / Link Playlist Spotify.")
        else:
            with st.spinner("Mengambil daftar lagu dari Spotify..."):
                try:
                    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
                    sp = spotipy.Spotify(auth_manager=auth_manager)
                    
                    playlist_id = extract_spotify_playlist_id(spotify_url_input)
                    playlist_info, tracks_data = fetch_all_spotify_tracks(sp, playlist_id)
                    
                    st.session_state["spotify_playlist_info"] = playlist_info
                    st.session_state["spotify_tracks"] = tracks_data
                    st.success(f"✅ Berhasil memuat {len(tracks_data)} lagu dari playlist '{playlist_info.get('name')}'!")
                except Exception as e:
                    st.error(f"Gagal mengambil data dari Spotify: {e}")

    # Tampilkan preview jika data sudah dimuat
    if "spotify_tracks" in st.session_state and st.session_state["spotify_tracks"]:
        tracks = st.session_state["spotify_tracks"]
        playlist_name = st.session_state["spotify_playlist_info"].get("name", "Spotify Playlist")
        st.markdown(f"#### Preview Playlist: **{playlist_name}** ({len(tracks)} lagu)")
        df_preview = pd.DataFrame(tracks)[["title", "artist", "album"]]
        st.dataframe(df_preview.head(50), use_container_width=True)
        if len(tracks) > 50:
            st.caption(f"...dan {len(tracks) - 50} lagu lainnya.")


# --- TAB 2: EKSEKUSI PEMINDAHAN PLAYLIST ---
with tab_convert:
    st.subheader("⚡ Eksekusi & Konversi Playlist")

    # Cek prasyarat sebelum memulai
    ytmusic_ready = st.session_state.get("ytmusic") is not None
    spotify_ready = "spotify_tracks" in st.session_state and len(st.session_state["spotify_tracks"]) > 0

    if not spotify_ready:
        st.warning("⚠️ Silakan muat data playlist Spotify terlebih dahulu di Tab 1.")
    if not ytmusic_ready:
        st.warning("⚠️ Silakan selesaikan autentikasi YouTube Music di Tab 1.")

    if spotify_ready and ytmusic_ready:
        default_name = st.session_state["spotify_playlist_info"].get("name", "Imported Spotify Playlist")
        default_desc = f"Diimpor dari Spotify ({len(st.session_state['spotify_tracks'])} lagu)"

        col_cfg1, col_cfg2 = st.columns(2)
        with col_cfg1:
            target_playlist_title = st.text_input("Judul Playlist YouTube Music Baru", value=default_name)
        with col_cfg2:
            privacy_status = st.selectbox("Status Privasi Playlist", ["PRIVATE", "PUBLIC", "UNLISTED"])

        target_playlist_desc = st.text_area("Deskripsi Playlist", value=default_desc, height=70)
        
        batch_size = st.slider("Ukuran Batch Penambahan Lagu (Recommended: 50)", min_value=10, max_value=100, value=50, step=10)

        st.divider()

        if st.button("🚀 Mulai Proses Pemindahan Playlist", type="primary", use_container_width=True):
            ytmusic: YTMusic = st.session_state["ytmusic"]
            spotify_tracks = st.session_state["spotify_tracks"]
            total_tracks = len(spotify_tracks)

            st.info(f"Mulai membuat playlist **'{target_playlist_title}'** di YouTube Music...")

            # 1. Buat playlist baru di YouTube Music
            try:
                new_playlist_id = ytmusic.create_playlist(
                    title=target_playlist_title,
                    description=target_playlist_desc,
                    privacy_status=privacy_status
                )
                st.success(f"✅ Playlist baru berhasil dibuat! ID: `{new_playlist_id}`")
            except Exception as e:
                st.error(f"❌ Gagal membuat playlist di YouTube Music: {e}")
                st.stop()

            # 2. Inisialisasi Progress Bar & Kontainer Status Real-time
            progress_bar = st.progress(0.0)
            status_text = st.empty()
            
            successful_video_ids = []
            failed_tracks = []
            current_batch = []
            
            success_count = 0
            fail_count = 0

            # 3. Iterasi Pemrosesan Lagu dengan Batching & Error Handling
            for idx, track in enumerate(spotify_tracks):
                track_title = track["title"]
                track_artist = track["artist"]
                query = track["query"]

                # Update tampilan status real-time
                status_text.markdown(f"⌛ Processing ({idx+1}/{total_tracks}): **{track_title}** - *{track_artist}*")

                try:
                    # Pencarian lagu di YouTube Music
                    search_results = ytmusic.search(query=query, filter="songs")
                    
                    if search_results and len(search_results) > 0:
                        video_id = search_results[0].get("videoId")
                        if video_id:
                            current_batch.append(video_id)
                            success_count += 1
                        else:
                            fail_count += 1
                            failed_tracks.append({
                                "title": track_title,
                                "artist": track_artist,
                                "reason": "videoId tidak ditemukan pada hasil pencarian"
                            })
                    else:
                        fail_count += 1
                        failed_tracks.append({
                            "title": track_title,
                            "artist": track_artist,
                            "reason": "Lagu tidak ditemukan di YouTube Music"
                        })
                except Exception as e:
                    fail_count += 1
                    failed_tracks.append({
                        "title": track_title,
                        "artist": track_artist,
                        "reason": f"Error pencarian: {str(e)}"
                    })

                # Jeda rate-limiting (0.3 detik per request agar IP server aman)
                time.sleep(0.3)

                # Kirim batch jika sudah mencapai batch_size atau lagu terakhir
                if len(current_batch) >= batch_size or (idx == total_tracks - 1 and len(current_batch) > 0):
                    try:
                        ytmusic.add_playlist_items(new_playlist_id, current_batch)
                        current_batch = []
                    except Exception as e:
                        # Jika batch gagal, catat error
                        st.warning(f"⚠️ Gagal menambahkan batch {len(current_batch)} lagu: {e}")
                        current_batch = []

                # Update progress bar
                progress_bar.progress((idx + 1) / total_tracks)

            # Pemrosesan selesai
            status_text.success("🎉 Pemrosesan Playlist Selesai!")

            # 4. Ringkasan & Hasil Statistik
            st.divider()
            st.subheader("📊 Hasil & Ringkasan Konversi")

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Lagu", total_tracks)
            col_m2.metric("Berhasil Ditemukan", success_count)
            col_m3.metric("Gagal / Tidak Ditemukan", fail_count)

            # Tampilkan link ke playlist YouTube Music
            yt_playlist_link = f"https://music.youtube.com/playlist?list={new_playlist_id}"
            st.markdown(f"🔗 **[Klik di sini untuk membuka Playlist di YouTube Music]({yt_playlist_link})**")

            # 5. Tabel Log Lagu Gagal & Download CSV
            if failed_tracks:
                st.subheader("⚠️ Log Lagu yang Gagal Ditambahkan")
                df_failed = pd.DataFrame(failed_tracks)
                st.dataframe(df_failed, use_container_width=True)

                # Tombol unduh file CSV
                csv_data = df_failed.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Unduh Log Gagal sebagai File CSV",
                    data=csv_data,
                    file_name="spotify_to_ytmusic_failed_log.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.balloons()
                st.success("✨ Semua lagu berhasil dipindahkan tanpa ada yang gagal!")

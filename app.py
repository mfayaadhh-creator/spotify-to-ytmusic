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
    """
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    app_password = st.secrets.get("APP_PASSWORD", None)

    st.markdown("<h2 style='text-align: center;'>🔒 Akses Terbatas (Password Gatekeeper)</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888;'>Masukkan password untuk mengakses aplikasi konversi playlist.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if not app_password:
            st.warning("⚠️ `APP_PASSWORD` belum diset di `.streamlit/secrets.toml`. Masukkan password sementara untuk masuk.")
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

if not check_password():
    st.stop()


# ==========================================
# 3. FUNGSI HELPER & PARSER IN-MEMORY
# ==========================================

def extract_spotify_playlist_id(url_or_id: str) -> str:
    """Eksktrak Playlist ID dari URL Spotify."""
    url_or_id = url_or_id.strip()
    match = re.search(r"playlist[/:]([a-zA-Z0-9]{22})", url_or_id)
    if match:
        return match.group(1)
    if len(url_or_id) == 22 and url_or_id.isalnum():
        return url_or_id
    return url_or_id


def fetch_all_spotify_tracks(sp: spotipy.Spotify, playlist_id: str):
    """Mengambil seluruh lagu dari playlist Spotify (Pagination 2.000+ lagu)."""
    playlist_info = sp.playlist(playlist_id, fields="name,description,tracks.total")
    tracks_data = []
    results = sp.playlist_items(playlist_id, additional_types=['track'])
    
    while results:
        for item in results.get('items', []):
            track = item.get('track')
            if track and track.get('name'):
                track_name = track['name']
                artists = ", ".join([artist['name'] for artist in track.get('artists', []) if 'name' in artist])
                album_name = track.get('album', {}).get('name', '')
                search_query = f"{track_name} {artists}".strip()
                
                tracks_data.append({
                    "title": track_name,
                    "artist": artists,
                    "album": album_name,
                    "query": search_query
                })
        
        if results.get('next'):
            results = sp.next(results)
        else:
            results = None
            
    return playlist_info, tracks_data


def parse_raw_headers_to_dict(raw_headers_text: str) -> dict:
    """
    Parser universal untuk men-decode JSON, Raw Headers, cURL Command, atau fetch() JavaScript.
    """
    headers = {}

    # 1. Cek apakah format cURL (misal: Copy as cURL (cmd / bash / powershell))
    curl_matches = re.findall(r"(?:-H|--header)\s+['\"]([^'\"]+)['\"]", raw_headers_text, re.IGNORECASE)
    if curl_matches:
        for item in curl_matches:
            if ":" in item:
                k, v = item.split(":", 1)
                headers[k.strip()] = v.strip()
        if headers:
            return headers

    # 2. Cek format Raw Headers biasa (baris per baris Key: Value)
    lines = raw_headers_text.strip().splitlines()
    for line in lines:
        if ":" in line:
            line_clean = line.lstrip()
            if line_clean.startswith(":") or line_clean.startswith("-H") or line_clean.startswith("curl"):
                continue
            key, val = line_clean.split(":", 1)
            headers[key.strip()] = val.strip()
            
    return headers


def init_ytmusic_from_any_input(auth_input: str) -> YTMusic:
    """Inisialisasi YTMusic dari JSON String, cURL Copy, atau Raw Browser Headers."""
    auth_input = auth_input.strip()
    
    # Coba parse sebagai JSON
    if auth_input.startswith("{"):
        try:
            auth_dict = json.loads(auth_input)
            return YTMusic(auth=json.dumps(auth_dict))
        except Exception:
            pass

    # Parse cURL / Raw Headers
    headers_dict = parse_raw_headers_to_dict(auth_input)
    if "cookie" in [k.lower() for k in headers_dict.keys()] or "authorization" in [k.lower() for k in headers_dict.keys()]:
        return YTMusic(auth=json.dumps(headers_dict))
    
    return YTMusic(auth=auth_input)


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
    st.markdown("### 💡 Cara Termudah Login YT Music")
    st.markdown(
        "**Tanpa buat file JSON!**\n"
        "1. Buka [music.youtube.com](https://music.youtube.com) (sudah login Google).\n"
        "2. Tekan **F12** (Developer Tools) -> Tab **Network**.\n"
        "3. Klik kanan request `browse` -> **Copy** -> **Copy as cURL (bash / cmd)**.\n"
        "4. Paste di kolom *Tempel Request Headers / cURL*."
    )


# ==========================================
# 5. ANTARMUKA UTAMA APLIKASI
# ==========================================
st.title("🚀 Spotify to YouTube Music Converter")
st.caption("Pindahkan playlist Spotify favorit Anda ke YouTube Music dengan mudah dan cepat.")

tab_setup, tab_convert = st.tabs(["1. Konfigurasi Input & Autentikasi", "2. Eksekusi Pemindahan Playlist"])

# --- TAB 1: KONFIGURASI INPUT & AUTENTIKASI ---
with tab_setup:
    st.subheader("📋 1. Input Link Playlist Spotify")

    secret_client_id = st.secrets.get("SPOTIPY_CLIENT_ID", "")
    secret_client_secret = st.secrets.get("SPOTIPY_CLIENT_SECRET", "")

    if secret_client_id and secret_client_secret:
        client_id = secret_client_id
        client_secret = secret_client_secret
        st.success("⚡ Spotify API Credentials otomatis dimuat dari sistem.")
    else:
        st.info("ℹ️ Spotify API Credentials belum diset di secrets.toml. Masukkan manual di bawah ini jika diperlukan:")
        col_sp1, col_sp2 = st.columns(2)
        with col_sp1:
            client_id = st.text_input("Spotify Client ID", type="password")
        with col_sp2:
            client_secret = st.text_input("Spotify Client Secret", type="password")

    spotify_url_input = st.text_input(
        "Link / URL Playlist Spotify Public", 
        placeholder="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    )

    if st.button("🔍 Muat Data Playlist Spotify", type="primary"):
        if not client_id or not client_secret:
            st.error("Spotify Client ID dan Client Secret belum dikonfigurasi.")
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

    if "spotify_tracks" in st.session_state and st.session_state["spotify_tracks"]:
        tracks = st.session_state["spotify_tracks"]
        playlist_name = st.session_state["spotify_playlist_info"].get("name", "Spotify Playlist")
        st.markdown(f"#### Preview Playlist: **{playlist_name}** ({len(tracks)} lagu)")
        df_preview = pd.DataFrame(tracks)[["title", "artist", "album"]]
        st.dataframe(df_preview.head(30), use_container_width=True)

    st.divider()
    st.subheader("🔴 2. Autentikasi YouTube Music")

    auth_method = st.radio(
        "Pilih Metode Autentikasi YT Music:",
        ["Tempel (Paste) Request Headers / cURL / JSON (Paling Praktis)", "Unggah File (headers_auth.json / oauth.json)"],
        horizontal=True
    )

    yt_auth_content = None

    if auth_method == "Tempel (Paste) Request Headers / cURL / JSON (Paling Praktis)":
        raw_headers_pasted = st.text_area(
            "Tempelkan cURL / Request Headers di sini:",
            height=200,
            placeholder="Pilih 'Copy as cURL (bash)' di browser DevTools lalu paste seluruh isinya di sini..."
        )
        if raw_headers_pasted.strip():
            yt_auth_content = raw_headers_pasted.strip()
    else:
        uploaded_file = st.file_uploader("Pilih file JSON autentikasi YT Music", type=["json"])
        if uploaded_file is not None:
            try:
                yt_auth_content = uploaded_file.getvalue().decode("utf-8")
            except Exception as e:
                st.error(f"Gagal membaca file: {e}")

    if yt_auth_content:
        try:
            ytmusic_instance = init_ytmusic_from_any_input(yt_auth_content)
            st.session_state["ytmusic"] = ytmusic_instance
            st.success("✅ Autentikasi YouTube Music Berhasil Ditautkan ke Sesi!")
        except Exception as e:
            st.session_state["ytmusic"] = None
            st.error(f"❌ Autentikasi YouTube Music Gagal: {e}")


# --- TAB 2: EKSEKUSI PEMINDAHAN PLAYLIST ---
with tab_convert:
    st.subheader("⚡ Eksekusi & Konversi Playlist")

    ytmusic_ready = st.session_state.get("ytmusic") is not None
    spotify_ready = "spotify_tracks" in st.session_state and len(st.session_state["spotify_tracks"]) > 0

    if not spotify_ready:
        st.warning("⚠️ Silakan muat data playlist Spotify di Tab 1 terlebih dahulu.")
    if not ytmusic_ready:
        st.warning("⚠️ Silakan lengkapi autentikasi YouTube Music di Tab 1.")

    if spotify_ready and ytmusic_ready:
        default_name = st.session_state["spotify_playlist_info"].get("name", "Imported Spotify Playlist")
        default_desc = f"Diimpor dari Spotify ({len(st.session_state['spotify_tracks'])} lagu)"

        col_cfg1, col_cfg2 = st.columns(2)
        with col_cfg1:
            target_playlist_title = st.text_input("Judul Playlist YouTube Music Baru", value=default_name)
        with col_cfg2:
            privacy_status = st.selectbox("Status Privasi Playlist", ["PRIVATE", "PUBLIC", "UNLISTED"])

        target_playlist_desc = st.text_area("Deskripsi Playlist", value=default_desc, height=70)
        batch_size = st.slider("Ukuran Batch (Recommended: 50)", min_value=10, max_value=100, value=50, step=10)

        st.divider()

        if st.button("🚀 Mulai Pemindahan ke YouTube Music", type="primary", use_container_width=True):
            ytmusic: YTMusic = st.session_state["ytmusic"]
            spotify_tracks = st.session_state["spotify_tracks"]
            total_tracks = len(spotify_tracks)

            st.info(f"Membuat playlist **'{target_playlist_title}'** di YouTube Music...")

            try:
                new_playlist_id = ytmusic.create_playlist(
                    title=target_playlist_title,
                    description=target_playlist_desc,
                    privacy_status=privacy_status
                )
                st.success(f"✅ Playlist baru dibuat! ID: `{new_playlist_id}`")
            except Exception as e:
                st.error(f"❌ Gagal membuat playlist: {e}")
                st.stop()

            progress_bar = st.progress(0.0)
            status_text = st.empty()
            
            failed_tracks = []
            current_batch = []
            success_count = 0
            fail_count = 0

            for idx, track in enumerate(spotify_tracks):
                track_title = track["title"]
                track_artist = track["artist"]
                query = track["query"]

                status_text.markdown(f"⌛ Processing ({idx+1}/{total_tracks}): **{track_title}** - *{track_artist}*")

                try:
                    search_results = ytmusic.search(query=query, filter="songs")
                    if search_results and len(search_results) > 0:
                        video_id = search_results[0].get("videoId")
                        if video_id:
                            current_batch.append(video_id)
                            success_count += 1
                        else:
                            fail_count += 1
                            failed_tracks.append({"title": track_title, "artist": track_artist, "reason": "videoId tidak ditemukan"})
                    else:
                        fail_count += 1
                        failed_tracks.append({"title": track_title, "artist": track_artist, "reason": "Lagu tidak ditemukan di YouTube Music"})
                except Exception as e:
                    fail_count += 1
                    failed_tracks.append({"title": track_title, "artist": track_artist, "reason": f"Error: {str(e)}"})

                time.sleep(0.3)

                if len(current_batch) >= batch_size or (idx == total_tracks - 1 and len(current_batch) > 0):
                    try:
                        ytmusic.add_playlist_items(new_playlist_id, current_batch)
                        current_batch = []
                    except Exception as e:
                        st.warning(f"⚠️ Gagal menambahkan batch: {e}")
                        current_batch = []

                progress_bar.progress((idx + 1) / total_tracks)

            status_text.success("🎉 Pemrosesan Selesai!")

            st.divider()
            st.subheader("📊 Hasil & Ringkasan Konversi")
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Lagu", total_tracks)
            col_m2.metric("Berhasil Ditemukan", success_count)
            col_m3.metric("Gagal / Tidak Ditemukan", fail_count)

            yt_playlist_link = f"https://music.youtube.com/playlist?list={new_playlist_id}"
            st.markdown(f"🔗 **[Buka Playlist di YouTube Music]({yt_playlist_link})**")

            if failed_tracks:
                st.subheader("⚠️ Log Lagu Gagal Ditambahkan")
                df_failed = pd.DataFrame(failed_tracks)
                st.dataframe(df_failed, use_container_width=True)
                csv_data = df_failed.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Unduh Log Gagal (CSV)",
                    data=csv_data,
                    file_name="spotify_to_ytmusic_failed_log.csv",
                    mime="text/csv"
                )
            else:
                st.balloons()
                st.success("✨ Semua lagu berhasil dipindahkan!")

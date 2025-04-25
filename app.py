from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
import requests
import time
from urllib.parse import urlencode
from datetime import datetime, timezone

# Cargar variables de entorno desde .env
load_dotenv()

# Inicialización de la aplicación Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['SESSION_COOKIE_SECURE'] = True

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuración de Spotify
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_AUTH_URL = os.getenv("SPOTIFY_AUTH_URL")
SPOTIFY_TOKEN_URL = os.getenv("SPOTIFY_TOKEN_URL")
SPOTIFY_API_BASE_URL = os.getenv("SPOTIFY_API_BASE_URL")

# Lista estática de géneros soportados por Spotify (como respaldo)
SPOTIFY_SUPPORTED_GENRES = [
    "acoustic", "afrobeat", "alt-rock", "alternative", "ambient", "anime", "black-metal", "bluegrass", "blues",
    "bossanova", "brazil", "breakbeat", "british", "cantopop", "chicago-house", "children", "chill", "classical",
    "club", "comedy", "country", "dance", "dancehall", "death-metal", "deep-house", "detroit-techno", "disco",
    "disney", "drum-and-bass", "dub", "dubstep", "edm", "electro", "electronic", "emo", "folk", "forro", "french",
    "funk", "garage", "german", "gospel", "goth", "grindcore", "groove", "grunge", "guitar", "happy", "hard-rock",
    "hardcore", "hardstyle", "heavy-metal", "hip-hop", "holidays", "honky-tonk", "house", "idm", "indian", "indie",
    "indie-pop", "industrial", "iranian", "j-dance", "j-idol", "j-pop", "j-rock", "jazz", "k-pop", "kids", "latin",
    "latino", "malay", "mandopop", "metal", "metal-misc", "metalcore", "minimal-techno", "movies", "mpb", "new-age",
    "new-release", "opera", "pagode", "party", "philippines-opm", "piano", "pop", "pop-film", "post-dubstep",
    "power-pop", "progressive-house", "psych-rock", "punk", "punk-rock", "r-n-b", "rainy-day", "reggae", "reggaeton",
    "road-trip", "rock", "rock-n-roll", "rockabilly", "romance", "sad", "salsa", "samba", "sertanejo", "show-tunes",
    "singer-songwriter", "ska", "sleep", "songwriter", "soul", "soundtracks", "spanish", "study", "summer", "swedish",
    "synth-pop", "tango", "techno", "trance", "trip-hop", "turkish", "work-out", "world-music"
]

# --- Helper Functions ---

def refresh_spotify_token():
    if 'refresh_token' not in session:
        return False
    
    refresh_url = 'https://accounts.spotify.com/api/token'
    refresh_data = {
        'grant_type': 'refresh_token',
        'refresh_token': session['refresh_token'],
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    }
    
    response = requests.post(refresh_url, data=refresh_data)
    if response.status_code == 200:
        token_data = response.json()
        session['spotify_token'] = token_data['access_token']
        session['token_expires_at'] = int(time.time()) + token_data['expires_in']
        if 'refresh_token' in token_data:
            session['refresh_token'] = token_data['refresh_token']
        return True
    else:
        print(f"Error al refrescar el token: {response.status_code}, {response.text}")
        return False

def get_spotify_genres(token):
    headers = {'Authorization': f'Bearer {token}'}
    url = f'{SPOTIFY_API_BASE_URL}recommendations/available-genre-seeds'
    print(f"Intentando obtener géneros de Spotify desde: {url}")
    response = requests.get(url, headers=headers)
    print(f"Respuesta de Spotify: {response.status_code}, {response.text}")
    if response.status_code == 200:
        return response.json()['genres']
    else:
        print(f"Error al obtener géneros de Spotify: {response.status_code}, {response.text}")
        return SPOTIFY_SUPPORTED_GENRES

# --- Middleware ---

@app.before_request
def before_request():
    if 'spotify_token' in session and 'token_expires_at' in session:
        if int(time.time()) > session['token_expires_at'] - 300:  # Refrescar 5 minutos antes de que expire
            refresh_spotify_token()

# --- Core Routes ---

@app.route('/')
def index():
    preview_songs = [
        {
            'title': 'Stairway to Heaven',
            'artist': 'Led Zeppelin',
            'image_url': 'https://picsum.photos/300/200?random=1',
            'embed_url': 'https://open.spotify.com/embed/track/5CQ30WqJwcep0pYcV4AMNc?utm_source=generator'
        },
        {
            'title': 'Bohemian Rhapsody',
            'artist': 'Queen',
            'image_url': 'https://picsum.photos/300/200?random=2',
            'embed_url': 'https://open.spotify.com/embed/track/1AhDOtG9vPSOmsWgNW0BEY?utm_source=generator'
        },
        {
            'title': 'Sweet Child O\' Mine',
            'artist': 'Guns N\' Roses',
            'image_url': 'https://picsum.photos/300/200?random=3',
            'embed_url': 'https://open.spotify.com/embed/track/7o2CTH4ctstm8TNelqjb51?utm_source=generator'
        }
    ]
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('tunings.html', preview_songs=preview_songs)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    comment_success = request.args.get('comment_success', default=False, type=bool)
    comment_error = request.args.get('comment_error', default=None, type=str)
    playlist_success = request.args.get('playlist_success', default=False, type=bool)
    playlist_error = request.args.get('playlist_error', default=None, type=str)
    
    playlists_response = supabase.table('playlists').select('*').eq('user_id', session['user_id']).execute()
    playlists = playlists_response.data if playlists_response.data else []
    
    for playlist in playlists:
        playlist['created_at'] = datetime.fromisoformat(playlist['created_at'].replace('Z', '+00:00'))
    
    history_response = supabase.table('listening_history').select('*').eq('user_id', session['user_id']).order('listened_at', desc=True).limit(3).execute()
    listening_history = history_response.data if history_response.data else []
    for entry in listening_history:
        entry['listened_at'] = datetime.fromisoformat(entry['listened_at'].replace('Z', '+00:00'))
    
    user_response = supabase.table('users').select('music_genre').eq('user_id', session['user_id']).execute()
    music_genre = user_response.data[0]['music_genre'] if user_response.data and user_response.data[0]['music_genre'] else 'pop'
    
    recommended_songs = []
    admin_playlist_songs = []
    
    admin_playlist_id = '0QGY1uzNgID0ul2jqczpEN'
    if 'spotify_token' in session:
        token = session['spotify_token']
        headers = {'Authorization': f'Bearer {token}'}
        
        playlist_response = requests.get(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, params={'limit': 10})
        print(f"Prueba /v1/playlists/{admin_playlist_id}/tracks: {playlist_response.status_code}, {playlist_response.text}")
        
        if playlist_response.status_code == 200:
            tracks = playlist_response.json()['items']
            for item in tracks:
                track = item['track']
                admin_playlist_songs.append({
                    'title': track['name'],
                    'artist': track['artists'][0]['name'],
                    'image_url': track['album']['images'][0]['url'] if track['album']['images'] else 'https://picsum.photos/300/200?random=1',
                    'uri': track['uri'],
                    'embed_url': f"https://open.spotify.com/embed/track/{track['uri'].split(':')[-1]}"
                })
            print(f"Canciones de la playlist del administrador: {admin_playlist_songs}")
        else:
            print(f"Error al obtener canciones de la playlist del administrador: {playlist_response.status_code}, {playlist_response.text}")
    
    if 'spotify_token' in session and music_genre:
        token = session['spotify_token']
        headers = {'Authorization': f'Bearer {token}'}
        
        user_response = requests.get(f'{SPOTIFY_API_BASE_URL}me', headers=headers)
        print(f"Prueba /v1/me: {user_response.status_code}, {user_response.text}")
        
        if user_response.status_code == 200:
            market = user_response.json().get('country', 'US')
            print(f"Mercado del usuario: {market}")
            
            user_genre = music_genre.lower().replace('&', 'and').replace(',', '').replace(' ', '-')
            print(f"Usando género: {user_genre}")
            
            print("Obteniendo recomendaciones con /v1/me/top/tracks...")
            top_tracks_response = requests.get(f'{SPOTIFY_API_BASE_URL}me/top/tracks', headers=headers, params={'limit': 10, 'time_range': 'medium_term'})
            print(f"Prueba /v1/me/top/tracks: {top_tracks_response.status_code}, {top_tracks_response.text}")
            
            if top_tracks_response.status_code == 200:
                tracks = top_tracks_response.json()['items']
                if tracks:
                    filtered_tracks = []
                    for track in tracks:
                        artist_id = track['artists'][0]['id']
                        artist_response = requests.get(f'{SPOTIFY_API_BASE_URL}artists/{artist_id}', headers=headers)
                        print(f"Prueba /v1/artists/{artist_id}: {artist_response.status_code}, {artist_response.text}")
                        if artist_response.status_code == 200:
                            artist_genres = artist_response.json().get('genres', [])
                            if user_genre in [genre.replace(' ', '-') for genre in artist_genres]:
                                filtered_tracks.append(track)
                                if len(filtered_tracks) >= 3:
                                    break
                    if len(filtered_tracks) < 3:
                        filtered_tracks = tracks[:3]
                    recommended_songs = [
                        {
                            'title': track['name'],
                            'artist': track['artists'][0]['name'],
                            'image_url': track['album']['images'][0]['url'] if track['album']['images'] else 'https://picsum.photos/300/200?random=1',
                            'uri': track['uri'],
                            'embed_url': f"https://open.spotify.com/embed/track/{track['uri'].split(':')[-1]}"
                        }
                        for track in filtered_tracks
                    ]
                else:
                    print("No se encontraron pistas principales para el usuario.")
            else:
                print(f"Error al obtener pistas principales: {top_tracks_response.status_code}, {top_tracks_response.text}")
        else:
            print(f"Error al obtener información del usuario: {user_response.status_code}, {user_response.text}")
    else:
        print("Falta el token de Spotify o el género musical")
    
    if not recommended_songs:
        recommended_songs = admin_playlist_songs if admin_playlist_songs else [
            {"title": "Sweet Child O' Mine", "artist": "Guns N' Roses", "image_url": "https://picsum.photos/300/200?random=1", "uri": "spotify:track:7o2CTH4ctstm8TNelqjb51", "embed_url": "https://open.spotify.com/embed/track/7o2CTH4ctstm8TNelqjb51"},
            {"title": "Billie Jean", "artist": "Michael Jackson", "image_url": "https://picsum.photos/300/200?random=2", "uri": "spotify:track:5ChkMS8OtdzJeqyybCc9R5", "embed_url": "https://open.spotify.com/embed/track/5ChkMS8OtdzJeqyybCc9R5"},
            {"title": "Stairway to Heaven", "artist": "Led Zeppelin", "image_url": "https://picsum.photos/300/200?random=3", "uri": "spotify:track:5CQ30WqJwcep0pYcV4AMNc", "embed_url": "https://open.spotify.com/embed/track/5CQ30WqJwcep0pYcV4AMNc"},
        ]
    
    return render_template('dashboard.html', playlists=playlists, recommended_songs=recommended_songs, 
                        admin_playlist_songs=admin_playlist_songs, listening_history=listening_history,
                        comment_success=comment_success, comment_error=comment_error,
                        playlist_success=playlist_success, playlist_error=playlist_error)

# --- Authentication Routes ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        music_genre = request.form['music_genre']
        password = request.form['password']
        
        response = supabase.table('users').select('email').eq('email', email).execute()
        print(f"Response from Supabase: {response.data}")
        if response.data and len(response.data) > 0:
            print("Correo duplicado encontrado")
            return render_template('register.html', error="El correo ya está registrado")
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        
        try:
            user_id = str(uuid.uuid4())
            supabase.table('users').insert({
                'email': email,
                'name': name,
                'music_genre': music_genre,
                'password': hashed_password,
                'role': 2,  # Rol por defecto: usuario normal
                'user_id': user_id
            }).execute()
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Error al registrar usuario: {e}")
            return render_template('register.html', error=f"Error al registrarse: {str(e)}")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        response = supabase.table('users').select('*').eq('email', email).execute()
        
        if response.data and len(response.data) > 0:
            user = response.data[0]
            if check_password_hash(user['password'], password):
                session['user_id'] = str(user['user_id'])
                session['user_name'] = user['name']
                session['role'] = user['role']
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error="Contraseña incorrecta")
        else:
            return render_template('login.html', error="Usuario no encontrado")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- Spotify Authentication Routes ---

@app.route('/login-spotify')
def login_spotify():
    auth_params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'scope': 'user-read-private user-read-email user-top-read playlist-modify-public playlist-modify-private streaming user-read-playback-state user-modify-playback-state',
        'show_dialog': 'true'
    }
    auth_url = f"{SPOTIFY_AUTH_URL}?{urlencode(auth_params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('dashboard', error='No se recibió el código de autorización de Spotify'))
    
    token_url = 'https://accounts.spotify.com/api/token'
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    }
    
    response = requests.post(token_url, data=token_data)
    if response.status_code == 200:
        token_info = response.json()
        session['spotify_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['token_expires_at'] = int(time.time()) + token_info['expires_in']
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('dashboard', error='Error al obtener el token de Spotify'))

# --- Spotify Interaction Routes ---

@app.route('/search_songs', methods=['GET'])
def search_songs():
    if 'user_id' not in session or 'spotify_token' not in session:
        return jsonify({'error': 'Usuario no autenticado o Spotify no conectado'}), 401
    
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'Falta el término de búsqueda'}), 400
    
    token = session['spotify_token']
    headers = {'Authorization': f'Bearer {token}'}
    params = {
        'q': query,
        'type': 'track',
        'limit': 10
    }
    
    search_response = requests.get(f'{SPOTIFY_API_BASE_URL}search', headers=headers, params=params)
    if search_response.status_code == 200:
        tracks = search_response.json()['tracks']['items']
        results = [
            {
                'title': track['name'],
                'artist': track['artists'][0]['name'],
                'image_url': track['album']['images'][0]['url'] if track['album']['images'] else 'https://picsum.photos/300/200?random=1',
                'uri': track['uri'],
                'embed_url': f"https://open.spotify.com/embed/track/{track['uri'].split(':')[-1]}"
            }
            for track in tracks
        ]
        return jsonify(results)
    else:
        return jsonify({'error': 'Error al buscar canciones'}), search_response.status_code

@app.route('/add_to_playlist', methods=['POST'])
def add_to_playlist():
    if 'user_id' not in session:
        return jsonify({'error': 'Usuario no autenticado'}), 401
    
    playlist_id = request.form.get('playlist_id')
    song_uri = request.form.get('song_uri')
    song_title = request.form.get('song_title')
    song_artist = request.form.get('song_artist')
    
    if not playlist_id:
        return jsonify({'error': 'Por favor selecciona una playlist'}), 400
    
    try:
        playlist_response = supabase.table('playlists').select('songs').eq('id', playlist_id).eq('user_id', session['user_id']).execute()
        if not playlist_response.data:
            return jsonify({'error': 'Playlist no encontrada'}), 404
        
        current_songs = playlist_response.data[0]['songs'] or []
        new_song = {
            'uri': song_uri,
            'title': song_title,
            'artist': song_artist
        }
        
        if not any(song['uri'] == song_uri for song in current_songs):
            current_songs.append(new_song)
        
        supabase.table('playlists').update({'songs': current_songs}).eq('id', playlist_id).execute()
        return jsonify({'success': True, 'message': 'Canción agregada a la playlist'})
    except Exception as e:
        return jsonify({'error': f'Error al agregar canción: {str(e)}'}), 500

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    if 'user_id' not in session:
        return jsonify({'error': 'Usuario no autenticado'}), 401

    playlist_name = request.form.get('playlist_name')
    if not playlist_name:
        return jsonify({'error': 'El nombre de la playlist es obligatorio'}), 400

    try:
        supabase.table('playlists').insert({
            'user_id': session['user_id'],
            'name': playlist_name,
            'songs': []
        }).execute()
        return jsonify({'success': True, 'message': 'Playlist creada con éxito'})
    except Exception as e:
        return jsonify({'error': f'Error al crear la playlist: {str(e)}'}), 500

@app.route('/log_listening', methods=['POST'])
def log_listening():
    if 'user_id' not in session:
        return jsonify({'error': 'Usuario no autenticado'}), 401
    
    data = request.get_json()
    song_uri = data.get('song_uri')
    song_title = data.get('song_title')
    song_artist = data.get('song_artist')
    
    try:
        supabase.table('listening_history').insert({
            'user_id': session['user_id'],
            'song_uri': song_uri,
            'song_title': song_title,
            'song_artist': song_artist,
        }).execute()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/load_more_history', methods=['GET'])
def load_more_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Usuario no autenticado'}), 401
    
    offset = request.args.get('offset', default=0, type=int)
    limit = 3
    
    history_response = supabase.table('listening_history').select('*').eq('user_id', session['user_id']).order('listened_at', desc=True).range(offset, offset + limit - 1).execute()
    listening_history = history_response.data if history_response.data else []
    for entry in listening_history:
        entry['listened_at'] = entry['listened_at'].replace('Z', '+00:00')
    
    return jsonify(listening_history)

# --- User Interaction Routes ---

@app.route('/submit_comment', methods=['POST'])
def submit_comment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    comment = request.form['comment']
    
    try:
        supabase.table('comentarios').insert({
            'user_id': session['user_id'],
            'comment': comment,
            'created_at': datetime.now(timezone.utc).isoformat()
        }).execute()
        return redirect(url_for('dashboard', comment_success=True))
    except Exception as e:
        return redirect(url_for('dashboard', comment_error=f"Error al enviar comentario: {str(e)}"))

# --- Testing Routes ---

@app.route('/test-spotify-token')
def test_spotify_token():
    token = 'BQDpegbKar3vJIGT73fuZ7qF1zMY_1vo9DUSPz89Xrzx8qAEDuN-VqUhSp4s8mHBnckOZLqxR7DWP6pFHkEvIaQDomiOnsSGf_KqHHcxFnZzKT2abHLdO0haqofWW_Rgonbx2u8YDQMMYcWdJqKNqzXI7wAjlc2L1n_ZLNvNn2S7spu4EgDFTNxTrlcyokQEZM-mh7FPuOcoXVCK5P1AX4lNDoCavO6FNe6h7GbG-2Q_1l5ScrLhSWp8A5e4n-NYf5bp'
    headers = {'Authorization': f'Bearer {token}'}
    
    user_response = requests.get(f'{SPOTIFY_API_BASE_URL}me', headers=headers)
    print(f"Prueba /v1/me con token manual: {user_response.status_code}, {user_response.text}")
    
    params = {
        'seed_genres': 'pop',
        'limit': 3
    }
    rec_response = requests.get(f'{SPOTIFY_API_BASE_URL}recommendations', headers=headers, params=params)
    print(f"Prueba /v1/recommendations con token manual: {rec_response.status_code}, {rec_response.text}")
    
    top_tracks_response = requests.get(f'{SPOTIFY_API_BASE_URL}me/top/tracks', headers=headers, params={'limit': 10, 'time_range': 'medium_term'})
    print(f"Prueba /v1/me/top/tracks con token manual: {top_tracks_response.status_code}, {top_tracks_response.text}")
    
    return "Prueba completada. Revisa el log en la terminal."

# --- Application Entry Point ---

if __name__ == '__main__':
    app.run(debug=True)
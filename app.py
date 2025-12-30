from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import supabase
import uuid
import requests
import math
import time
import json
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from flask_cors import CORS
import bleach  # Biblioteca para sanitizar entradas
from flask_wtf.csrf import CSRFProtect  # Protección CSRF
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, TextAreaField, HiddenField, SelectField, FileField
from wtforms.validators import DataRequired, Email, Length
from flask_wtf.file import FileRequired
from gtts import gTTS
from pydub import AudioSegment
import spotipy
import speech_recognition as sr
from vosk import Model, KaldiRecognizer
import wave
import pygame
import pyttsx3
import re
from spotipy.oauth2 import SpotifyOAuth
from functools import wraps
import logging
from logging.handlers import RotatingFileHandler
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')  # Necesario para CSRF y sesiones

# Configurar protección CSRF
csrf = CSRFProtect(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_AUTH_URL = os.getenv("SPOTIFY_AUTH_URL")
SPOTIFY_TOKEN_URL = os.getenv("SPOTIFY_TOKEN_URL")
SPOTIFY_API_BASE_URL = os.getenv("SPOTIFY_API_BASE_URL")

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

with open('fallback_songs.json', 'r') as f:
    FALLBACK_SONGS_BY_GENRE = json.load(f)

    # Formularios con CSRF
class PlaylistForm(FlaskForm):
    playlist_name = StringField('Nombre de la Playlist', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Crear Playlist')

class AddToPlaylistForm(FlaskForm):
    playlist_id = SelectField('Playlist', coerce=str, validators=[DataRequired()])
    song_uri = HiddenField('Song URI', validators=[DataRequired()])
    song_title = HiddenField('Song Title', validators=[DataRequired()])
    song_artist = HiddenField('Song Artist', validators=[DataRequired()])
    submit = SubmitField('Agregar a Playlist')

class CommentForm(FlaskForm):
    comment = StringField('Comentario', validators=[DataRequired(), Length(min=1, max=500)])
    submit = SubmitField('Enviar Comentario')

class LoginForm(FlaskForm):
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')

class RegisterForm(FlaskForm):
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
    name = StringField('Nombre', validators=[DataRequired()])
    music_genre = StringField('Género Musical Favorito')
    language = SelectField('Idioma', choices=[('en-US', 'Inglés'), ('es', 'Español'), ('fr', 'Francés'), ('ja', 'Japonés'), ('ko', 'Coreano')], default='en-US')
    password = PasswordField('Contraseña', validators=[DataRequired()])
    voice_sample = FileField('Muestra de Voz (graba tu voz diciendo "Hola, soy [tu nombre]")', validators=[FileRequired()])  # Nuevo campo
    submit = SubmitField('Registrarse')

    # Formularios para artistas
class ArtistProfileForm(FlaskForm):
    bio = TextAreaField('Biografía', validators=[Length(max=500)])
    submit = SubmitField('Guardar')

class ArtistSongForm(FlaskForm):
    title = StringField('Título de la Canción', validators=[DataRequired(), Length(max=100)])
    song_file = FileField('Archivo de Audio', validators=[DataRequired()])
    submit = SubmitField('Subir')

def refresh_spotify_token():
    if 'refresh_token' not in session:
        print("No refresh token available in session")
        return False

    refresh_url = 'https://accounts.spotify.com/api/token'
    refresh_data = {
        'grant_type': 'refresh_token',
        'refresh_token': session['refresh_token'],
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    }

    try:
        response = requests.post(refresh_url, data=refresh_data)
        response.raise_for_status()
        token_data = response.json()
        session['spotify_token'] = token_data['access_token']
        session['token_expires_at'] = int(time.time()) + token_data['expires_in']
        if 'refresh_token' in token_data:
            session['refresh_token'] = token_data['refresh_token']
        print("Token refreshed successfully")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error refreshing Spotify token: {e}")
        return False

def get_new_releases(limit=10, market='US'):
    import time
    import requests

    if 'spotify_token' not in session:
        print("No hay token de Spotify en la sesión")
        return []

    # Forzar refresh del token si está cerca de expirar
    if 'token_expires_at' in session and int(time.time()) > session['token_expires_at'] - 300:
        if not refresh_spotify_token():
            print("No se pudo refrescar el token")
            return []

    headers = {'Authorization': f"Bearer {session['spotify_token']}"}
    params = {'limit': limit, 'country': market}
    max_retries = 3
    backoff_factor = 1

    for attempt in range(max_retries):
        try:
            # Obtener nuevos lanzamientos (álbumes)
            response = requests.get(f'{SPOTIFY_API_BASE_URL}browse/new-releases', headers=headers, params=params)
            response.raise_for_status()
            albums = response.json()['albums']['items']

            # Obtener pistas de los álbumes
            tracks = []
            for album in albums[:limit]:
                album_id = album['id']
                tracks_response = requests.get(
                    f'{SPOTIFY_API_BASE_URL}albums/{album_id}/tracks',
                    headers=headers,
                    params={'limit': 1}  # Tomar solo la primera pista por álbum
                )
                tracks_response.raise_for_status()
                album_tracks = tracks_response.json()['items']
                for track in album_tracks:
                    # Obtener detalles completos de la pista para asegurar datos como imágenes
                    track_details = requests.get(
                        f'{SPOTIFY_API_BASE_URL}tracks/{track["id"]}',
                        headers=headers,
                        params={'market': market}
                    )
                    track_details.raise_for_status()
                    track_data = track_details.json()
                    tracks.append({
                        'title': track_data['name'],
                        'artist': track_data['artists'][0]['name'],
                        'image_url': track_data['album']['images'][0]['url'] if track_data['album']['images'] else 'https://picsum.photos/300/200?random=1',
                        'uri': track_data['uri'],
                        'embed_url': f"https://open.spotify.com/embed/track/{track_data['uri'].split(':')[-1]}"
                    })
                if len(tracks) >= limit:
                    break

            return tracks[:limit]
        except requests.exceptions.RequestException as e:
            print(f"Intento {attempt + 1} fallido en /browse/new-releases: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
                continue
            print(f"Error al obtener nuevos lanzamientos: {str(e)}")
            return []

def get_available_markets():
    import time
    import requests

    # Verificar si ya está en caché
    if 'available_markets' in session:
        return session['available_markets']

    if 'spotify_token' not in session:
        print("No hay token de Spotify en la sesión")
        return []

    # Forzar refresh del token si está cerca de expirar
    if 'token_expires_at' in session and int(time.time()) > session['token_expires_at'] - 300:
        if not refresh_spotify_token():
            print("No se pudo refrescar el token")
            return []

    headers = {'Authorization': f"Bearer {session['spotify_token']}"}
    max_retries = 3
    backoff_factor = 1

    for attempt in range(max_retries):
        try:
            response = requests.get(f'{SPOTIFY_API_BASE_URL}markets', headers=headers)
            response.raise_for_status()
            data = response.json()
            markets = data['markets']
            # Almacenar en caché
            session['available_markets'] = markets
            session.modified = True
            return markets
        except requests.exceptions.RequestException as e:
            print(f"Intento {attempt + 1} fallido en /markets: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
                continue
            print(f"Error al obtener mercados disponibles: {str(e)}")
            return []

def get_available_genres():
    import time
    import requests

    # Verificar si ya está en caché
    if 'available_genres' in session:
        return session['available_genres']

    if 'spotify_token' not in session:
        print("No hay token de Spotify en la sesión")
        return []

    # Forzar refresh del token si está cerca de expirar
    if 'token_expires_at' in session and int(time.time()) > session['token_expires_at'] - 300:
        if not refresh_spotify_token():
            print("No se pudo refrescar el token")
            return []

    headers = {'Authorization': f"Bearer {session['spotify_token']}"}
    max_retries = 3
    backoff_factor = 1

    for attempt in range(max_retries):
        try:
            response = requests.get(f'{SPOTIFY_API_BASE_URL}recommendations/available-genre-seeds', headers=headers)
            response.raise_for_status()
            data = response.json()
            genres = data['genres']
            # Almacenar en caché
            session['available_genres'] = genres
            session.modified = True
            return genres
        except requests.exceptions.RequestException as e:
            print(f"Intento {attempt + 1} fallido en /recommendations/available-genre-seeds: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
                continue
            print(f"Error al obtener géneros disponibles: {str(e)}")
            return []

def get_recommendations(genre, market, limit=8):
    import time
    import requests
    import random

    user_genre = genre.lower().replace('&', 'and').replace(',', '').replace(' ', '-')
    if user_genre not in SPOTIFY_SUPPORTED_GENRES:
        print(f"Género '{user_genre}' no soportado. Usando 'pop' como fallback.")
        user_genre = 'pop'

    # Forzar refresh del token si está cerca de expirar
    if 'token_expires_at' in session and int(time.time()) > session['token_expires_at'] - 300:
        if not refresh_spotify_token():
            print("No se pudo refrescar el token, usando respaldo")
            return FALLBACK_SONGS_BY_GENRE.get(user_genre, FALLBACK_SONGS_BY_GENRE['pop'])[:limit]

    if 'spotify_token' not in session:
        print("No hay token de Spotify en la sesión, usando respaldo")
        return FALLBACK_SONGS_BY_GENRE.get(user_genre, FALLBACK_SONGS_BY_GENRE['pop'])[:limit]

    headers = {'Authorization': f"Bearer {session['spotify_token']}"}
    max_retries = 3
    backoff_factor = 1

    # Inicializar historial de recomendaciones
    if 'recent_recommendations' not in session:
        session['recent_recommendations'] = []

    # Usar la hora actual como semilla para consistencia
    current_hour = int(time.time() // 3600)
    random.seed(current_hour)

    for attempt in range(max_retries):
        try:
            # Obtener semillas
            seed_artists = None
            seed_tracks = None

            # Obtener tracks del historial de escucha
            try:
                history_response = supabase.table('listening_history') \
                    .select('song_uri') \
                    .eq('user_id', session['user_id']) \
                    .order('listened_at', desc=True) \
                    .limit(5) \
                    .execute()
                history_tracks = [entry['song_uri'].split(':')[-1] for entry in history_response.data] if history_response.data else []
                seed_tracks = ','.join(history_tracks[:1]) if history_tracks else None  # Usar solo 1 track
            except Exception as e:
                print(f"Error obteniendo historial de escucha: {str(e)}")

            # Obtener top artists
            try:
                top_artists_response = requests.get(
                    f'{SPOTIFY_API_BASE_URL}me/top/artists',
                    headers=headers,
                    params={'limit': 5, 'time_range': 'medium_term'}
                )
                top_artists_response.raise_for_status()
                top_artists_data = top_artists_response.json()
                artists_list = [item['id'] for item in top_artists_data['items']]
                seed_artists = ','.join(random.sample(artists_list, min(2, len(artists_list)))) if artists_list else None
            except Exception as e:
                print(f"Error obteniendo top artists: {str(e)}")

            # Construir parámetros
            params = {
                'limit': limit,
                'market': market,
                'seed_genres': user_genre  # Usar solo el género principal
            }
            seeds_used = 1  # Contar el género
            if seed_artists and seeds_used < 5:
                params['seed_artists'] = seed_artists
                seeds_used += len(seed_artists.split(','))
            if seed_tracks and seeds_used < 5:
                params['seed_tracks'] = seed_tracks
                seeds_used += 1

            # Ajustar popularidad
            params['target_popularity'] = random.randint(40, 80)

            print(f"Parámetros para /recommendations: {params}")
            response = requests.get(f'{SPOTIFY_API_BASE_URL}recommendations', headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            tracks = data['tracks']
            if not tracks:
                raise ValueError("No se encontraron recomendaciones")

            # Filtrar canciones recientes
            recent_uris = set(session['recent_recommendations'])
            filtered_tracks = [track for track in tracks if track['uri'] not in recent_uris]
            if not filtered_tracks:
                filtered_tracks = tracks

            recommendations = [
                {
                    'title': track['name'],
                    'artist': track['artists'][0]['name'],
                    'image_url': track['album']['images'][0]['url'] if track['album']['images'] else 'https://picsum.photos/300/200?random=1',
                    'uri': track['uri'],
                    'embed_url': f"https://open.spotify.com/embed/track/{track['uri'].split(':')[-1]}"
                } for track in filtered_tracks[:limit]
            ]

            # Actualizar historial
            session['recent_recommendations'] = [track['uri'] for track in recommendations] + session['recent_recommendations']
            session['recent_recommendations'] = session['recent_recommendations'][:20]
            session.modified = True

            return recommendations

        except requests.exceptions.RequestException as e:
            print(f"Intento {attempt + 1} fallido en /recommendations: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor * (2 ** attempt))
                continue
            # Fallback a top tracks
            try:
                top_tracks_response = requests.get(
                    f'{SPOTIFY_API_BASE_URL}me/top/tracks',
                    headers=headers,
                    params={'limit': limit, 'time_range': 'medium_term'}
                )
                top_tracks_response.raise_for_status()
                tracks = top_tracks_response.json()['items']
                recommendations = [
                    {
                        'title': track['name'],
                        'artist': track['artists'][0]['name'],
                        'image_url': track['album']['images'][0]['url'] if track['album']['images'] else 'https://picsum.photos/300/200?random=1',
                        'uri': track['uri'],
                        'embed_url': f"https://open.spotify.com/embed/track/{track['uri'].split(':')[-1]}"
                    } for track in tracks
                ]
                session['recent_recommendations'] = [track['uri'] for track in recommendations] + session['recent_recommendations']
                session['recent_recommendations'] = session['recent_recommendations'][:20]
                session.modified = True
                return recommendations
            except Exception as e:
                print(f"Fallback a top tracks falló: {str(e)}. Usando lista estática.")
                return FALLBACK_SONGS_BY_GENRE.get(user_genre, FALLBACK_SONGS_BY_GENRE['pop'])[:limit]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
from concurrent_log_handler import ConcurrentRotatingFileHandler
handler = ConcurrentRotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
logging.getLogger().addHandler(handler)
recognizer = sr.Recognizer()

# Configuración de Vosk
language_models = {
    'en-US': "models/vosk-model-small-en-us-0.15",
    'es': "models/vosk-model-small-es-0.42",
    'fr': "models/vosk-model-small-fr-0.22",
    'ja': "models/vosk-model-small-ja-0.22",
    'ko': "models/vosk-model-small-ko-0.22"
}

@app.before_request
def before_request():
    if 'spotify_token' in session and 'token_expires_at' in session:
        if int(time.time()) > session['token_expires_at'] - 300:
            print("Refrescando token de Spotify...")
            refresh_spotify_token()

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

    # Obtener parámetros de la solicitud
    comment_success = request.args.get('comment_success', default=False, type=bool)
    comment_error = request.args.get('comment_error', default=None, type=str)
    playlist_success = request.args.get('playlist_success', default=False, type=bool)
    playlist_error = request.args.get('playlist_error', default=None, type=str)

    # Inicializar formularios
    create_playlist_form = PlaylistForm()
    add_to_playlist_form = AddToPlaylistForm()
    comment_form = CommentForm()

    # Obtener playlists del usuario desde Supabase
    playlists_response = supabase.table('playlists').select('*').eq('user_id', session['user_id']).execute()
    playlists = playlists_response.data if playlists_response.data else []
    for playlist in playlists:
        playlist['created_at'] = datetime.fromisoformat(playlist['created_at'].replace('Z', '+00:00'))
        # Agregar lista vacía de canciones si no existe (para evitar errores en el template)
        playlist['songs'] = playlist.get('songs', [])

    # Crear la lista de choices para el formulario
    playlist_choices = [('', 'Seleccionar Playlist')] + [(str(playlist['id']), playlist['name']) for playlist in playlists]

    # Obtener historial de escucha
    history_response = supabase.table('listening_history').select('*').eq('user_id', session['user_id']).order('listened_at', desc=True).limit(3).execute()
    listening_history = history_response.data if history_response.data else []
    for entry in listening_history:
        entry['listened_at'] = datetime.fromisoformat(entry['listened_at'].replace('Z', '+00:00'))

    # Obtener datos del usuario
    user_response = supabase.table('users').select('music_genre, role').eq('user_id', session['user_id']).execute()

    artist_songs_response = supabase.table('artist_songs').select('*').order('created_at', desc=True).limit(5).execute()
    artist_songs = artist_songs_response.data if artist_songs_response.data else []
    for song in artist_songs:
        song['created_at'] = datetime.fromisoformat(song['created_at'].replace('Z', '+00:00'))

    if not user_response.data:
        return redirect(url_for('login'))
    music_genre = user_response.data[0]['music_genre'] if user_response.data[0]['music_genre'] else 'pop'
    user_role = user_response.data[0]['role'] if user_response.data else 2

    # Inicializar variables
    recommended_songs = []
    admin_playlist_songs = []
    new_releases = []
    admin_metrics = {}
    admin_playlist_id = '0QGY1uzNgID0ul2jqczpEN'


    user_genre = music_genre.lower().replace('&', 'and').replace(',', '').replace(' ', '-') if music_genre else 'pop'
    if user_genre not in SPOTIFY_SUPPORTED_GENRES:
        user_genre = 'pop'

    if 'spotify_token' in session:
        token = session['spotify_token']
        headers = {'Authorization': f'Bearer {token}'}

        # Obtener canciones de la playlist del administrador
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

        # Obtener información del usuario para el mercado
        user_response = requests.get(f'{SPOTIFY_API_BASE_URL}me', headers=headers)
        print(f"Prueba /v1/me: {user_response.status_code}, {user_response.text}")

        if user_response.status_code == 200:
            user_data = user_response.json()
            print(f"Detalles del usuario: {user_data}")
            market = user_data.get('country', 'US')
            print(f"Mercado del usuario: {market}")

            # Obtener recomendaciones (función definida en tu código)
            recommended_songs = get_recommendations(user_genre, market, limit=8)
        else:
            print(f"Error al obtener información del usuario: {user_response.status_code}, {user_response.text}")
    else:
        print("Falta el token de Spotify")
        recommended_songs = FALLBACK_SONGS_BY_GENRE.get(user_genre, FALLBACK_SONGS_BY_GENRE['pop'])[:8]

    # Métricas para administradores
    if user_role == 1:
        active_users_response = supabase.table('users').select('user_id').execute()
        admin_metrics['active_users'] = len(active_users_response.data) if active_users_response.data else 0

        listening_history_response = supabase.table('listening_history').select('song_title, song_artist').execute()
        listening_data = listening_history_response.data if listening_history_response.data else []

        song_counts = {}
        for entry in listening_data:
            key = (entry['song_title'], entry['song_artist'])
            song_counts[key] = song_counts.get(key, 0) + 1

        top_songs = [
            {'song_title': title, 'song_artist': artist, 'play_count': count}
            for (title, artist), count in song_counts.items()
        ]
        top_songs = sorted(top_songs, key=lambda x: x['play_count'], reverse=True)[:5]
        admin_metrics['top_songs'] = top_songs
        new_releases = get_new_releases(limit=5)

    return render_template('dashboard.html',
                    playlists=playlists,
                    recommended_songs=recommended_songs,
                    new_releases=new_releases,
                    playlist_choices=playlist_choices,
                    admin_playlist_songs=admin_playlist_songs,
                    listening_history=listening_history,
                    comment_success=comment_success,
                    comment_error=comment_error,
                    playlist_success=playlist_success,
                    playlist_error=playlist_error,
                    create_playlist_form=create_playlist_form,
                    add_to_playlist_form=add_to_playlist_form,
                    user_role=user_role,
                    admin_metrics=admin_metrics,
                    form=create_playlist_form,
                    comment_form=comment_form,
                    artist_songs=artist_songs)

@app.route('/admin')
def admin():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))

    recent_users_response = supabase.table('users').select('name').order('created_at', desc=True).limit(3).execute()
    recent_users = recent_users_response.data if recent_users_response.data else []

    recent_comments_response = supabase.table('comentarios').select('comment, created_at, user_id').order('created_at', desc=True).limit(2).execute()
    recent_comments = recent_comments_response.data if recent_comments_response.data else []
    for comment in recent_comments:
        comment['created_at'] = datetime.fromisoformat(comment['created_at'].replace('Z', '+00:00'))
        user_response = supabase.table('users').select('name').eq('user_id', comment['user_id']).execute()
        comment['user_name'] = user_response.data[0]['name'] if user_response.data else 'Anónimo'

    return render_template('admin.html', recent_users=recent_users, recent_comments=recent_comments)

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))

    users_response = supabase.table('users').select('user_id, email, name, music_genre, role').execute()
    usuarios = users_response.data if users_response.data else []
    return render_template('admin_users.html', usuarios=usuarios)

@app.route('/admin/news')
def admin_news():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))

    # Simulación de noticias (puedes integrar con una tabla de Supabase si es necesario)
    news = [
        {'title': 'Noticia 1', 'content': 'Contenido de la noticia 1'},
        {'title': 'Noticia 2', 'content': 'Contenido de la noticia 2'}
    ]

    return render_template('admin_news.html', news=news)

@app.route('/admin/trends')
def admin_trends():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))

    # Obtener géneros más escuchados
    genre_response = supabase.table('listening_history').select('song_genre', count='exact').order('count', desc=True).limit(5).execute()
    top_genres = [entry['song_genre'] for entry in genre_response.data]

    # Obtener artistas más escuchados
    artist_response = supabase.table('listening_history').select('song_artist', count='exact').order('count', desc=True).limit(5).execute()
    top_artists = [entry['song_artist'] for entry in artist_response.data]

    # Obtener canciones más escuchadas
    song_response = supabase.table('listening_history').select('song_title, song_artist', count='exact').order('count', desc=True).limit(5).execute()
    top_songs = [{'title': entry['song_title'], 'artist': entry['song_artist']} for entry in song_response.data]

    trends = {
        'top_genres': top_genres,
        'top_artists': top_artists,
        'top_songs': top_songs
    }
    return render_template('admin_trends.html', trends=trends)

@app.route('/admin/geotend')
def admin_geotend():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))

    geotend = {
        'top_countries': [
            {'country': 'Colombia', 'percentage': 65},
            {'country': 'EEUU', 'percentage': 15.7},
            {'country': 'Russia', 'percentage': 5.6}
        ]
    }
    return render_template('admin_geotend.html', geotend=geotend)

@app.route('/admin/statistics', methods=['GET'])
def admin_statistics():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))

    # Obtener el parámetro de rango temporal
    time_range = request.args.get('range', 'all')

    # Definir filtros de tiempo
    if time_range == 'week':
        time_filter = datetime.now() - timedelta(days=7)
        users_query = supabase.table('users').select('user_id').gte('created_at', time_filter.isoformat()).execute()
        plays_query = supabase.table('listening_history').select('id').gte('listened_at', time_filter.isoformat()).execute()
        comments_query = supabase.table('comentarios').select('id').gte('created_at', time_filter.isoformat()).execute()
    elif time_range == 'month':
        time_filter = datetime.now() - timedelta(days=30)
        users_query = supabase.table('users').select('user_id').gte('created_at', time_filter.isoformat()).execute()
        plays_query = supabase.table('listening_history').select('id').gte('listened_at', time_filter.isoformat()).execute()
        comments_query = supabase.table('comentarios').select('id').gte('created_at', time_filter.isoformat()).execute()
    else:
        users_query = supabase.table('users').select('user_id').execute()
        plays_query = supabase.table('listening_history').select('id').execute()
        comments_query = supabase.table('comentarios').select('id').execute()

    total_users = len(users_query.data)
    total_plays = len(plays_query.data)
    total_comments = len(comments_query.data)

    statistics = {
        'total_users': total_users,
        'total_songs_played': total_plays,
        'total_comments': total_comments
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(statistics)
    return render_template('admin_statistics.html', statistics=statistics)

@app.route('/artist/dashboard')
def artist_dashboard():
    if 'user_id' not in session or session.get('role') != 3:
        return redirect(url_for('login'))

    # Obtener información del artista
    artist_response = supabase.table('users').select('name, bio').eq('user_id', session['user_id']).execute()
    if not artist_response.data:
        return redirect(url_for('login'))
    artist = artist_response.data[0]

    # Obtener canciones del artista
    songs_response = supabase.table('artist_songs').select('*').eq('user_id', session['user_id']).order('created_at', desc=True).execute()
    songs = songs_response.data if songs_response.data else []

    for song in songs:
        song['created_at'] = datetime.fromisoformat(song['created_at'].replace('Z', '+00:00'))

    return render_template('artist_dashboard.html', artist=artist, songs=songs)

@app.route('/artist/edit_profile', methods=['GET', 'POST'])
def artist_edit_profile():
    if 'user_id' not in session or session.get('role') != 3:
        return redirect(url_for('login'))

    form = ArtistProfileForm()
    if form.validate_on_submit():
        try:
            supabase.table('users').update({
                'bio': form.bio.data
            }).eq('user_id', session['user_id']).execute()
            return redirect(url_for('artist_dashboard', success='Perfil actualizado correctamente'))
        except Exception as e:
            return render_template('artist_edit_profile.html', form=form, error=f'Error al actualizar el perfil: {str(e)}')

    # Precargar la biografía actual
    artist_response = supabase.table('users').select('bio').eq('user_id', session['user_id']).execute()
    if artist_response.data:
        form.bio.data = artist_response.data[0]['bio'] or ''

    return render_template('artist_edit_profile.html', form=form)

@app.route('/artist/upload_song', methods=['GET', 'POST'])
def artist_upload_song():
    if 'user_id' not in session or session.get('role') != 3:
        return redirect(url_for('login'))

    form = ArtistSongForm()
    if form.validate_on_submit():
        try:
            song_file = form.song_file.data
            title = form.title.data
            filename = secure_filename(song_file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if file_ext not in ['mp3', 'wav']:
                return render_template('artist_upload_song.html', form=form, error='Solo se permiten archivos MP3 o WAV')

            # Generar un nombre único para el archivo
            unique_filename = f"{session['user_id']}_{int(datetime.now(timezone.utc).timestamp())}.{file_ext}"

            # Subir archivo a Supabase Storage
            file_data = song_file.read()
            storage_response = supabase.storage.from_('artist_songs').upload(unique_filename, file_data, {'content-type': f'audio/{file_ext}'})

            # Obtener la URL pública del archivo
            public_url = supabase.storage.from_('artist_songs').get_public_url(unique_filename)

            # Guardar metadatos en la tabla artist_songs
            supabase.table('artist_songs').insert({
                'user_id': session['user_id'],
                'title': title,
                'file_url': public_url,
                'created_at': datetime.now(timezone.utc).isoformat()
            }).execute()

            return redirect(url_for('artist_dashboard', success='Canción subida correctamente'))
        except Exception as e:
            return render_template('artist_upload_song.html', form=form, error=f'Error al subir la canción: {str(e)}')

    return render_template('artist_upload_song.html', form=form)

@app.route('/admin_manage_playlist', methods=['GET', 'POST'])
def admin_manage_playlist():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))

    admin_playlist_id = '0QGY1uzNgID0ul2jqczpEN'
    headers = {'Authorization': f'Bearer {session["spotify_token"]}'}
    SPOTIFY_API_BASE_URL = 'https://api.spotify.com/v1/'

    if request.method == 'POST':
        action = request.form.get('action')
        song_uri = request.form.get('song_uri')

        if action == 'add':
            payload = {
                'uris': [song_uri],
                'position': 0
            }
            response = requests.post(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, json=payload)
            if response.status_code == 201:
                return jsonify({'success': True, 'message': 'Canción agregada a la playlist del administrador'})
            else:
                return jsonify({'error': 'Error al agregar la canción'}), 500

        elif action == 'remove':
            payload = {
                'tracks': [{'uri': song_uri}]
            }
            response = requests.delete(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, json=payload)
            if response.status_code == 200:
                return jsonify({'success': True, 'message': 'Canción eliminada de la playlist del administrador'})
            else:
                return jsonify({'error': 'Error al eliminar la canción'}), 500

        elif action == 'reorder':
            song_uris = json.loads(request.form.get('song_uris', '[]'))
            # Obtener las canciones actuales de la playlist
            current_tracks_response = requests.get(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers)
            if current_tracks_response.status_code != 200:
                return jsonify({'error': 'Error al obtener la playlist'}), 500

            current_tracks = current_tracks_response.json()['items']
            current_uris = [track['track']['uri'] for track in current_tracks]

            # Encontrar la canción que cambió de posición
            for i, uri in enumerate(song_uris):
                if i < len(current_uris) and uri != current_uris[i]:
                    # Mover la canción de su posición actual a la nueva posición
                    old_index = current_uris.index(uri)
                    payload = {
                        'range_start': old_index,
                        'range_length': 1,
                        'insert_before': i
                    }
                    response = requests.put(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, json=payload)
                    if response.status_code == 200:
                        return jsonify({'success': True, 'message': 'Orden actualizado con éxito'})
                    else:
                        return jsonify({'error': 'Error al actualizar el orden'}), 500
            return jsonify({'success': True, 'message': 'Orden actualizado con éxito'})

    # Obtener las canciones de la playlist para mostrarlas
    playlist_response = requests.get(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, params={'limit': 10})
    if playlist_response.status_code == 200:
        tracks = playlist_response.json()['items']
        admin_playlist_songs = [
            {
                'title': track['track']['name'],
                'artist': track['track']['artists'][0]['name'],
                'uri': track['track']['uri'],
                'image_url': track['track']['album']['images'][0]['url'] if track['track']['album']['images'] else 'https://picsum.photos/50/50?random=1'
            } for track in tracks
        ]
    else:
        admin_playlist_songs = []

    return render_template('admin_manage_playlist.html', admin_playlist_songs=admin_playlist_songs)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    available_genres = get_available_genres()
    if request.method == 'POST' and form.validate_on_submit():
        email = form.email.data
        name = form.name.data
        music_genre = form.music_genre.data
        language = form.language.data
        password = form.password.data
        voice_sample = form.voice_sample.data

        normalized_genre = music_genre.lower().replace('&', 'and').replace(',', '').replace(' ', '-') if music_genre else 'pop'
        if normalized_genre not in SPOTIFY_SUPPORTED_GENRES:
            normalized_genre = 'pop'

        # Verificar si el correo ya está registrado
        response = supabase.table('users').select('email').eq('email', email).execute()
        if response.data and len(response.data) > 0:
            return render_template('register.html', error="El correo ya está registrado", form=form)

        # Procesar la muestra de voz para obtener el vector de hablante
        temp_path = f"temp_voice_sample_{int(datetime.now(timezone.utc).timestamp())}.wav"
        voice_sample.save(temp_path)

        try:
            # Convertir audio al formato correcto
            audio = AudioSegment.from_file(temp_path)
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            audio.export(temp_path, format="wav")

            # Cargar el modelo de identificación de hablantes
            spk_model = Model("models/vosk-model-spk-0.4")
            wf = wave.open(temp_path, "rb")
            recognizer = KaldiRecognizer(spk_model, 16000)

            speaker_data = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    spk_result = json.loads(recognizer.Result())
                    if 'spk' in spk_result:
                        speaker_data.append(spk_result['spk'])
            wf.close()

            if not speaker_data:
                os.remove(temp_path)
                return render_template('register.html', error="No se pudo procesar la muestra de voz. Intenta de nuevo.", form=form)

            # Calcular el vector de hablante promedio
            speaker_vector = [sum(x) / len(speaker_data) for x in zip(*speaker_data)]

        except Exception as e:
            os.remove(temp_path)
            return render_template('register.html', error=f"Error al procesar la muestra de voz: {str(e)}", form=form)

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        # Guardar el usuario en Supabase con el vector de hablante
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
        try:
            user_id = str(uuid.uuid4())
            supabase.table('users').insert({
                'email': email,
                'name': name,
                'music_genre': normalized_genre,
                'language': language,
                'password': hashed_password,
                'role': 2,
                'user_id': user_id,
                'speaker_vector': speaker_vector  # Almacenar el vector
            }).execute()
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('register.html', error=f"Error al registrarse: {str(e)}", form=form)
    return render_template('register.html', form=form, supported_genres=SPOTIFY_SUPPORTED_GENRES, available_genres=available_genres)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        response = supabase.table('users').select('*').eq('email', email).execute()

        if response.data and len(response.data) > 0:
            user = response.data[0]
            if check_password_hash(user['password'], password):
                session['user_id'] = str(user['user_id'])
                session['user_name'] = user['name']
                session['role'] = user['role']
                # Redirigir según el rol del usuario
                if user['role'] == 3:
                    return redirect(url_for('artist_dashboard'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error="Contraseña incorrecta", form=form)
        else:
            return render_template('login.html', error="Usuario no encontrado", form=form)
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/login-spotify')
def login_spotify():
    auth_params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'scope': 'user-read-private user-read-email user-top-read user-read-recently-played playlist-modify-public playlist-modify-private streaming user-read-playback-state user-modify-playback-state',
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
    token_info = response.json()

    print("Token Info:", token_info)
    if response.status_code == 200:
        session['spotify_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['token_expires_at'] = int(time.time()) + token_info['expires_in']

        # Obtener géneros disponibles
        headers = {'Authorization': f"Bearer {session['spotify_token']}"}
        genres_response = requests.get(f'{SPOTIFY_API_BASE_URL}recommendations/available-genre-seeds', headers=headers)
        if genres_response.status_code == 200:
            genres_data = genres_response.json()
            session['available_genres'] = genres_data['genres']
        else:
            print(f"Error al obtener géneros disponibles: {genres_response.status_code}, {genres_response.text}")
            session['available_genres'] = []

        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('dashboard', error='Error al obtener el token de Spotify'))

@app.route('/search_songs')
def search_songs():
    try:
        query = request.args.get('query')
        if not query:
            return jsonify({'error': 'Query parameter is required'}), 400

        if 'spotify_token' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        headers = {
            'Authorization': f"Bearer {session['spotify_token']}"
        }
        params = {
            'q': query,
            'type': 'track',
            'limit': 10
        }
        print(f"Buscando canciones con query: {query}")
        response = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"Respuesta de Spotify: {data}")
        tracks = data['tracks']['items']
        results = [
            {
                'title': track['name'],
                'artist': track['artists'][0]['name'],
                'uri': track['uri'],
                'image_url': track['album']['images'][0]['url'] if track['album']['images'] else 'https://picsum.photos/200/200?random=1'
            } for track in tracks
        ]
        return jsonify(results)
    except requests.exceptions.RequestException as e:
        print(f"Error al buscar canciones: {str(e)}")
        return jsonify({'error': 'Failed to search songs'}), 500
    except Exception as e:
        print(f"Error inesperado en /search_songs: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Función para ejecutar acciones en Spotify
def control_spotify(action, token, track_uri=None, volume=None):
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        if action == 'play':
            if track_uri:
                payload = {'uris': [track_uri]}
                response = requests.put('https://api.spotify.com/v1/me/player/play', headers=headers, json=payload)
            else:
                response = requests.put('https://api.spotify.com/v1/me/player/play', headers=headers)
        elif action == 'pause':
            response = requests.put('https://api.spotify.com/v1/me/player/pause', headers=headers)
        elif action == 'next':
            response = requests.post('https://api.spotify.com/v1/me/player/next', headers=headers)
        elif action == 'previous':
            response = requests.post('https://api.spotify.com/v1/me/player/previous', headers=headers)
        elif action == 'volume' and volume is not None:
            response = requests.put(f'https://api.spotify.com/v1/me/player/volume?volume_percent={int(volume * 100)}', headers=headers)

        if response.status_code in [200, 204]:
            return True
        else:
            logging.error(f"Error al ejecutar acción en Spotify ({action}): {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logging.error(f"Error al ejecutar acción en Spotify ({action}): {str(e)}")
        return False

@app.route('/voice-command', methods=['POST'])
def voice_command():
    if 'user_id' not in session:
        logging.warning("Intento de comando de voz sin autenticación")
        return jsonify({'error': 'Usuario no autenticado'}), 401

    if 'spotify_token' not in session:
        logging.warning("Intento de comando de voz sin token de Spotify")
        return jsonify({'error': 'Token de Spotify no encontrado'}), 401

    # Obtener el idioma y rol del usuario desde Supabase
    try:
        user_response = supabase.table('users').select('language, role').eq('user_id', session['user_id']).execute()
        user_language = user_response.data[0]['language'] if user_response.data and 'language' in user_response.data[0] else 'en-US'
        user_role = user_response.data[0]['role'] if user_response.data else 2
    except Exception as e:
        logging.warning(f"Error al obtener idioma del usuario: {str(e)}. Usando inglés por defecto.")
        user_language = 'en-US'
        user_role = 2

    # Mapa de idiomas soportados por Vosk
    language_models = {
        'en-US': "models/vosk-model-small-en-us-0.15",
        'es': "models/vosk-model-small-es-0.42",
        'fr': "models/vosk-model-small-fr-0.22",
        'ja': "models/vosk-model-small-ja-0.22",
        'ko': "models/vosk-model-small-ko-0.22"
    }

    if user_language not in language_models:
        user_language = 'en-US'  # Fallback

    # Verificar si se envió un archivo de audio
    if 'audio' not in request.files:
        logging.warning("Solicitud de comando de voz sin archivo de audio")
        return jsonify({'error': 'Archivo de audio no proporcionado'}), 400

    audio_file = request.files['audio']
    if audio_file.filename == '':
        logging.warning("Archivo de audio vacío recibido")
        return jsonify({'error': 'Archivo de audio vacío'}), 400

    # Medida de seguridad: Limitar tamaño del archivo de audio
    audio_file.seek(0, os.SEEK_END)
    file_size = audio_file.tell()
    if file_size > 5 * 1024 * 1024:  # 5 MB límite
        logging.warning(f"Archivo de audio demasiado grande: {file_size} bytes")
        return jsonify({'error': 'Archivo de audio demasiado grande'}), 400
    audio_file.seek(0)  # Volver al inicio del archivo

    try:
        # Guardar temporalmente el archivo de audio
        temp_path = f"temp_audio_{session['user_id']}_{int(datetime.now(timezone.utc).timestamp())}.wav"
        audio_file.save(temp_path)

        # Convertir audio al formato correcto para Vosk usando pydub
        audio = AudioSegment.from_file(temp_path)
        audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
        audio.export(temp_path, format="wav")

        # Cargar el modelo de Vosk para reconocimiento de voz
        model = Model(language_models[user_language])
        recognizer = KaldiRecognizer(model, 16000)

        # Cargar el modelo de identificación de hablantes
        spk_model = Model("models/vosk-model-spk-0.4")

        # Leer el archivo WAV
        wf = wave.open(temp_path, "rb")
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
            wf.close()
            os.remove(temp_path)
            logging.error("Formato de audio inválido después de conversión")
            return jsonify({'error': 'Error en formato de audio después de conversión.'}), 500

        # Reconocer el audio
        command = ""
        speaker_data = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                command += result.get('text', '')
                # Identificación de hablante
                spk_result = json.loads(recognizer.Result())
                if 'spk' in spk_result:
                    speaker_data.append(spk_result['spk'])

        wf.close()

        # Eliminar el archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if not command:
            logging.warning("No se pudo entender el comando de voz")
            return jsonify({'error': 'No se pudo entender el comando. Intenta hablar más claro.'}), 400

        logging.info(f"Comando reconocido ({user_language}): {command.lower()}")

        # Identificación de hablante
        if speaker_data:
            avg_speaker_vector = [sum(x) / len(speaker_data) for x in zip(*speaker_data)]
            logging.info(f"Vector de hablante promedio: {avg_speaker_vector}")

            # Obtener el vector almacenado del usuario
            stored_vector_response = supabase.table('users').select('speaker_vector').eq('user_id', session['user_id']).execute()
            if not stored_vector_response.data or 'speaker_vector' not in stored_vector_response.data[0]:
                logging.warning("Vector de hablante no encontrado para el usuario")
                return jsonify({'error': 'Vector de hablante no encontrado para este usuario. Registra una muestra de voz.'}), 400

            stored_vector = stored_vector_response.data[0]['speaker_vector']

            # Calcular la distancia coseno
            def cosine_distance(vec1, vec2):
                dot_product = sum(a * b for a, b in zip(vec1, vec2))
                norm1 = math.sqrt(sum(a * a for a in vec1))
                norm2 = math.sqrt(sum(b * b for b in vec2))
                if norm1 == 0 or norm2 == 0:
                    return 1.0
                return 1 - (dot_product / (norm1 * norm2))

            distance = cosine_distance(avg_speaker_vector, stored_vector)
            logging.info(f"Distancia coseno entre vectores: {distance}")

            # Umbral para aceptar la coincidencia
            if distance > 0.2:
                logging.warning(f"Identificación de hablante fallida. Distancia: {distance}")
                return jsonify({'error': 'Identificación de hablante fallida. La voz no coincide con el usuario registrado.'}), 403

        # Procesar el comando
        spotify_token = session['spotify_token']
        action = None
        message = None

        # Comandos generales
        if 'play' in command.lower() or any(x in command.lower() for x in ['reproducir', 'jouer', '再生', '재생']):
            match = re.search(r'(play|reproducir|jouer|再生|재생)\s+(.+?)(?:\s+by\s+(.+))?$', command.lower())
            if match:
                song_query = match.group(2)
                artist = match.group(3) if match.group(3) else ''
                query = f"{song_query} {artist}".strip()
                headers = {'Authorization': f"Bearer {spotify_token}"}
                params = {'q': query, 'type': 'track', 'limit': 1}
                response = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                tracks = data['tracks']['items']
                if tracks:
                    track = tracks[0]
                    track_uri = track['uri']
                    track_title = track['name']
                    track_artist = track['artists'][0]['name']
                    if control_spotify('play', spotify_token, track_uri=track_uri):
                        action = 'play'
                        message = {
                            'en-US': f"Playing {track_title} by {track_artist}",
                            'es': f"Reproduciendo {track_title} de {track_artist}",
                            'fr': f"Lecture de {track_title} par {track_artist}",
                            'ja': f"{track_artist}の{track_title}を再生中",
                            'ko': f"{track_artist}의 {track_title} 재생 중"
                        }.get(user_language, f"Playing {track_title} by {track_artist}")
                        supabase.table('listening_history').insert({
                            'user_id': session['user_id'],
                            'song_uri': track_uri,
                            'song_title': track_title,
                            'song_artist': track_artist,
                            'listened_at': datetime.now(timezone.utc).isoformat()
                        }).execute()
                    else:
                        logging.error("Error al reproducir la canción")
                        return jsonify({'error': 'Error al reproducir la canción'}), 500
                else:
                    logging.warning("Canción no encontrada")
                    return jsonify({'error': 'Canción no encontrada'}), 404
            else:
                if control_spotify('play', spotify_token):
                    action = 'play'
                    message = {
                        'en-US': "Resuming playback",
                        'es': "Reanudando reproducción",
                        'fr': "Reprise de la lecture",
                        'ja': "再生を再開",
                        'ko': "재생 재개"
                    }.get(user_language, "Resuming playback")
                else:
                    logging.error("Error al reanudar la reproducción")
                    return jsonify({'error': 'Error al reanudar la reproducción'}), 500

        elif any(x in command.lower() for x in ['pause', 'pausar', 'stop', 'para', 'arrêter', '停止', '정지']):
            if control_spotify('pause', spotify_token):
                action = 'pause'
                message = {
                    'en-US': "Pausing music",
                    'es': "Pausando música",
                    'fr': "Mise en pause de la musique",
                    'ja': "音楽を一時停止",
                    'ko': "음악 일시정지"
                }.get(user_language, "Pausing music")
            else:
                logging.error("Error al pausar la reproducción")
                return jsonify({'error': 'Error al pausar la reproducción'}), 500

        elif any(x in command.lower() for x in ['next', 'siguiente', 'skip', 'suivant', '次へ', '다음']):
            if control_spotify('next', spotify_token):
                action = 'next'
                message = {
                    'en-US': "Skipping to next song",
                    'es': "Saltando a la siguiente canción",
                    'fr': "Passage à la chanson suivante",
                    'ja': "次の曲にスキップ",
                    'ko': "다음 곡으로 건너뛰기"
                }.get(user_language, "Skipping to next song")
            else:
                logging.error("Error al saltar a la siguiente canción")
                return jsonify({'error': 'Error al saltar a la siguiente canción'}), 500

        elif any(x in command.lower() for x in ['previous', 'anterior', 'back', 'atrás', 'précédent', '前へ', '이전']):
            if control_spotify('previous', spotify_token):
                action = 'previous'
                message = {
                    'en-US': "Going back to previous song",
                    'es': "Volviendo a la canción anterior",
                    'fr': "Retour à la chanson précédente",
                    'ja': "前の曲に戻る",
                    'ko': "이전 곡으로 돌아가기"
                }.get(user_language, "Going back to previous song")
            else:
                logging.error("Error al volver a la canción anterior")
                return jsonify({'error': 'Error al volver a la canción anterior'}), 500

        elif any(x in command.lower() for x in ['volume', 'volumen', 'volume', 'ボリューム', '볼륨']):
            match = re.search(r'(volume|volumen|volume|ボリューム|볼륨)\s*(?:to)?\s*(\d+)', command.lower())
            if match:
                volume_level = float(match.group(2)) / 100
                if 0 <= volume_level <= 1:
                    if control_spotify('volume', spotify_token, volume=volume_level):
                        action = 'volume'
                        message = {
                            'en-US': f"Volume set to {int(volume_level * 100)} percent",
                            'es': f"Volumen ajustado a {int(volume_level * 100)} por ciento",
                            'fr': f"Volume réglé à {int(volume_level * 100)} pour cent",
                            'ja': f"ボリュームを{int(volume_level * 100)}パーセントに設定",
                            'ko': f"볼륨이 {int(volume_level * 100)}퍼센트로 설정됨"
                        }.get(user_language, f"Volume set to {int(volume_level * 100)} percent")
                        supabase.table('player_state').update({
                            'volume': volume_level,
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        }).eq('user_id', session['user_id']).execute()
                    else:
                        logging.error("Error al ajustar el volumen")
                        return jsonify({'error': 'Error al ajustar el volumen'}), 500
                else:
                    logging.warning("Volumen fuera de rango")
                    return jsonify({'error': 'El volumen debe estar entre 0 y 100'}), 400
            else:
                logging.warning("Nivel de volumen no especificado")
                return jsonify({'error': 'No se especificó un nivel de volumen válido'}), 400

        elif any(x in command.lower() for x in ['create playlist', 'crear playlist', 'créer playlist', 'プレイリストを作成', '플레이리스트 생성']):
            match = re.search(r'(create playlist|crear playlist|créer playlist|プレイリストを作成|플레이리스트 생성)\s+(.+)', command.lower())
            if match:
                playlist_name = match.group(2)
                try:
                    supabase.table('playlists').insert({
                        'user_id': session['user_id'],
                        'name': playlist_name,
                        'created_at': datetime.now(timezone.utc).isoformat()
                    }).execute()
                    action = 'create_playlist'
                    message = {
                        'en-US': f"Playlist {playlist_name} created",
                        'es': f"Playlist {playlist_name} creada",
                        'fr': f"Playlist {playlist_name} créée",
                        'ja': f"プレイリスト{playlist_name}を作成しました",
                        'ko': f"플레이리스트 {playlist_name} 생성됨"
                    }.get(user_language, f"Playlist {playlist_name} created")
                except Exception as e:
                    logging.error(f"Error al crear la playlist: {str(e)}")
                    return jsonify({'error': f"Error al crear la playlist: {str(e)}"}), 500
            else:
                logging.warning("Nombre de playlist no especificado")
                return jsonify({'error': 'Por favor especifica un nombre para la playlist'}), 400

        elif any(x in command.lower() for x in ['add to playlist', 'agregar a playlist', 'ajouter à la playlist', 'プレイリストに追加', '플레이리스트에 추가']):
            match = re.search(r'(add to playlist|agregar a playlist|ajouter à la playlist|プレイリストに追加|플레이리스트에 추가)\s+(.+)', command.lower())
            if match:
                playlist_name = match.group(2)
                playlists_response = supabase.table('playlists').select('id, songs').eq('user_id', session['user_id']).eq('name', playlist_name).execute()
                if not playlists_response.data:
                    logging.warning(f"Playlist {playlist_name} no encontrada")
                    return jsonify({'error': f"Playlist {playlist_name} no encontrada"}), 404

                player_state = supabase.table('player_state').select('track_queue, current_index').eq('user_id', session['user_id']).execute()
                if not player_state.data or not player_state.data[0]['track_queue']:
                    logging.warning("No hay canción en reproducción para agregar")
                    return jsonify({'error': 'No hay canción en reproducción para agregar'}), 400

                current_index = player_state.data[0]['current_index']
                track = player_state.data[0]['track_queue'][current_index]
                playlist_id = playlists_response.data[0]['id']
                current_songs = playlists_response.data[0]['songs'] or []
                new_song = {
                    'uri': track['uri'],
                    'title': track['title'],
                    'artist': track['artist']
                }
                if not any(song['uri'] == track['uri'] for song in current_songs):
                    current_songs.append(new_song)
                    supabase.table('playlists').update({'songs': current_songs}).eq('id', playlist_id).execute()
                    action = 'add_to_playlist'
                    message = {
                        'en-US': f"Song added to playlist {playlist_name}",
                        'es': f"Canción agregada a la playlist {playlist_name}",
                        'fr': f"Chanson ajoutée à la playlist {playlist_name}",
                        'ja': f"プレイリスト{playlist_name}に曲を追加しました",
                        'ko': f"플레이리스트 {playlist_name}에 곡 추가됨"
                    }.get(user_language, f"Song added to playlist {playlist_name}")
                else:
                    message = {
                        'en-US': f"Song already in playlist {playlist_name}",
                        'es': f"La canción ya está en la playlist {playlist_name}",
                        'fr': f"La chanson est déjà dans la playlist {playlist_name}",
                        'ja': f"その曲はすでにプレイリスト{playlist_name}にあります",
                        'ko': f"그 곡은 이미 플레이리스트 {playlist_name}에 있습니다"
                    }.get(user_language, f"Song already in playlist {playlist_name}")
            else:
                logging.warning("Nombre de playlist no especificado para agregar")
                return jsonify({'error': 'Por favor especifica el nombre de la playlist'}), 400

        # Comandos para administradores
        elif user_role == 1 and any(x in command.lower() for x in ['manage playlist', 'administrar playlist', 'gérer playlist', 'プレイリストを管理', '플레이리스트 관리']):
            match = re.search(r'(manage playlist|administrar playlist|gérer playlist|プレイリストを管理|플레이리스트 관리)\s+(add|remove|reorder)\s+(.+)', command.lower())
            if match:
                action_type = match.group(2)
                song_title = match.group(3)
                admin_playlist_id = '0QGY1uzNgID0ul2jqczpEN'
                headers = {'Authorization': f'Bearer {spotify_token}'}

                params = {'q': song_title, 'type': 'track', 'limit': 1}
                response = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params)
                response.raise_for_status()
                tracks = response.json()['tracks']['items']
                if not tracks:
                    logging.warning(f"Canción {song_title} no encontrada")
                    return jsonify({'error': 'Canción no encontrada'}), 404
                song_uri = tracks[0]['uri']

                if action_type == 'add':
                    payload = {'uris': [song_uri], 'position': 0}
                    response = requests.post(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, json=payload)
                    if response.status_code == 201:
                        action = 'admin_add_song'
                        message = {
                            'en-US': "Song added to admin playlist",
                            'es': "Canción agregada a la playlist del administrador",
                            'fr': "Chanson ajoutée à la playlist admin",
                            'ja': "管理者プレイリストに曲を追加しました",
                            'ko': "관리자 플레이리스트에 곡 추가됨"
                        }.get(user_language, "Song added to admin playlist")
                    else:
                        logging.error(f"Error al agregar canción al playlist del administrador: {response.status_code}")
                        return jsonify({'error': 'Error al agregar la canción'}), 500

                elif action_type == 'remove':
                    payload = {'tracks': [{'uri': song_uri}]}
                    response = requests.delete(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, json=payload)
                    if response.status_code == 200:
                        action = 'admin_remove_song'
                        message = {
                            'en-US': "Song removed from admin playlist",
                            'es': "Canción eliminada de la playlist del administrador",
                            'fr': "Chanson supprimée de la playlist admin",
                            'ja': "管理者プレイリストから曲を削除しました",
                            'ko': "관리자 플레이리스트에서 곡 삭제됨"
                        }.get(user_language, "Song removed from admin playlist")
                    else:
                        logging.error(f"Error al eliminar canción del playlist del administrador: {response.status_code}")
                        return jsonify({'error': 'Error al eliminar la canción'}), 500

                elif action_type == 'reorder':
                    current_tracks_response = requests.get(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers)
                    if current_tracks_response.status_code != 200:
                        logging.error(f"Error al obtener la playlist del administrador: {current_tracks_response.status_code}")
                        return jsonify({'error': 'Error al obtener la playlist'}), 500
                    current_tracks = current_tracks_response.json()['items']
                    current_uris = [track['track']['uri'] for track in current_tracks]
                    old_index = current_uris.index(song_uri) if song_uri in current_uris else -1
                    if old_index == -1:
                        logging.warning(f"Canción {song_title} no encontrada en la playlist del administrador")
                        return jsonify({'error': 'Canción no encontrada en la playlist'}), 404
                    payload = {'range_start': old_index, 'range_length': 1, 'insert_before': 0}
                    response = requests.put(f'{SPOTIFY_API_BASE_URL}playlists/{admin_playlist_id}/tracks', headers=headers, json=payload)
                    if response.status_code == 200:
                        action = 'admin_reorder_song'
                        message = {
                            'en-US': "Song reordered in admin playlist",
                            'es': "Canción reordenada en la playlist del administrador",
                            'fr': "Chanson réorganisée dans la playlist admin",
                            'ja': "管理者プレイリストで曲を並べ替えました",
                            'ko': "관리자 플레이리스트에서 곡 재정렬됨"
                        }.get(user_language, "Song reordered in admin playlist")
                    else:
                        logging.error(f"Error al reordenar canción en el playlist del administrador: {response.status_code}")
                        return jsonify({'error': 'Error al reordenar la canción'}), 500
            else:
                logging.warning("Acción o canción no especificada para gestionar playlist")
                return jsonify({'error': 'Especifica una acción (add, remove, reorder) y el nombre de la canción'}), 400

        # Comandos específicos para artistas
        elif user_role == 3:  # Rol de artista
            if any(x in command.lower() for x in ['editar biografía', 'editar perfil', 'cambiar biografía']):
                action = 'edit_profile'
                message = {
                    'en-US': "Redirecting to edit profile",
                    'es': "Redirigiendo a editar perfil",
                    'fr': "Redirection vers l'édition du profil",
                    'ja': "プロフィール編集にリダイレクト",
                    'ko': "프로필 편집으로 리디렉션"
                }.get(user_language, "Redirecting to edit profile")
            elif any(x in command.lower() for x in ['subir canción', 'subir musica', 'upload song']):
                action = 'upload_song'
                message = {
                    'en-US': "Redirecting to upload song",
                    'es': "Redirigiendo a subir canción",
                    'fr': "Redirection vers le téléchargement de chanson",
                    'ja': "曲のアップロードにリダイレクト",
                    'ko': "노래 업로드로 리디렉션"
                }.get(user_language, "Redirecting to upload song")
            else:
                logging.warning(f"Comando no reconocido para artistas: {command.lower()}")
                return jsonify({'error': 'Comando no reconocido para artistas'}), 400
        else:
            logging.warning(f"Comando no reconocido o no autorizado: {command.lower()}")
            return jsonify({'error': 'Comando no reconocido o no autorizado para tu rol'}), 400

        # Proporcionar retroalimentación con gTTS usando pygame
        try:
            # Ajustar el código de idioma para gTTS
            gtts_lang = {'en-US': 'en', 'es': 'es', 'fr': 'fr', 'ja': 'ja', 'ko': 'ko'}.get(user_language, 'en')
            tts = gTTS(text=message, lang=gtts_lang)
            temp_audio_path = f"response_{session['user_id']}_{int(datetime.now(timezone.utc).timestamp())}.mp3"
            tts.save(temp_audio_path)

            # Reproducir el audio usando pygame
            pygame.mixer.init()
            pygame.mixer.music.load(temp_audio_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            # Eliminar el archivo temporal
            os.remove(temp_audio_path)
        except Exception as e:
            logging.error(f"Error al generar retroalimentación con gTTS: {str(e)}")
            logging.info(f"Retroalimentación sin audio: {message}")

        # Manejar redirecciones para comandos de artistas
        if action == 'edit_profile':
            return jsonify({'success': True, 'action': action, 'message': message, 'redirect': url_for('artist_edit_profile')})
        elif action == 'upload_song':
            return jsonify({'success': True, 'action': action, 'message': message, 'redirect': url_for('artist_upload_song')})

        return jsonify({'success': True, 'action': action, 'message': message})

    except Exception as e:
        logging.error(f"Error general al procesar el comando de voz: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'Error al procesar el comando: {str(e)}'}), 500

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

    if not all([song_uri, song_title, song_artist]):
        return jsonify({'error': 'Faltan datos requeridos: song_uri, song_title, song_artist'}), 400

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

        form = AddToPlaylistForm()
        if form.validate_on_submit():
            try:
                playlist_id = form.playlist_id.data
                song_data = {
                    'uri': form.song_uri.data,
                    'title': form.song_title.data,
                    'artist': form.song_artist.data
                }
            except Exception as e:
                print(f"Error processing form data: {e}")
                return jsonify({'error': 'Formulario inválido'}), 400

        if not any(song['uri'] == song_uri for song in current_songs):
            current_songs.append(new_song)

        supabase.table('playlists').update({'songs': current_songs}).eq('id', playlist_id).execute()
        return jsonify({'success': True, 'message': 'Canción agregada a la playlist'})
    except Exception as e:
        return jsonify({'error': f'Error al agregar canción: {str(e)}'}), 500

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    form = PlaylistForm()
    if form.validate_on_submit():
        try:
            # Insertar la nueva playlist en Supabase
            playlist_data = {
                'user_id': session['user_id'],
                'name': form.playlist_name.data,
                'created_at': datetime.utcnow().isoformat()
            }
            response = supabase.table('playlists').insert(playlist_data).execute()
            return redirect(url_for('dashboard', playlist_success=True))
        except Exception as e:
            return redirect(url_for('dashboard', playlist_error=f"Error al crear la playlist: {str(e)}"))
    return redirect(url_for('dashboard', playlist_error="Formulario inválido"))

# Ruta para registrar el historial de escucha
@app.route('/log_listening', methods=['POST'])
def log_listening():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Usuario no autenticado'}), 401

    data = request.get_json()
    song_uri = data.get('song_uri')
    song_title = data.get('song_title')
    song_artist = data.get('song_artist')

    if not all([song_uri, song_title, song_artist]):
        return jsonify({'success': False, 'message': 'Faltan datos de la canción'}), 400

    try:
        supabase.table('listening_history').insert({
            'user_id': session['user_id'],
            'song_uri': song_uri,
            'song_title': song_title,
            'song_artist': song_artist,
            'listened_at': datetime.now(timezone.utc).isoformat()
        }).execute()
        return jsonify({'success': True, 'message': 'Canción registrada en el historial'}), 200
    except Exception as e:
        logging.error(f"Error al registrar la canción en el historial: {str(e)}")
        return jsonify({'success': False, 'message': f'Error al registrar la canción: {str(e)}'}), 500

# Caché simple en memoria para el historial de escucha
history_cache = {}

@app.route('/load_more_history', methods=['GET'])
def load_more_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Usuario no autenticado'}), 401

    offset = request.args.get('offset', default=0, type=int)
    limit = 3
    cache_key = f"{session['user_id']}_{offset}_{limit}"

    # Verificar si los datos están en caché
    if cache_key in history_cache:
        return jsonify(history_cache[cache_key])

    history_response = supabase.table('listening_history').select('*').eq('user_id', session['user_id']).order('listened_at', desc=True).range(offset, offset + limit - 1).execute()
    listening_history = history_response.data if history_response.data else []
    for entry in listening_history:
        entry['listened_at'] = entry['listened_at'].replace('Z', '+00:00')

    # Almacenar en caché
    history_cache[cache_key] = listening_history
    return jsonify(listening_history)

@app.route('/refresh_recommendations')
def refresh_recommendations():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    user_response = supabase.table('users').select('music_genre').eq('user_id', session['user_id']).execute()
    music_genre = user_response.data[0]['music_genre'] if user_response.data and user_response.data[0].get('music_genre') else 'pop'
    user_genre = music_genre.lower().replace('&', 'and').replace(',', '').replace(' ', '-') if music_genre else 'pop'

    market = 'US'  # Valor por defecto
    if 'spotify_token' in session:
        try:
            headers = {'Authorization': f'Bearer {session["spotify_token"]}'}
            me_response = requests.get(f'{SPOTIFY_API_BASE_URL}me', headers=headers)
            me_response.raise_for_status()
            user_data = me_response.json()
            market = user_data.get('country', 'US')
        except requests.exceptions.RequestException as e:
            print(f"Error al obtener mercado dinámicamente: {str(e)}. Usando 'US' como fallback.")

    recommended_songs = get_recommendations(user_genre, market, limit=8)
    return jsonify(recommended_songs)

@app.route('/player')
def player():
    if 'user_id' not in session or session.get('role') != 1:
        return redirect(url_for('login'))
    return render_template('player.html')

@app.route('/submit_comment', methods=['POST'])
def submit_comment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    form = CommentForm()
    if form.validate_on_submit():
        comment = bleach.clean(form.comment.data)
        try:
            supabase.table('comentarios').insert({
                'user_id': session['user_id'],
                'comment': comment,
                'created_at': datetime.now(timezone.utc).isoformat()
            }).execute()
            return redirect(url_for('dashboard', comment_success=True))
        except Exception as e:
            return redirect(url_for('dashboard', comment_error=f"Error al enviar comentario: {str(e)}"))
    return redirect(url_for('dashboard', comment_error="El comentario no puede estar vacío"))

@app.route('/test-spotify-token')
def test_spotify_token():
    token = 'BQA9cgsTY5DLkXh9BHwN5lqLXIHhiL_vrKrp0zC_Y7TXFfloPUhUZWeojJbLXz_b5VUq0WyKMwW9AH5SzWnj0EiI71thvTvwHA6_u-l22heBm_R4Atm44fdjK0jlRK_0F2oYDQvoPbCNL2AXDEgkTYU75hBcSAsDxverGPZ9Q5r8ZCI5qlByKoCLHs4yY6xmT2fEB_fCqLZKHHI3oy3AYZJfi62DW_qaxoBABXLK0NuLfTeaXzLpqnoo1AMKzQl55cFa'
    headers = {'Authorization': f'Bearer {token}'}

    user_response = requests.get(f'{SPOTIFY_API_BASE_URL}me', headers=headers)
    print(f"Prueba /v1/me con token manual: {user_response.status_code}, {user_response.text}")

    params = {
        'seed_genres': 'pop',
        'limit': 3,
        'market': 'CO'
    }
    rec_response = requests.get(f'{SPOTIFY_API_BASE_URL}recommendations', headers=headers, params=params)
    print(f"Prueba /v1/recommendations con token manual: {rec_response.status_code}, {rec_response.text}")

    top_tracks_response = requests.get(f'{SPOTIFY_API_BASE_URL}me/top/tracks', headers=headers, params={'limit': 10, 'time_range': 'medium_term'})
    print(f"Prueba /v1/me/top/tracks con token manual: {top_tracks_response.status_code}, {top_tracks_response.text}")

    return "Prueba completada. Revisa el log en la terminal."

@app.route('/check_role', methods=['GET'])
def check_role():
    if 'user_id' in session and session.get('role') == 1:
        return jsonify({'role': 1})
    return jsonify({'role': 0})

@app.route('/save_player_state', methods=['POST'])
def save_player_state():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Usuario no autenticado'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No se enviaron datos'}), 400

    user_id = session['user_id']
    track_queue = data.get('track_queue', [])
    current_index = data.get('current_index', 0)
    is_playing = data.get('is_playing', False)
    position_ms = data.get('position_ms', 0)
    volume = data.get('volume', 0.5)
    shuffle_mode = data.get('shuffle_mode', False)
    repeat_mode = data.get('repeat_mode', 'none')
    context = data.get('context', 'user')

    # Validaciones
    if not isinstance(track_queue, list):
        return jsonify({'success': False, 'message': 'track_queue debe ser una lista'}), 400
    if not isinstance(current_index, int) or current_index < 0:
        return jsonify({'success': False, 'message': 'current_index debe ser un entero no negativo'}), 400
    if not isinstance(position_ms, int) or position_ms < 0:
        return jsonify({'success': False, 'message': 'position_ms debe ser un entero no negativo'}), 400
    if not isinstance(volume, (int, float)) or not 0 <= volume <= 1:
        return jsonify({'success': False, 'message': 'volume debe estar entre 0 y 1'}), 400
    if context not in ['admin', 'user']:
        return jsonify({'success': False, 'message': 'context debe ser "admin" o "user"'}), 400

    try:
        # Verificar si ya existe un estado para este user_id y context
        existing_state = supabase.table('player_state').select('*').eq('user_id', user_id).eq('context', context).execute()

        state_data = {
            'user_id': user_id,
            'track_queue': track_queue,
            'current_index': current_index,
            'is_playing': is_playing,
            'position_ms': position_ms,
            'volume': volume,
            'shuffle_mode': shuffle_mode,
            'repeat_mode': repeat_mode,
            'context': context,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        if existing_state.data:
            # Actualizar estado existente
            supabase.table('player_state').update(state_data).eq('user_id', user_id).eq('context', context).execute()
        else:
            # Insertar nuevo estado
            supabase.table('player_state').insert(state_data).execute()

        return jsonify({'success': True, 'message': 'Estado del reproductor guardado correctamente'}), 200
    except Exception as e:
        logging.error(f"Error al guardar el estado del reproductor: {str(e)}")
        return jsonify({'success': False, 'message': f'Error al guardar el estado: {str(e)}'}), 500

@app.route('/load_player_state', methods=['GET'])
def load_player_state():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Usuario no autenticado'}), 401

    user_id = session['user_id']
    context = request.args.get('context', 'user')  # Obtener context de los parámetros de consulta

    if context not in ['admin', 'user']:
        return jsonify({'success': False, 'message': 'context debe ser "admin" o "user"'}), 400

    try:
        state = supabase.table('player_state').select('*').eq('user_id', user_id).eq('context', context).execute()

        if state.data:
            return jsonify({
                'success': True,
                'state': {
                    'track_queue': state.data[0]['track_queue'],
                    'current_index': state.data[0]['current_index'],
                    'is_playing': state.data[0]['is_playing'],
                    'position_ms': state.data[0]['position_ms'],
                    'volume': state.data[0]['volume'],
                    'shuffle_mode': state.data[0]['shuffle_mode'],
                    'repeat_mode': state.data[0]['repeat_mode'],
                    'context': state.data[0]['context']
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'No se encontró estado para este usuario y contexto'
            }), 404
    except Exception as e:
        logging.error(f"Error al cargar el estado del reproductor: {str(e)}")
        return jsonify({'success': False, 'message': f'Error al cargar el estado: {str(e)}'}), 500

@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def handle_devtools_json():
    return jsonify({}), 200  # Return an empty JSON response

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
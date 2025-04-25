from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from supabase import create_client, Client
import time
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import uuid

# Cargar variables de entorno
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configurar el proxy de OWASP ZAP
chrome_options = Options()
chrome_options.add_argument('--proxy-server=http://localhost:8080')

# Configurar el WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def setup_test_user():
    """Crear un usuario de prueba en Supabase"""
    try:
        # Eliminar usuario de prueba si ya existe
        response = supabase.table('users').select('email').eq('email', 'testuser@example.com').execute()
        if response.data:
            supabase.table('users').delete().eq('email', 'testuser@example.com').execute()

        # Crear usuario de prueba
        user_id = str(uuid.uuid4())
        hashed_password = generate_password_hash('testpassword', method='pbkdf2:sha256', salt_length=16)
        supabase.table('users').insert({
            'email': 'testuser@example.com',
            'name': 'Test User',
            'music_genre': 'rock',
            'password': hashed_password,
            'role': 2,
            'user_id': user_id
        }).execute()
        return True
    except Exception as e:
        print(f"Error al crear usuario de prueba: {e}")
        return False

def test_create_playlist():
    try:
        # Crear usuario de prueba
        if not setup_test_user():
            raise Exception("No se pudo crear el usuario de prueba")

        # Abrir la app Tuning localmente
        driver.get('http://127.0.0.1:5000')

        # Simular login
        try:
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'email'))
            )
            email_field.send_keys('testuser@example.com')

            driver.find_element(By.ID, 'password').send_keys('testpassword')
            driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        except Exception as e:
            print(f"Error al iniciar sesión: {e}")
            raise

        # Crear una playlist
        try:
            playlist_name_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'playlist-name'))
            )
            playlist_name_field.send_keys('My Test Playlist')

            driver.find_element(By.ID, 'submit-playlist').click()

            # Verificar si la playlist se creó correctamente
            playlist = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//h3[@class='text-lg font-medium playlist-title' and text()='My Test Playlist']"))
            )
            assert playlist is not None, "Playlist no se creó correctamente"
        except Exception as e:
            print(f"Error al crear playlist: {e}")
            raise

        # Reproducir una canción
        try:
            play_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'play-button'))
            )
            play_button.click()
            time.sleep(2)  # Esperar la reproducción
            print("Botón de reproducción cliqueado con éxito")
        except Exception as e:
            print(f"Error al reproducir canción: {e}")
            raise

        print("✅ Prueba de creación de playlist y reproducción: ÉXITO")

    except Exception as e:
        print(f"❌ Error en la prueba: {e}")
    finally:
        # Limpiar: Eliminar usuario de prueba
        supabase.table('users').delete().eq('email', 'testuser@example.com').execute()
        driver.quit()

if __name__ == "__main__":
    test_create_playlist()
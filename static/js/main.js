document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const loadMoreButton = document.getElementById('load-more-history');
    const playButtons = document.querySelectorAll('.play-button');
    const playPlaylistButtons = document.querySelectorAll('.play-playlist');
    const playRecommendedButton = document.querySelector('.play-recommended');
    const playAdminPlaylistButton = document.querySelector('.play-admin-playlist');
    const playPauseButton = document.getElementById('play-pause');
    const prevTrackButton = document.getElementById('prev-track');
    const nextTrackButton = document.getElementById('next-track');
    const playerTitle = document.getElementById('player-title');
    const playerArtist = document.getElementById('player-artist');
    const playerAlbum = document.getElementById('player-album');
    const progressBar = document.getElementById('progress-bar');
    const currentTimeLabel = document.getElementById('current-time');
    const durationLabel = document.getElementById('duration');
    const toggleSongsButtons = document.querySelectorAll('.toggle-songs');

    let historyOffset = 3;
    let player;
    let deviceId;
    let currentTrackUri = null;
    let isPlaying = false;
    let trackQueue = [];
    let currentIndex = 0;
    let trackDurationMs = 0;

    // Función para formatear el tiempo en mm:ss
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    // Inicializar el Spotify Playback SDK
    window.onSpotifyWebPlaybackSDKReady = () => {
        if (!window.spotifyToken) {
            console.error('Token de Spotify no disponible');
            return;
        }

        player = new Spotify.Player({
            name: 'Tuning Web Player',
            getOAuthToken: cb => { cb(window.spotifyToken); },
            volume: 0.5
        });

        // Errores
        player.addListener('initialization_error', ({ message }) => {
            console.error('Initialization Error:', message);
        });
        player.addListener('authentication_error', ({ message }) => {
            console.error('Authentication Error:', message);
        });
        player.addListener('account_error', ({ message }) => {
            console.error('Account Error:', message);
        });
        player.addListener('playback_error', ({ message }) => {
            console.error('Playback Error:', message);
        });

        // Estado del reproductor
        player.addListener('player_state_changed', state => {
            if (!state) return;

            isPlaying = !state.paused;
            playPauseButton.textContent = isPlaying ? 'Pausar' : 'Reproducir';

            if (state.track_window.current_track) {
                const track = state.track_window.current_track;
                playerTitle.textContent = track.name;
                playerArtist.textContent = track.artists.map(artist => artist.name).join(', ');
                playerAlbum.src = track.album.images[0]?.url || 'https://picsum.photos/50/50?random=1';
                currentTrackUri = track.uri;

                // Actualizar duración y barra de progreso
                trackDurationMs = state.duration;
                progressBar.max = trackDurationMs;
                const progressMs = state.position;
                progressBar.value = progressMs;
                currentTimeLabel.textContent = formatTime(progressMs / 1000);
                durationLabel.textContent = formatTime(trackDurationMs / 1000);
            }

            // Reproducción automática de la siguiente canción
            if (state.paused && state.position === 0 && trackQueue.length > 0 && currentIndex < trackQueue.length - 1) {
                currentIndex++;
                playTrack(trackQueue[currentIndex]);
                updateTrackInfo(trackQueue[currentIndex]);
            }
        });

        // Dispositivo listo
        player.addListener('ready', ({ device_id }) => {
            console.log('Dispositivo listo con ID:', device_id);
            deviceId = device_id;
        });

        // Conectar el reproductor
        player.connect();
    };

    // Notificaciones
    const showNotification = (message, type) => {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded shadow-md text-white ${type === 'success' ? 'bg-green-500' : 'bg-red-500'}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => {
            notification.remove();
        }, 3000);
    };

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('playlist_success') === 'True') {
        showNotification('¡Playlist creada con éxito!', 'success');
    }
    if (urlParams.get('playlist_error')) {
        showNotification(urlParams.get('playlist_error'), 'error');
    }

    // Registrar en el historial de escucha
    const logListeningHistory = async (songUri, songTitle, songArtist) => {
        try {
            const response = await fetch('/log_listening', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    song_uri: songUri,
                    song_title: songTitle,
                    song_artist: songArtist,
                }),
            });
            if (!response.ok) {
                console.error('Error al registrar el historial de escucha');
            }
        } catch (error) {
            console.error('Error:', error);
        }
    };

    // Reproducir una canción
    const playTrack = async (uri) => {
        if (!deviceId) {
            console.error('Dispositivo no está listo');
            return;
        }

        try {
            await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${window.spotifyToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    uris: [uri],
                }),
            });
            currentTrackUri = uri;
        } catch (error) {
            console.error('Error al reproducir:', error);
        }
    };

    // Actualizar información del reproductor
    const updateTrackInfo = (uri) => {
        const button = Array.from(document.querySelectorAll('.play-button')).find(btn => btn.getAttribute('data-uri') === uri);
        if (button) {
            const title = button.getAttribute('data-title') || button.parentElement.querySelector('h3')?.textContent || button.parentElement.querySelector('p')?.textContent.split(' - ')[0];
            const artist = button.getAttribute('data-artist') || button.parentElement.querySelector('p')?.textContent.split(' - ')[1] || button.parentElement.querySelector('p')?.textContent;
            const albumSrc = button.parentElement.querySelector('img')?.src || 'https://picsum.photos/50/50?random=1';

            playerTitle.textContent = title;
            playerArtist.textContent = artist;
            playerAlbum.src = albumSrc;
        }
    };

    // Botones de reproducción individual
    playButtons.forEach(button => {
        button.addEventListener('click', () => {
            const uri = button.getAttribute('data-uri');
            const title = button.getAttribute('data-title') || button.parentElement.querySelector('h3')?.textContent || button.parentElement.querySelector('p')?.textContent.split(' - ')[0];
            const artist = button.getAttribute('data-artist') || button.parentElement.querySelector('p')?.textContent.split(' - ')[1] || button.parentElement.querySelector('p')?.textContent;
            const playlistId = button.getAttribute('data-playlist-id');

            // Construir la cola basada en la fuente
            if (playlistId) {
                const songsList = document.querySelector(`.songs-list[data-playlist-id="${playlistId}"]`);
                trackQueue = Array.from(songsList.querySelectorAll('.play-button')).map(btn => btn.getAttribute('data-uri'));
                currentIndex = trackQueue.indexOf(uri);
            } else {
                trackQueue = [uri];
                currentIndex = 0;
            }

            playTrack(uri);
            logListeningHistory(uri, title, artist);
        });
    });

    // Botones de reproducir toda la playlist
    playPlaylistButtons.forEach(button => {
        button.addEventListener('click', () => {
            const playlistId = button.getAttribute('data-playlist-id');
            const songsList = document.querySelector(`.songs-list[data-playlist-id="${playlistId}"]`);
            trackQueue = Array.from(songsList.querySelectorAll('.play-button')).map(btn => btn.getAttribute('data-uri'));
            currentIndex = 0;
            if (trackQueue.length > 0) {
                playTrack(trackQueue[currentIndex]);
                updateTrackInfo(trackQueue[currentIndex]);
                logListeningHistory(
                    trackQueue[currentIndex],
                    songsList.querySelector('.play-button').getAttribute('data-title'),
                    songsList.querySelector('.play-button').getAttribute('data-artist')
                );
            }
        });
    });

    // Botón de reproducir todas las canciones recomendadas
    playRecommendedButton?.addEventListener('click', () => {
        const recommendedSection = document.querySelector('h2.text-2xl.font-semibold.mb-4 + .flex + .grid');
        if (recommendedSection) {
            trackQueue = Array.from(recommendedSection.querySelectorAll('.play-button')).map(btn => btn.getAttribute('data-uri'));
            currentIndex = 0;
            if (trackQueue.length > 0) {
                playTrack(trackQueue[currentIndex]);
                updateTrackInfo(trackQueue[currentIndex]);
                logListeningHistory(
                    trackQueue[currentIndex],
                    recommendedSection.querySelector('.play-button').getAttribute('data-title'),
                    recommendedSection.querySelector('.play-button').getAttribute('data-artist')
                );
            }
        }
    });

    // Botón de reproducir toda la playlist del administrador
    playAdminPlaylistButton?.addEventListener('click', () => {
        const adminSection = document.querySelector('h2.text-2xl.font-semibold.mb-4.mt-8 + .flex + .grid');
        if (adminSection) {
            trackQueue = Array.from(adminSection.querySelectorAll('.play-button')).map(btn => btn.getAttribute('data-uri'));
            currentIndex = 0;
            if (trackQueue.length > 0) {
                playTrack(trackQueue[currentIndex]);
                updateTrackInfo(trackQueue[currentIndex]);
                logListeningHistory(
                    trackQueue[currentIndex],
                    adminSection.querySelector('.play-button').getAttribute('data-title'),
                    adminSection.querySelector('.play-button').getAttribute('data-artist')
                );
            }
        }
    });

    // Botón de reproducir/pausar
    playPauseButton.addEventListener('click', () => {
        if (isPlaying) {
            player.pause();
        } else {
            player.resume();
        }
    });

    // Botón de canción anterior
    prevTrackButton.addEventListener('click', () => {
        if (currentIndex > 0) {
            currentIndex--;
            playTrack(trackQueue[currentIndex]);
            updateTrackInfo(trackQueue[currentIndex]);
        }
    });

    // Botón de siguiente pista
    nextTrackButton.addEventListener('click', () => {
        if (currentIndex < trackQueue.length - 1) {
            currentIndex++;
            playTrack(trackQueue[currentIndex]);
            updateTrackInfo(trackQueue[currentIndex]);
        }
    });

    // Barra de progreso
    progressBar.addEventListener('input', async () => {
        if (!currentTrackUri || !trackDurationMs) return;

        const positionMs = parseInt(progressBar.value); // Valor directo en milisegundos
        try {
            await fetch(`https://api.spotify.com/v1/me/player/seek?position_ms=${positionMs}&device_id=${deviceId}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${window.spotifyToken}`,
                },
            });
            currentTimeLabel.textContent = formatTime(positionMs / 1000);
        } catch (error) {
            console.error('Error al ajustar la posición:', error);
        }
    });

    // Mostrar/ocultar canciones adicionales en playlists
    toggleSongsButtons.forEach(button => {
        button.addEventListener('click', () => {
            const extraSongs = button.previousElementSibling;
            if (extraSongs.classList.contains('hidden')) {
                extraSongs.classList.remove('hidden');
                button.textContent = 'Ver Menos';
            } else {
                extraSongs.classList.add('hidden');
                button.textContent = 'Ver Más';
            }
        });
    });

    // Buscador
    if (searchInput && searchResults) {
        searchInput.addEventListener('input', async (e) => {
            const query = e.target.value.trim();
            if (query.length < 3) {
                searchResults.innerHTML = '';
                return;
            }

            try {
                const response = await fetch(`/search_songs?query=${encodeURIComponent(query)}`);
                const results = await response.json();

                if (response.ok) {
                    searchResults.innerHTML = results.map(song => {
                        const playlistOptions = window.playlists && window.playlists.length > 0
                            ? window.playlists.map(playlist => 
                                `<option value="${playlist.id}">${playlist.name}</option>`
                            ).join('')
                            : '<option value="">No tienes playlists</option>';

                        return `
                            <div class="bg-white dark:bg-gray-700 p-3 rounded-lg shadow-md">
                                <img src="${song.image_url}" alt="${song.title}" class="w-full h-32 object-cover rounded-md mb-2">
                                <h3 class="text-base font-semibold truncate">${song.title}</h3>
                                <p class="text-gray-600 dark:text-gray-300 text-sm truncate">${song.artist}</p>
                                <button class="play-button bg-green-500 text-white py-1 px-2 rounded hover:bg-green-600 transition mt-2" data-uri="${song.uri}" data-title="${song.title}" data-artist="${song.artist}">Reproducir</button>
                                <form class="add-to-playlist-form mt-2 flex items-center gap-2" data-uri="${song.uri}" data-title="${song.title}" data-artist="${song.artist}">
                                    <input type="hidden" name="song_uri" value="${song.uri}">
                                    <input type="hidden" name="song_title" value="${song.title}">
                                    <input type="hidden" name="song_artist" value="${song.artist}">
                                    <select name="playlist_id" class="p-1 text-sm border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white">
                                        <option value="">Seleccionar Playlist</option>
                                        ${playlistOptions}
                                    </select>
                                    <button type="submit" class="bg-blue-500 text-white py-1 px-2 text-sm rounded hover:bg-blue-600 transition">Agregar</button>
                                </form>
                            </div>
                        `;
                    }).join('');

                    // Agregar eventos a los nuevos botones de reproducción
                    searchResults.querySelectorAll('.play-button').forEach(button => {
                        button.addEventListener('click', () => {
                            const uri = button.getAttribute('data-uri');
                            const title = button.getAttribute('data-title');
                            const artist = button.getAttribute('data-artist');

                            trackQueue = [uri];
                            currentIndex = 0;
                            playTrack(uri);
                            logListeningHistory(uri, title, artist);
                            updateTrackInfo(uri);
                        });
                    });

                    // Agregar eventos a los formularios de agregar a playlist
                    searchResults.querySelectorAll('.add-to-playlist-form').forEach(form => {
                        form.addEventListener('submit', async (e) => {
                            e.preventDefault();
                            const formData = new FormData(form);
                            try {
                                const response = await fetch('/add_to_playlist', {
                                    method: 'POST',
                                    body: formData,
                                });
                                const result = await response.json();
                                if (response.ok) {
                                    showNotification('Canción agregada a la playlist', 'success');
                                } else {
                                    showNotification(result.error || 'Error al agregar la canción', 'error');
                                }
                            } catch (error) {
                                console.error('Error al agregar canción:', error);
                                showNotification('Error al agregar la canción', 'error');
                            }
                        });
                    });
                } else {
                    searchResults.innerHTML = '<p class="text-red-500">Error al buscar canciones.</p>';
                }
            } catch (error) {
                console.error('Error:', error);
                searchResults.innerHTML = '<p class="text-red-500">Error al buscar canciones.</p>';
            }
        });
    }

    // Manejar todos los formularios de agregar a playlist
    document.querySelectorAll('.add-to-playlist-form').forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            try {
                const response = await fetch('/add_to_playlist', {
                    method: 'POST',
                    body: formData,
                });
                const result = await response.json();
                if (response.ok) {
                    showNotification('Canción agregada a la playlist', 'success');
                } else {
                    showNotification(result.error || 'Error al agregar la canción', 'error');
                }
            } catch (error) {
                console.error('Error al agregar canción:', error);
                showNotification('Error al agregar la canción', 'error');
            }
        });
    });

// Manejar el formulario de creación de playlists
const createPlaylistForm = document.querySelector('.create-playlist-form');
if (createPlaylistForm) {
    createPlaylistForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(createPlaylistForm);
        try {
            const response = await fetch('/create_playlist', {
                method: 'POST',
                body: formData,
            });
            const result = await response.json();
            if (response.ok) {
                showNotification('Playlist creada con éxito', 'success');
                // Opcional: Actualizar la UI dinámicamente para mostrar la nueva playlist
                createPlaylistForm.reset(); // Limpiar el formulario
            } else {
                showNotification(result.error || 'Error al crear la playlist', 'error');
            }
        } catch (error) {
            console.error('Error al crear playlist:', error);
            showNotification('Error al crear la playlist', 'error');
        }
    });
}

    // Cargar más historial de escucha
    if (loadMoreButton) {
        loadMoreButton.addEventListener('click', async () => {
            try {
                const response = await fetch(`/load_more_history?offset=${historyOffset}`);
                const newEntries = await response.json();
                
                if (newEntries.length > 0) {
                    const historyContainer = document.getElementById('listening-history');
                    newEntries.forEach(entry => {
                        const entryDiv = document.createElement('div');
                        entryDiv.className = 'bg-white dark:bg-gray-800 p-4 rounded-lg shadow flex items-center justify-between';
                        entryDiv.innerHTML = `
                            <div>
                                <p class="text-lg font-medium">${entry.song_title} - ${entry.song_artist}</p>
                                <p class="text-gray-600 dark:text-gray-300">Escuchada el: ${new Date(entry.listened_at).toLocaleString()}</p>
                            </div>
                            <button class="play-button bg-green-500 text-white py-1 px-2 rounded hover:bg-green-600 transition" data-uri="${entry.song_uri}" data-title="${entry.song_title}" data-artist="${entry.song_artist}">Reproducir</button>
                        `;
                        historyContainer.appendChild(entryDiv);

                        // Agregar evento al nuevo botón de reproducción
                        entryDiv.querySelector('.play-button').addEventListener('click', () => {
                            const uri = entry.song_uri;
                            const title = entry.song_title;
                            const artist = entry.song_artist;

                            trackQueue = [uri];
                            currentIndex = 0;
                            playTrack(uri);
                            logListeningHistory(uri, title, artist);
                            updateTrackInfo(uri);
                        });
                    });
                    historyOffset += newEntries.length;
                } else {
                    loadMoreButton.textContent = 'No hay más entradas';
                    loadMoreButton.disabled = true;
                }
            } catch (error) {
                console.error('Error al cargar más historial:', error);
            }
        });
    }
// Slider para Canciones Recomendadas
    const recommendedSlider = document.getElementById('recommended-slider');
if (recommendedSlider) {
    const recommendedCards = recommendedSlider.children;
    const recommendedCardWidth = recommendedCards[0]?.offsetWidth + 16 || 216; // ancho + margin
    let recommendedIndex = 0;

    function updateRecommendedSlider() {
        recommendedSlider.style.transform = `translateX(${-recommendedIndex * recommendedCardWidth}px)`;
    }

    document.getElementById('recommended-right-btn').addEventListener('click', () => {
        recommendedIndex = (recommendedIndex + 1) % recommendedCards.length;
        updateRecommendedSlider();
    });

    document.getElementById('recommended-left-btn').addEventListener('click', () => {
        recommendedIndex = (recommendedIndex - 1 + recommendedCards.length) % recommendedCards.length;
        updateRecommendedSlider();
    });

    window.addEventListener('resize', updateRecommendedSlider);
    updateRecommendedSlider();
}

// Slider para Playlist del Administrador
const adminSlider = document.getElementById('admin-slider');
if (adminSlider) {
    const adminCards = adminSlider.children;
    const adminCardWidth = adminCards[0]?.offsetWidth + 16 || 216; // ancho + margin
    let adminIndex = 0;

    function updateAdminSlider() {
        adminSlider.style.transform = `translateX(${-adminIndex * adminCardWidth}px)`;
    }

    document.getElementById('admin-right-btn').addEventListener('click', () => {
        adminIndex = (adminIndex + 1) % adminCards.length;
        updateAdminSlider();
    });

    document.getElementById('admin-left-btn').addEventListener('click', () => {
        adminIndex = (adminIndex - 1 + adminCards.length) % adminCards.length;
        updateAdminSlider();
    });

    window.addEventListener('resize', updateAdminSlider);
    updateAdminSlider();
}
// Escuchar mensajes del iframe de tunings.html para reproducir canciones
window.addEventListener('message', (event) => {
    if (event.data.type === 'playTrack') {
        const { uri, title, artist } = event.data;
        trackQueue = [uri];
        currentIndex = 0;
        playTrack(uri);
        logListeningHistory(uri, title, artist);
        updateTrackInfo(uri);
    }
});

});

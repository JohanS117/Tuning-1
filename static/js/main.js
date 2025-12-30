document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    const loadMoreButton = document.getElementById('load-more-history');
    const playButtons = document.querySelectorAll('.play-button');
    const playPlaylistButtons = document.querySelectorAll('.play-playlist');
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
    const refreshRecommendationsButton = document.getElementById('refresh-recommendations');


    let historyOffset = 3;
    let player;
    let deviceId;
    let currentTrackUri = null;
    let isPlaying = false;
    let trackQueue = [];
    let currentIndex = 0;
    let trackDurationMs = 0;
    let activeNotifications = []; // Arreglo para apilar notificaciones
    let isAdmin = false;
    fetch('/check_role')
        .then(response => response.json())
        .then(data => {
            isAdmin = data.role === 1;
            initializePlayer();
        })
        .catch(error => {
            console.error('Error al verificar rol:', error);
            initializePlayer();
        });

    function initializePlayer() {
        if (isAdmin) {
            // Para administradores, no inicializar el reproductor local
            console.log('Usuario administrador detectado. Usando reproductor en iframe.');
            return;
        }

            // Inicialización del reproductor de Spotify
    window.onSpotifyWebPlaybackSDKReady = () => {
        if (!window.spotifyToken) {
            console.warn('Token de Spotify no disponible. Reproducción no disponible.');
            showNotification('Por favor, conecta tu cuenta de Spotify para reproducir.', 'error');
            return;
        }

        player = new Spotify.Player({
            name: 'Tuning Web Player',
            getOAuthToken: cb => { cb(window.spotifyToken); },
            volume: 0.5
        });

        player.addListener('initialization_error', ({ message }) => {
            console.error('Error de inicialización del reproductor:', message);
            showNotification('Error al inicializar el reproductor. Por favor, intenta de nuevo.', 'error');
        });

        player.addListener('authentication_error', ({ message }) => {
            console.error('Error de autenticación:', message);
            showNotification('Error de autenticación con Spotify. Por favor, reconecta tu cuenta.', 'error');
        });

        player.addListener('account_error', ({ message }) => {
            console.error('Error de cuenta:', message);
            showNotification('Error de cuenta: ' + message, 'error');
        });

        player.addListener('playback_error', ({ message }) => {
            console.error('Error de reproducción:', message);
            showNotification('Error al reproducir la canción: ' + message, 'error');
        });

        player.addListener('player_state_changed', state => {
            if (!state) return;

            isPlaying = !state.paused;
            playPauseButton.textContent = isPlaying ? '⏸️' : '⏯️';

            if (state.track_window.current_track) {
                const track = state.track_window.current_track;
                playerTitle.textContent = track.name;
                playerArtist.textContent = track.artists.map(artist => artist.name).join(', ');
                playerAlbum.src = track.album.images[0]?.url || 'https://picsum.photos/50/50?random=1';
                currentTrackUri = track.uri;

                trackDurationMs = state.duration;
                progressBar.max = trackDurationMs;
                const progressMs = state.position;
                progressBar.value = progressMs;
                currentTimeLabel.textContent = formatTime(progressMs / 1000);
                durationLabel.textContent = formatTime(trackDurationMs / 1000);
            }

            if (state.paused && state.position === 0 && trackQueue.length > 0 && currentIndex < trackQueue.length - 1) {
                currentIndex++;
                playTrack(trackQueue[currentIndex]);
                updateTrackInfo(trackQueue[currentIndex]);
            }
        });

        player.addListener('ready', ({ device_id }) => {
            console.log('Dispositivo listo con ID:', device_id);
            deviceId = device_id;
            localStorage.setItem('deviceId', deviceId); // Guardar deviceId
            showNotification('Reproductor listo. ¡Puedes empezar a reproducir canciones!', 'success');
        });

        player.addListener('not_ready', ({ device_id }) => {
            console.warn('Dispositivo no listo con ID:', device_id);
            showNotification('El reproductor no está listo. Por favor, intenta de nuevo más tarde.', 'error');
        });

        player.connect().then(success => {
            if (success) {
                console.log('Reproductor conectado exitosamente.');
            } else {
                console.error('Fallo al conectar el reproductor.');
                showNotification('Error al conectar el reproductor. Por favor, intenta de nuevo.', 'error');
            }
        });
}};

    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    function updateTrackInfo(uri) {
        const button = Array.from(document.querySelectorAll('.play-button')).find(btn => btn.getAttribute('data-uri') === uri);
        if (button) {
            const title = button.getAttribute('data-title') || button.parentElement.querySelector('h3')?.textContent || button.parentElement.querySelector('p')?.textContent.split(' - ')[0];
            const artist = button.getAttribute('data-artist') || button.parentElement.querySelector('p')?.textContent.split(' - ')[1] || button.parentElement.querySelector('p')?.textContent;
            const albumSrc = button.parentElement.querySelector('img')?.src || 'https://picsum.photos/50/50?random=1';

            playerTitle.textContent = title;
            playerArtist.textContent = artist;
            playerAlbum.src = albumSrc;
        }
    }

    // Nueva función showNotification con Anime.js y apilamiento
    const showNotification = (message, type = 'info') => {
        const header = document.querySelector('header');
        const headerHeight = header ? header.offsetHeight : 0;

        // Crear el elemento de notificación
        const notification = document.createElement('div');
        notification.className = `fixed right-4 p-4 rounded-lg shadow-lg text-white z-60 transition-all duration-300`;
        notification.textContent = message;

        // Estilos según el tipo de notificación
        const styles = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            info: 'bg-blue-500',
            warning: 'bg-yellow-500'
        };
        notification.classList.add(styles[type] || styles.info);

        // Agregar al DOM
        document.body.appendChild(notification);
        activeNotifications.push(notification);

        // Calcular la posición inicial
        updateNotificationPositions(headerHeight);

        // Animación de entrada con Anime.js
        anime({
            targets: notification,
            translateX: [300, 0],
            opacity: [0, 1],
            easing: 'easeOutQuad',
            duration: 400
        });

        // Programar la eliminación después de 3 segundos
        setTimeout(() => {
            // Animación de salida
            anime({
                targets: notification,
                translateX: 300,
                opacity: 0,
                easing: 'easeInQuad',
                duration: 400,
                complete: () => {
                    notification.remove();
                    activeNotifications = activeNotifications.filter(n => n !== notification);
                    updateNotificationPositions(headerHeight);
                }
            });
        }, 3000);
    };

    // Función para actualizar las posiciones de las notificaciones
    function updateNotificationPositions(headerHeight) {
        activeNotifications.forEach((notification, index) => {
            const topPosition = headerHeight + 16 + (index * (notification.offsetHeight + 8));
            notification.style.top = `${topPosition}px`;
        });
    }

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('playlist_success') === 'True') {
        showNotification('¡Playlist creada con éxito!', 'success');
    }
    if (urlParams.get('playlist_error')) {
        showNotification(urlParams.get('playlist_error'), 'error');
    }

    async function logListeningHistory(songUri, songTitle, songArtist) {
    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const response = await fetch('/log_listening', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({
                song_uri: songUri,
                song_title: songTitle,
                song_artist: songArtist
            })
        });
        if (!response.ok) {
            throw new Error('Error al registrar el historial de escucha');
        }
        const data = await response.json();
        console.log('Historial registrado:', data);
    } catch (error) {
        console.error('Error al registrar el historial de escucha:', error);
        showNotification('Error al registrar el historial de escucha', 'error');
    }
}

    async function playTrack(songUri) {
        if (!deviceId) {
            console.warn('Dispositivo no está listo');
            showNotification('El reproductor no está listo. Por favor, espera un momento.', 'error');
            return;
        }

        try {
            // Verificar dispositivos disponibles
            const response = await fetch('https://api.spotify.com/v1/me/player/devices', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${window.spotifyToken}`,
                },
            });
            const data = await response.json();
            console.log('Dispositivos disponibles:', data);

            const device = data.devices.find(d => d.id === deviceId);
            if (!device || !device.is_active) {
                await fetch('https://api.spotify.com/v1/me/player', {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${window.spotifyToken}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        device_ids: [deviceId],
                        play: false
                    }),
                });
                console.log('Dispositivo activado:', deviceId);
            }

            // Reproducir la canción
            const playResponse = await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${window.spotifyToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    uris: [songUri],
                }),
            });

            if (playResponse.status === 204) {
                currentTrackUri = songUri;
            } else {
                const errorData = await playResponse.json();
                console.error('Error al reproducir:', errorData);
                if (errorData.error?.status === 403) {
                    showNotification('No se puede reproducir: se requiere una suscripción Premium de Spotify.', 'error');
                } else {
                    showNotification('Error al reproducir la canción: ' + (errorData.error?.message || 'Desconocido'), 'error');
                }
            }
        } catch (error) {
            console.error('Error al reproducir:', error);
            showNotification('Error al reproducir la canción: ' + error.message, 'error');
        }
    }

    //Eventos de reproducción para administradores
    playButtons.forEach(button => {
        button.addEventListener('click', () => {
            const uri = button.getAttribute('data-uri');
            const title = button.getAttribute('data-title') || button.parentElement.querySelector('h3')?.textContent || button.parentElement.querySelector('p')?.textContent.split(' - ')[0];
            const artist = button.getAttribute('data-artist') || button.parentElement.querySelector('p')?.textContent.split(' - ')[1] || button.parentElement.querySelector('p')?.textContent;
            const imageUrl = button.getAttribute('data-image-url') || button.parentElement.querySelector('img')?.src || 'https://picsum.photos/50/50?random=1';
            const playlistId = button.getAttribute('data-playlist-id');

            if (isAdmin) {
                // Enviar comando al iframe para administradores
                const playerIframe = document.getElementById('player-iframe');
                if (playerIframe) {
                    if (playlistId) {
                        const songsList = document.querySelector(`.songs-list[data-playlist-id="${playlistId}"]`);
                        const songs = Array.from(songsList.querySelectorAll('.play-button')).map(btn => ({
                            uri: btn.getAttribute('data-uri'),
                            title: btn.getAttribute('data-title'),
                            artist: btn.getAttribute('data-artist'),
                            image_url: btn.getAttribute('data-image-url') || 'https://picsum.photos/50/50?random=1'
                        }));
                        playerIframe.contentWindow.postMessage({
                            type: 'playPlaylist',
                            songs: songs
                        }, '*');
                    } else {
                        playerIframe.contentWindow.postMessage({
                            type: 'playTrack',
                            uri: uri,
                            title: title,
                            artist: artist,
                            image_url: imageUrl
                        }, '*');
                    }
                    logListeningHistory(uri, title, artist);
                    showNotification('Reproduciendo en el reproductor en segundo plano', 'success');
                } else {
                    showNotification('Error: Reproductor en segundo plano no disponible', 'error');
                }
                return;
            }

            // Lógica para usuarios no administradores
            if (playlistId) {
                const songsList = document.querySelector(`.songs-list[data-playlist-id="${playlistId}"]`);
                trackQueue = Array.from(songsList.querySelectorAll('.play-button')).map(btn => btn.getAttribute('data-uri'));
                currentIndex = trackQueue.indexOf(uri);
            } else {
                trackQueue = [uri];
                currentIndex = 0;
            }

            if (window.spotifyToken) {
                playTrack(uri);
                logListeningHistory(uri, title, artist);
                updateTrackInfo(uri);
            } else {
                showNotification('Por favor, conecta tu cuenta de Spotify para reproducir.', 'error');
            }
        });
    });

    playPlaylistButtons.forEach(button => {
        button.addEventListener('click', () => {
            const playlistId = button.getAttribute('data-playlist-id');
            const songsList = document.querySelector(`.songs-list[data-playlist-id="${playlistId}"]`);
            const songs = Array.from(songsList.querySelectorAll('.play-button')).map(btn => ({
                uri: btn.getAttribute('data-uri'),
                title: btn.getAttribute('data-title'),
                artist: btn.getAttribute('data-artist'),
                image_url: btn.getAttribute('data-image-url') || 'https://picsum.photos/50/50?random=1'
            }));

            if (isAdmin) {
                // Enviar comando al iframe para administradores
                const playerIframe = document.getElementById('player-iframe');
                if (playerIframe) {
                    playerIframe.contentWindow.postMessage({
                        type: 'playPlaylist',
                        songs: songs
                    }, '*');
                    logListeningHistory(
                        songs[0].uri,
                        songs[0].title,
                        songs[0].artist
                    );
                    showNotification('Reproduciendo playlist en el reproductor en segundo plano', 'success');
                } else {
                    showNotification('Error: Reproductor en segundo plano no disponible', 'error');
                }
                return;
            }

            // Lógica para usuarios no administradores
            trackQueue = songs.map(song => song.uri);
            currentIndex = 0;
            if (trackQueue.length > 0 && window.spotifyToken) {
                playTrack(trackQueue[currentIndex]);
                updateTrackInfo(trackQueue[currentIndex]);
                logListeningHistory(
                    trackQueue[currentIndex],
                    songs[0].title,
                    songs[0].artist
                );
            }
        });
    });

    playPauseButton.addEventListener('click', () => {
        if (!window.spotifyToken) {
            showNotification('Por favor, conecta tu cuenta de Spotify para reproducir.', 'error');
            return;
        }

        if (isPlaying) {
            player.pause();
        } else {
            player.resume();
        }
    });

    prevTrackButton.addEventListener('click', () => {
        if (!window.spotifyToken) {
            showNotification('Por favor, conecta tu cuenta de Spotify para reproducir.', 'error');
            return;
        }

        if (currentIndex > 0) {
            currentIndex--;
            playTrack(trackQueue[currentIndex]);
            updateTrackInfo(trackQueue[currentIndex]);
        }
    });

    nextTrackButton.addEventListener('click', () => {
        if (!window.spotifyToken) {
            showNotification('Por favor, conecta tu cuenta de Spotify para reproducir.', 'error');
            return;
        }

        if (currentIndex < trackQueue.length - 1) {
            currentIndex++;
            playTrack(trackQueue[currentIndex]);
            updateTrackInfo(trackQueue[currentIndex]);
        }
    });

    progressBar.addEventListener('input', async () => {
        if (!currentTrackUri || !trackDurationMs || !window.spotifyToken) return;

        const positionMs = parseInt(progressBar.value);
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
            showNotification('Error al ajustar la posición de la canción.', 'error');
        }
    });

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
                                <img src="${song.image_url || 'https://picsum.photos/200/200?random=1'}" alt="${song.title}" class="w-full h-32 object-cover rounded-md mb-2">
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

                    searchResults.querySelectorAll('.play-button').forEach(button => {
                        button.addEventListener('click', () => {
                            const uri = button.getAttribute('data-uri');
                            const title = button.getAttribute('data-title');
                            const artist = button.getAttribute('data-artist');

                            trackQueue = [uri];
                            currentIndex = 0;
                            if (window.spotifyToken) {
                                playTrack(uri);
                                logListeningHistory(uri, title, artist);
                                updateTrackInfo(uri);
                            }
                        });
                    });

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
                console.error('Error al buscar canciones:', error);
                searchResults.innerHTML = '<p class="text-red-500">Error al buscar canciones.</p>';
            }
        });
        updateNewReleasesSlider();
    }

    // Listener para el botón "Refrescar Recomendaciones"
    if (refreshRecommendationsButton) {
        refreshRecommendationsButton.addEventListener('click', async () => {
            try {
                const response = await fetch('/refresh_recommendations');
                if (response.status === 401) {
                    showNotification('Por favor, inicia sesión para refrescar las recomendaciones.', 'error');
                    return;
                }
                if (!response.ok) {
                    throw new Error('Error al refrescar las recomendaciones');
                }
                const songs = await response.json();
                const slider = document.getElementById('recommended-slider');
                if (slider) {
                    slider.innerHTML = songs.map(song => `
                        <div class="min-w-[200px] mx-2 rounded">
                            <div class="relative">
                                <img src="${song.image_url || 'https://picsum.photos/200/200?random=' + Math.random()}" alt="${song.title}" class="w-full h-48 object-cover rounded-md mb-4">
                                <button class="play-button absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-white text-4xl opacity-50 hover:opacity-100 transition-opacity" data-uri="${song.uri}" data-title="${song.title}" data-artist="${song.artist}" data-image-url="${song.image_url || 'https://picsum.photos/200/200?random=1'}">►</button>
                            </div>
                            <h3 class="text-lg font-semibold truncate">${song.title}</h3>
                            <p class="text-gray-600 dark:text-gray-300 truncate">${song.artist}</p>
                            <form class="add-to-playlist-form mt-2 flex items-center gap-2" data-uri="${song.uri}" data-title="${song.title}" data-artist="${song.artist}">
                                <input type="hidden" name="song_uri" value="${song.uri}">
                                <input type="hidden" name="song_title" value="${song.title}">
                                <input type="hidden" name="song_artist" value="${song.artist}">
                                <select name="playlist_id" class="p-1 text-sm border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white">
                                    <option value="">Seleccionar Playlist</option>
                                    ${window.playlists && window.playlists.length > 0 ? window.playlists.map(playlist => `<option value="${playlist.id}">${playlist.name}</option>`).join('') : '<option value="">No tienes playlists</option>'}
                                </select>
                                <button type="submit" class="bg-blue-500 text-white py-1 px-2 text-sm rounded hover:bg-blue-600 transition">Agregar</button>
                            </form>
                        </div>
                    `).join('');

                    // Reasignar eventos a los nuevos botones de reproducción
                    slider.querySelectorAll('.play-button').forEach(button => {
                        button.addEventListener('click', () => {
                            const uri = button.getAttribute('data-uri');
                            const title = button.getAttribute('data-title');
                            const artist = button.getAttribute('data-artist');
                            const imageUrl = button.getAttribute('data-image-url');

                            trackQueue = [uri];
                            currentIndex = 0;
                            if (window.spotifyToken) {
                                playTrack(uri);
                                logListeningHistory(uri, title, artist);
                                updateTrackInfo(uri);
                            } else {
                                showNotification('Por favor, conecta tu cuenta de Spotify para reproducir.', 'error');
                            }
                        });
                    });

                    // Reasignar eventos a los formularios de agregar a playlist
                    slider.querySelectorAll('.add-to-playlist-form').forEach(form => {
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

                    // Resetear el índice del slider después de refrescar
                    recommendedIndex = 0;
                    updateRecommendedSlider();
                    showNotification('Recomendaciones actualizadas con éxito', 'success');
                }
            } catch (error) {
                console.error('Error al refrescar recomendaciones:', error);
                showNotification('Error al refrescar las recomendaciones', 'error');
            }
        });
    }

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
                    createPlaylistForm.reset();
                } else {
                    showNotification(result.error || 'Error al crear la playlist', 'error');
                }
            } catch (error) {
                console.error('Error al crear playlist:', error);
                showNotification('Error al crear la playlist', 'error');
            }
        });
    }

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

                        entryDiv.querySelector('.play-button').addEventListener('click', () => {
                            const uri = entry.song_uri;
                            const title = entry.song_title;
                            const artist = entry.song_artist;

                            trackQueue = [uri];
                            currentIndex = 0;
                            if (window.spotifyToken) {
                                playTrack(uri);
                                logListeningHistory(uri, title, artist);
                                updateTrackInfo(uri);
                            }
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

document.getElementById('voice-command-btn')?.addEventListener('click', () => {
    let mediaRecorder;
    let audioChunks = [];

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const formData = new FormData();
                formData.append('audio', audioBlob, 'command.wav');

                fetch('/voice-command', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showNotification(data.message, 'success');
                        // Actualizar UI según la acción
                        if (data.action === 'play') {
                            // Actualizar el estado del reproductor si es necesario
                            playPauseButton.textContent = '⏸️';
                        } else if (data.action === 'pause') {
                            playPauseButton.textContent = '⏯️';
                        }
                    } else {
                        showNotification(data.error, 'error');
                    }
                })
                .catch(error => {
                    console.error('Error al enviar comando de voz:', error);
                    showNotification('Error al procesar el comando de voz', 'error');
                });

                audioChunks = []; // Limpiar para la próxima grabación
            };

            if (mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            } else {
                mediaRecorder.start();
                showNotification('Grabando... Habla ahora.', 'info');
            }
        })
        .catch(error => {
            console.error('Error al acceder al micrófono:', error);
            showNotification('Error al acceder al micrófono', 'error');
        });
});

const newReleasesSlider = document.getElementById('new-releases-slider');
if (newReleasesSlider) {
        const newReleasesCards = newReleasesSlider.children;
        const newReleasesCardWidth = newReleasesCards[0]?.offsetWidth + 16 || 216;
        const cardsPerView = 3;
        const totalCards = newReleasesCards.length;
        const maxIndex = Math.ceil(totalCards / cardsPerView) - 1;
        let newReleasesIndex = 0;

       function updateNewReleasesSlider() {
    const slider = document.getElementById('new-releases-slider');
    if (!slider) return;

    const cards = slider.children;
    const cardWidth = cards[0]?.offsetWidth + 16 || 216; // Ancho de la tarjeta + margen
    const cardsPerView = 3;
    const totalCards = cards.length;
    const maxIndex = Math.ceil(totalCards / cardsPerView) - 1;
    let index = 0;

    anime({
        targets: slider,
        translateX: -index * cardWidth * cardsPerView,
        easing: 'easeInOutQuad',
        duration: 500
    });

    document.getElementById('new-releases-right-btn').addEventListener('click', () => {
        if (index < maxIndex) index++;
        else index = 0;
        anime({
            targets: slider,
            translateX: -index * cardWidth * cardsPerView,
            easing: 'easeInOutQuad',
            duration: 500
        });
    });

    document.getElementById('new-releases-left-btn').addEventListener('click', () => {
        if (index > 0) index--;
        else index = maxIndex;
        anime({
            targets: slider,
            translateX: -index * cardWidth * cardsPerView,
            easing: 'easeInOutQuad',
            duration: 500
        });
    });
}

// Llamar a la función después de cargar el DOM
document.addEventListener('DOMContentLoaded', () => {
    updateNewReleasesSlider();
});

        document.getElementById('new-releases-right-btn').addEventListener('click', () => {
            if (newReleasesIndex < maxIndex) newReleasesIndex++;
            else newReleasesIndex = 0;
            updateNewReleasesSlider();
        });

        document.getElementById('new-releases-left-btn').addEventListener('click', () => {
            if (newReleasesIndex > 0) newReleasesIndex--;
            else newReleasesIndex = maxIndex;
            updateNewReleasesSlider();
        });

        window.addEventListener('resize', () => {
            updateNewReleasesSlider();
        });

        newReleasesSlider.querySelectorAll('.play-button').forEach(button => {
            button.addEventListener('click', () => {
                const uri = button.getAttribute('data-uri');
                const title = button.getAttribute('data-title');
                const artist = button.getAttribute('data-artist');
                if (isAdmin) {
                    const playerIframe = document.getElementById('player-iframe');
                    if (playerIframe) {
                        playerIframe.contentWindow.postMessage({ type: 'playTrack', uri, title, artist, image_url: button.parentElement.querySelector('img')?.src || 'https://picsum.photos/50/50?random=1' }, '*');
                        logListeningHistory(uri, title, artist);
                        showNotification('Reproduciendo en el reproductor en segundo plano', 'success');
                    } else {
                        showNotification('Error: Reproductor en segundo plano no disponible', 'error');
                    }
                    return;
                }
                trackQueue = [uri];
                currentIndex = 0;
                if (window.spotifyToken) {
                    playTrack(uri);
                    logListeningHistory(uri, title, artist);
                    updateTrackInfo(uri);
                } else {
                    showNotification('Por favor, conecta tu cuenta de Spotify para reproducir.', 'error');
                }
            });
        });
    }

    const adminSlider = document.getElementById('admin-slider');
    if (adminSlider) {
        const adminCards = adminSlider.children;
        const adminCardWidth = adminCards[0]?.offsetWidth + 16 || 216;
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



    // Manejar notificaciones desde el reproductor en segundo plano
    window.addEventListener('message', (event) => {
        if (event.data.type === 'notification') {
            showNotification(event.data.message, event.data.notificationType);
        }
        // Manejo existente de playTrack
        if (event.data.type === 'playTrack' && window.spotifyToken && !isAdmin) {
            const { uri, title, artist } = event.data;
            trackQueue = [uri];
            currentIndex = 0;
            playTrack(uri);
            logListeningHistory(uri, title, artist);
            updateTrackInfo(uri);
        }
    });
});
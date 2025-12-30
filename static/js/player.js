class Player {
    constructor() {
        this.trackQueue = [];
        this.currentTrackIndex = 0;
        this.isPlaying = false;
        this.player = null;
        this.deviceId = null;
        this.trackDurationMs = 0;
        this.volume = 0.5;
        this.isMuted = false;
        this.previousVolume = this.volume;
        this.isPlaylistVisible = false;
        this.shuffleMode = false;
        this.repeatMode = 'none'; // 'none', 'all', 'one'

        this.initSpotifyPlayer();
        this.setupEventListeners();
    }

    initSpotifyPlayer() {
        window.onSpotifyWebPlaybackSDKReady = () => {
            if (!window.spotifyToken) {
                parent.postMessage({ type: 'notification', message: 'Por favor, conecta tu cuenta de Spotify para reproducir.', notificationType: 'error' }, '*');
                return;
            }

            this.player = new Spotify.Player({
                name: 'Tuning Player',
                getOAuthToken: cb => { cb(window.spotifyToken); },
                volume: this.volume
            });

            this.player.addListener('initialization_error', ({ message }) => {
                parent.postMessage({ type: 'notification', message: `Error al inicializar el reproductor: ${message}`, notificationType: 'error' }, '*');
            });

            this.player.addListener('authentication_error', ({ message }) => {
                parent.postMessage({ type: 'notification', message: `Error de autenticación con Spotify: ${message}`, notificationType: 'error' }, '*');
            });

            this.player.addListener('account_error', ({ message }) => {
                parent.postMessage({ type: 'notification', message: `Error de cuenta: ${message}`, notificationType: 'error' }, '*');
            });

            this.player.addListener('playback_error', ({ message }) => {
                parent.postMessage({ type: 'notification', message: `Error al reproducir: ${message}`, notificationType: 'error' }, '*');
            });

            this.player.addListener('player_state_changed', state => {
                if (!state) return;

                this.isPlaying = !state.paused;
                this.shuffleMode = state.shuffle;
                this.repeatMode = state.repeat_mode === 0 ? 'none' : state.repeat_mode === 1 ? 'all' : 'one';
                document.getElementById('play-pause').textContent = this.isPlaying ? '⏸️' : '⏯️';
                document.getElementById('shuffle-btn')?.classList.toggle('active', this.shuffleMode);
                document.getElementById('repeat-btn')?.textContent = this.repeatMode === 'one' ? '🔂' : '🔁';
                document.getElementById('repeat-btn')?.classList.toggle('active', this.repeatMode !== 'none');

                if (state.track_window.current_track) {
                    const track = state.track_window.current_track;
                    const trackInfo = {
                        title: track.name,
                        artist: track.artists.map(artist => artist.name).join(', '),
                        image_url: track.album.images[0]?.url || 'https://picsum.photos/200/200?random=1',
                        uri: track.uri
                    };
                    this.updateTrackInfo(trackInfo);

                    this.trackDurationMs = state.duration;
                    document.getElementById('progress-bar').max = this.trackDurationMs;
                    const progressMs = state.position;
                    document.getElementById('progress-bar').value = progressMs;
                    document.getElementById('current-time').textContent = this.formatTime(progressMs / 1000);
                    document.getElementById('duration').textContent = this.formatTime(this.trackDurationMs / 1000);

                    anime({
                        targets: '#progress-bar',
                        value: progressMs,
                        duration: 200,
                        easing: 'easeOutQuad'
                    });

                    this.updatePlaylistDisplay();
                    this.saveState();

                    // Enviar estado al padre (dashboard.html)
                    parent.postMessage({
                        type: 'playerState',
                        isPlaying: this.isPlaying,
                        track: trackInfo,
                        position: progressMs,
                        duration: this.trackDurationMs
                    }, '*');
                }
            });

            this.player.addListener('ready', ({ device_id }) => {
                this.deviceId = device_id;
                parent.postMessage({ type: 'notification', message: 'Reproductor listo.', notificationType: 'success' }, '*');
                this.loadState();
            });

            this.player.addListener('not_ready', ({ device_id }) => {
                parent.postMessage({ type: 'notification', message: 'El reproductor no está listo. Por favor, intenta de nuevo más tarde.', notificationType: 'error' }, '*');
            });

            this.player.connect();
        };
    }

    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
        return array;
    }

    saveState() {
        localStorage.setItem('playerState', JSON.stringify({
            trackQueue: this.trackQueue,
            currentIndex: this.currentTrackIndex,
            isPlaying: this.isPlaying,
            positionMs: parseInt(document.getElementById('progress-bar').value),
            volume: this.volume,
            shuffleMode: this.shuffleMode,
            repeatMode: this.repeatMode
        }));

        fetch('/save_player_state', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: document.querySelector('meta[name="user-id"]')?.content || 'user',
                track_queue: this.trackQueue,
                current_index: this.currentTrackIndex,
                is_playing: this.isPlaying,
                position_ms: parseInt(document.getElementById('progress-bar').value),
                volume: this.volume,
                shuffle_mode: this.shuffleMode,
                repeat_mode: this.repeatMode,
                context: window.location.pathname.includes('/admin') ? 'admin' : 'user'
            })
        }).catch(error => {
            console.error('Error al guardar estado en Supabase:', error);
        });
    }

    loadState() {
        fetch('/load_player_state')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.trackQueue = data.state.track_queue || [];
                    this.currentTrackIndex = data.state.current_index || 0;
                    this.isPlaying = data.state.is_playing || false;
                    this.volume = data.state.volume || 0.5;
                    this.shuffleMode = data.state.shuffle_mode || false;
                    this.repeatMode = data.state.repeat_mode || 'none';
                    const positionMs = data.state.position_ms || 0;
                    if (this.trackQueue.length > 0 && this.currentTrackIndex < this.trackQueue.length) {
                        this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                        if (this.isPlaying && this.deviceId) {
                            this.playTrack(this.trackQueue[this.currentTrackIndex].uri, positionMs);
                        }
                    }
                    document.getElementById('volume').value = this.volume * 100;
                    if (this.player) {
                        this.player.setVolume(this.volume);
                    }
                    this.updatePlaylistDisplay();
                    document.getElementById('shuffle-btn')?.classList.toggle('active', this.shuffleMode);
                    document.getElementById('repeat-btn')?.textContent = this.repeatMode === 'one' ? '🔂' : '🔁';
                    document.getElementById('repeat-btn')?.classList.toggle('active', this.repeatMode !== 'none');
                    parent.postMessage({
                        type: 'updateQueue',
                        queue: this.trackQueue,
                        currentIndex: this.currentTrackIndex
                    }, '*');
                } else {
                    const state = JSON.parse(localStorage.getItem('playerState') || '{}');
                    this.trackQueue = state.trackQueue || [];
                    this.currentTrackIndex = state.currentIndex || 0;
                    this.isPlaying = state.isPlaying || false;
                    this.volume = state.volume || 0.5;
                    this.shuffleMode = state.shuffleMode || false;
                    this.repeatMode = state.repeat_mode || 'none';
                    const positionMs = state.positionMs || 0;
                    if (this.trackQueue.length > 0 && this.currentTrackIndex < this.trackQueue.length) {
                        this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                        if (this.isPlaying && this.deviceId) {
                            this.playTrack(this.trackQueue[this.currentTrackIndex].uri, positionMs);
                        }
                    }
                    document.getElementById('volume').value = this.volume * 100;
                    if (this.player) {
                        this.player.setVolume(this.volume);
                    }
                    this.updatePlaylistDisplay();
                    document.getElementById('shuffle-btn')?.classList.toggle('active', this.shuffleMode);
                    document.getElementById('repeat-btn')?.textContent = this.repeatMode === 'one' ? '🔂' : '🔁';
                    document.getElementById('repeat-btn')?.classList.toggle('active', this.repeatMode !== 'none');
                    parent.postMessage({
                        type: 'updateQueue',
                        queue: this.trackQueue,
                        currentIndex: this.currentTrackIndex
                    }, '*');
                }
            })
            .catch(error => {
                console.error('Error al cargar estado desde Supabase:', error);
                const state = JSON.parse(localStorage.getItem('playerState') || '{}');
                this.trackQueue = state.trackQueue || [];
                this.currentTrackIndex = state.currentIndex || 0;
                this.isPlaying = state.isPlaying || false;
                this.volume = state.volume || 0.5;
                this.shuffleMode = state.shuffleMode || false;
                this.repeatMode = state.repeat_mode || 'none';
                const positionMs = state.positionMs || 0;
                if (this.trackQueue.length > 0 && this.currentTrackIndex < this.trackQueue.length) {
                    this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                    if (this.isPlaying && this.deviceId) {
                        this.playTrack(this.trackQueue[this.currentTrackIndex].uri, positionMs);
                    }
                }
                document.getElementById('volume').value = this.volume * 100;
                if (this.player) {
                    this.player.setVolume(this.volume);
                }
                this.updatePlaylistDisplay();
                document.getElementById('shuffle-btn')?.classList.toggle('active', this.shuffleMode);
                document.getElementById('repeat-btn')?.textContent = this.repeatMode === 'one' ? '🔂' : '🔁';
                document.getElementById('repeat-btn')?.classList.toggle('active', this.repeatMode !== 'none');
                parent.postMessage({
                    type: 'updateQueue',
                    queue: this.trackQueue,
                    currentIndex: this.currentTrackIndex
                }, '*');
            });
    }

    updateTrackInfo(track) {
        const titleElement = document.getElementById('player-title');
        const artistElement = document.getElementById('player-artist');
        const albumElement = document.getElementById('player-album');

        anime({
            targets: [titleElement, artistElement, albumElement],
            opacity: [1, 0],
            duration: 200,
            easing: 'easeInQuad',
            complete: () => {
                titleElement.textContent = track.title || 'Selecciona una canción';
                artistElement.textContent = track.artist || 'Artista';
                albumElement.src = track.image_url || 'https://picsum.photos/200/200?random=1';
                anime({
                    targets: [titleElement, artistElement, albumElement],
                    opacity: [0, 1],
                    duration: 200,
                    easing: 'easeOutQuad'
                });
            }
        });
    }

    updatePlaylistDisplay() {
        const playlistList = document.getElementById('playlist-list');
        if (!playlistList) return;
        playlistList.innerHTML = '';
        this.trackQueue.forEach((track, index) => {
            const li = document.createElement('li');
            li.textContent = `${track.title} - ${track.artist}`;
            li.className = 'cursor-pointer hover:bg-gray-100 p-2 rounded';
            li.addEventListener('click', () => {
                this.currentTrackIndex = index;
                this.playTrack(track.uri);
                this.updateTrackInfo(track);
                this.updatePlaylistDisplay();
                this.saveState();
            });
            if (index === this.currentTrackIndex) {
                li.classList.add('active');
            }
            playlistList.appendChild(li);
        });
    }

    async playTrack(uri, positionMs = 0) {
        if (!this.deviceId) {
            parent.postMessage({ type: 'notification', message: 'El reproductor no está listo. Por favor, espera un momento.', notificationType: 'error' }, '*');
            return;
        }

        try {
            const response = await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${this.deviceId}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${window.spotifyToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    uris: [uri],
                    position_ms: positionMs
                }),
            });

            if (response.status === 204) {
                this.isPlaying = true;
                document.getElementById('play-pause').textContent = '⏸️';
                this.saveState();
            } else {
                const errorData = await response.json();
                parent.postMessage({ type: 'notification', message: `Error al reproducir la canción: ${errorData.error?.message || 'Desconocido'}`, notificationType: 'error' }, '*');
            }
        } catch (error) {
            parent.postMessage({ type: 'notification', message: `Error al reproducir la canción: ${error.message}`, notificationType: 'error' }, '*');
        }
    }

    async seek(positionMs) {
        try {
            await fetch(`https://api.spotify.com/v1/me/player/seek?device_id=${this.deviceId}&position_ms=${positionMs}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${window.spotifyToken}`,
                },
            });
            document.getElementById('current-time').textContent = this.formatTime(positionMs / 1000);
            this.saveState();
        } catch (error) {
            parent.postMessage({ type: 'notification', message: 'Error al ajustar la posición de la canción.', notificationType: 'error' }, '*');
        }
    }

    setupEventListeners() {
        window.addEventListener('message', (event) => {
            if (event.data.type === 'playTrack') {
                this.trackQueue = [{
                    uri: event.data.uri,
                    title: event.data.title,
                    artist: event.data.artist,
                    image_url: event.data.image_url
                }];
                this.currentTrackIndex = 0;
                if (window.spotifyToken && this.deviceId) {
                    this.playTrack(event.data.uri);
                    this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                    this.updatePlaylistDisplay();
                    parent.postMessage({
                        type: 'updateQueue',
                        queue: this.trackQueue,
                        currentIndex: this.currentTrackIndex
                    }, '*');
                }
            } else if (event.data.type === 'playPlaylist') {
                this.trackQueue = event.data.songs;
                if (this.shuffleMode) this.trackQueue = this.shuffleArray([...this.trackQueue]);
                this.currentTrackIndex = 0;
                if (this.trackQueue.length > 0 && window.spotifyToken && this.deviceId) {
                    this.playTrack(this.trackQueue[this.currentTrackIndex].uri);
                    this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                    this.updatePlaylistDisplay();
                    parent.postMessage({
                        type: 'updateQueue',
                        queue: this.trackQueue,
                        currentIndex: this.currentTrackIndex
                    }, '*');
                }
            } else if (event.data.type === 'playPause') {
                if (this.isPlaying) {
                    this.player.pause();
                } else {
                    this.player.resume();
                }
                this.saveState();
            } else if (event.data.type === 'previous') {
                if (this.currentTrackIndex > 0) {
                    this.currentTrackIndex--;
                    this.playTrack(this.trackQueue[this.currentTrackIndex].uri);
                    this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                    this.updatePlaylistDisplay();
                    this.saveState();
                    parent.postMessage({
                        type: 'updateQueue',
                        queue: this.trackQueue,
                        currentIndex: this.currentTrackIndex
                    }, '*');
                }
            } else if (event.data.type === 'next') {
                if (this.currentTrackIndex < this.trackQueue.length - 1) {
                    this.currentTrackIndex++;
                    this.playTrack(this.trackQueue[this.currentTrackIndex].uri);
                    this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                    this.updatePlaylistDisplay();
                    this.saveState();
                    parent.postMessage({
                        type: 'updateQueue',
                        queue: this.trackQueue,
                        currentIndex: this.currentTrackIndex
                    }, '*');
                }
            } else if (event.data.type === 'toggleShuffle') {
                this.shuffleMode = !this.shuffleMode;
                document.getElementById('shuffle-btn')?.classList.toggle('active', this.shuffleMode);
                if (this.shuffleMode && this.trackQueue.length > 0) {
                    const currentTrack = this.trackQueue[this.currentTrackIndex];
                    this.trackQueue = this.shuffleArray([...this.trackQueue]);
                    this.currentTrackIndex = this.trackQueue.findIndex(track => track.uri === currentTrack.uri);
                    this.updatePlaylistDisplay();
                }
                this.saveState();
            } else if (event.data.type === 'toggleRepeat') {
                if (this.repeatMode === 'none') {
                    this.repeatMode = 'all';
                    document.getElementById('repeat-btn')?.classList.add('active');
                } else if (this.repeatMode === 'all') {
                    this.repeatMode = 'one';
                    document.getElementById('repeat-btn')?.textContent = '🔂';
                } else {
                    this.repeatMode = 'none';
                    document.getElementById('repeat-btn')?.textContent = '🔁';
                    document.getElementById('repeat-btn')?.classList.remove('active');
                }
                this.saveState();
            } else if (event.data.type === 'toggleMute') {
                if (this.isMuted) {
                    this.volume = this.previousVolume;
                    this.player.setVolume(this.volume);
                    document.getElementById('mute').textContent = '🔊';
                    document.getElementById('volume').value = this.volume * 100;
                } else {
                    this.previousVolume = this.volume;
                    this.volume = 0;
                    this.player.setVolume(0);
                    document.getElementById('mute').textContent = '🔇';
                    document.getElementById('volume').value = 0;
                }
                this.isMuted = !this.isMuted;
                this.saveState();
            } else if (event.data.type === 'setVolume') {
                this.volume = event.data.volume;
                this.player.setVolume(this.volume);
                if (this.isMuted) {
                    this.isMuted = false;
                    document.getElementById('mute').textContent = '🔊';
                }
                this.saveState();
            } else if (event.data.type === 'seek') {
                this.seek(event.data.positionMs);
            }
        });

        document.getElementById('play-pause').addEventListener('click', () => {
            if (this.isPlaying) {
                this.player.pause();
            } else {
                this.player.resume();
            }
            this.saveState();
        });

        document.getElementById('prev-track').addEventListener('click', () => {
            if (this.currentTrackIndex > 0) {
                this.currentTrackIndex--;
                this.playTrack(this.trackQueue[this.currentTrackIndex].uri);
                this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                this.updatePlaylistDisplay();
                this.saveState();
                parent.postMessage({
                    type: 'updateQueue',
                    queue: this.trackQueue,
                    currentIndex: this.currentTrackIndex
                }, '*');
            }
        });

        document.getElementById('next-track').addEventListener('click', () => {
            if (this.currentTrackIndex < this.trackQueue.length - 1) {
                this.currentTrackIndex++;
                this.playTrack(this.trackQueue[this.currentTrackIndex].uri);
                this.updateTrackInfo(this.trackQueue[this.currentTrackIndex]);
                this.updatePlaylistDisplay();
                this.saveState();
                parent.postMessage({
                    type: 'updateQueue',
                    queue: this.trackQueue,
                    currentIndex: this.currentTrackIndex
                }, '*');
            }
        });

        document.getElementById('shuffle-btn')?.addEventListener('click', () => {
            this.shuffleMode = !this.shuffleMode;
            document.getElementById('shuffle-btn').classList.toggle('active', this.shuffleMode);
            if (this.shuffleMode && this.trackQueue.length > 0) {
                const currentTrack = this.trackQueue[this.currentTrackIndex];
                this.trackQueue = this.shuffleArray([...this.trackQueue]);
                this.currentTrackIndex = this.trackQueue.findIndex(track => track.uri === currentTrack.uri);
                this.updatePlaylistDisplay();
            }
            this.saveState();
        });

        document.getElementById('repeat-btn')?.addEventListener('click', () => {
            if (this.repeatMode === 'none') {
                this.repeatMode = 'all';
                document.getElementById('repeat-btn').classList.add('active');
            } else if (this.repeatMode === 'all') {
                this.repeatMode = 'one';
                document.getElementById('repeat-btn').textContent = '🔂';
            } else {
                this.repeatMode = 'none';
                document.getElementById('repeat-btn').textContent = '🔁';
                document.getElementById('repeat-btn').classList.remove('active');
            }
            this.saveState();
        });

        document.getElementById('progress-bar').addEventListener('input', () => {
            const positionMs = parseInt(document.getElementById('progress-bar').value);
            this.seek(positionMs);
        });

        document.getElementById('volume').addEventListener('input', (e) => {
            this.volume = e.target.value / 100;
            this.player.setVolume(this.volume);
            if (this.isMuted) {
                this.isMuted = false;
                document.getElementById('mute').textContent = '🔊';
            }
            this.saveState();
        });

        document.getElementById('mute').addEventListener('click', () => {
            if (this.isMuted) {
                this.volume = this.previousVolume;
                this.player.setVolume(this.volume);
                document.getElementById('mute').textContent = '🔊';
                document.getElementById('volume').value = this.volume * 100;
            } else {
                this.previousVolume = this.volume;
                this.volume = 0;
                this.player.setVolume(0);
                document.getElementById('mute').textContent = '🔇';
                document.getElementById('volume').value = 0;
            }
            this.isMuted = !this.isMuted;
            this.saveState();
        });

document.getElementById('voice-command-btn')?.addEventListener('click', () => {
    let mediaRecorder;
    let audioChunks = [];

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
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
                    if (data.status === 'success') {
                        parent.postMessage({ type: 'notification', message: data.message, notificationType: 'success' }, '*');
                        handleVoiceCommand(data.action); // Ejecutar acción en el reproductor
                    } else {
                        parent.postMessage({ type: 'notification', message: data.error, notificationType: 'error' }, '*');
                    }
                })
                .catch(error => {
                    parent.postMessage({ type: 'notification', message: 'Error al procesar el comando', notificationType: 'error' }, '*');
                });
                audioChunks = [];
            };

            mediaRecorder.start();
            parent.postMessage({ type: 'notification', message: 'Grabando...', notificationType: 'info' }, '*');
            setTimeout(() => mediaRecorder.stop(), 3000); // Grabar por 3 segundos
        })
        .catch(error => {
            parent.postMessage({ type: 'notification', message: 'Error al acceder al micrófono', notificationType: 'error' }, '*');
        });
});

function handleVoiceCommand(action) {
    switch (action) {
        case 'play': player.resume(); break;
        case 'pause': player.pause(); break;
        case 'next': player.nextTrack(); break;
        case 'previous': player.previousTrack(); break;
        default: console.log('Comando no reconocido');
    }
}

        document.getElementById('playlist-toggle')?.addEventListener('click', () => {
            this.isPlaylistVisible = !this.isPlaylistVisible;
            const playlistList = document.getElementById('playlist-list');
            playlistList.classList.toggle('show');
            document.getElementById('playlist-toggle').textContent = this.isPlaylistVisible ? '🔼' : '📜';
            anime({
                targets: '#playlist-list',
                maxHeight: this.isPlaylistVisible ? '200px' : '0px',
                duration: 300,
                easing: 'easeOutQuad'
            });
        });
    }
}

const player = new Player();
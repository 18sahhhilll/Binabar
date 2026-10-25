/**
 * Binabar: Client-side game controller
 * Handles audio playback, autocomplete, guess submission, hints, and scoring.
 * All state verification and scoring rules are enforced server-side.
 */
(function () {
    'use strict';

    // State
    var gameState = {
        token: null,
        round: 0,
        totalRounds: 10,
        totalScore: 0,
        replaysLeft: 3,
        audio: null,
        audioElement: null,
        youtubePlayer: null,
        isPlaying: false,
        playTimeout: null,
        activeSearchIndex: -1,
        searchTimer: null
    };

    // DOM Elements
    var screens = {
        preGame: document.getElementById('pre-game'),
        activeRound: document.getElementById('active-round'),
        roundResult: document.getElementById('round-result'),
        endScreen: document.getElementById('end-screen')
    };

    var startBtn = document.getElementById('start-game-btn');
    var playAudioBtn = document.getElementById('play-audio-btn');
    var eqBars = document.getElementById('eq-bars');
    var replayCountEl = document.getElementById('replay-count');
    var roundNumEl = document.getElementById('round-number');
    var totalRoundsEl = document.getElementById('total-rounds');
    var currentScoreEl = document.getElementById('current-score');

    var hintArtistBtn = document.getElementById('hint-artist');
    var hintYearBtn = document.getElementById('hint-year');
    var hintLangBtn = document.getElementById('hint-language');
    var hintDisplay = document.getElementById('hint-display');

    var guessInput = document.getElementById('guess-input');
    var autocompleteList = document.getElementById('autocomplete-list');
    var submitGuessBtn = document.getElementById('submit-guess-btn');
    var skipBtn = document.getElementById('skip-btn');
    var attemptsLeftEl = document.getElementById('attempts-left');
    var guessFeedback = document.getElementById('guess-feedback');

    var resultStatus = document.getElementById('result-status');
    var resultCredits = document.getElementById('result-credits');
    var nextRoundBtn = document.getElementById('next-round-btn');

    var finalScoreEl = document.getElementById('final-score');
    var bestScoreDisplay = document.getElementById('best-score-display');
    var bestScoreValue = document.getElementById('best-score-value');
    var roundRecap = document.getElementById('round-recap');
    var playAgainBtn = document.getElementById('play-again-btn');

    var csrfToken = document.getElementById('csrf-token') ? document.getElementById('csrf-token').value : '';

    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function getCsrf() {
        return csrfToken || getCookie('csrftoken') || '';
    }

    function showScreen(screenKey) {
        Object.keys(screens).forEach(function (k) {
            if (screens[k]) {
                if (k === screenKey) {
                    screens[k].removeAttribute('hidden');
                } else {
                    screens[k].setAttribute('hidden', '');
                }
            }
        });
    }

    // Audio handling
    function stopAudio() {
        if (gameState.playTimeout) {
            clearTimeout(gameState.playTimeout);
            gameState.playTimeout = null;
        }

        if (gameState.audioElement) {
            gameState.audioElement.pause();
            gameState.audioElement.currentTime = 0;
        }

        if (gameState.youtubePlayer && typeof gameState.youtubePlayer.stopVideo === 'function') {
            try {
                gameState.youtubePlayer.stopVideo();
            } catch (e) {}
        }

        gameState.isPlaying = false;
        if (playAudioBtn) {
            playAudioBtn.classList.remove('is-playing');
            var textSpan = playAudioBtn.querySelector('.btn-audio-text');
            if (textSpan) textSpan.textContent = 'Play clip';
        }
        if (eqBars) eqBars.classList.remove('active');
    }

    function playClip() {
        if (gameState.isPlaying) {
            stopAudio();
            return;
        }

        if (gameState.replaysLeft <= 0) {
            return;
        }

        if (!gameState.audio) return;

        gameState.isPlaying = true;
        gameState.replaysLeft -= 1;
        updateReplayDisplay();

        if (playAudioBtn) {
            playAudioBtn.classList.add('is-playing');
            var textSpan = playAudioBtn.querySelector('.btn-audio-text');
            if (textSpan) textSpan.textContent = 'Stop clip';
        }
        if (eqBars) eqBars.classList.add('active');

        var audioData = gameState.audio;
        var start = audioData.start || 0;
        var end = audioData.end || 0;
        var duration = (end > start) ? (end - start) : 12;

        if (audioData.type === 'upload' && audioData.url) {
            if (!gameState.audioElement) {
                gameState.audioElement = new Audio();
            }
            gameState.audioElement.src = audioData.url;
            gameState.audioElement.currentTime = start;
            gameState.audioElement.play().catch(function () {
                stopAudio();
            });

            gameState.playTimeout = setTimeout(function () {
                stopAudio();
            }, duration * 1000);

            gameState.audioElement.onended = function () {
                stopAudio();
            };
        } else if (audioData.type === 'youtube' && audioData.youtube_id) {
            playYouTubeClip(audioData.youtube_id, start, duration);
        }
    }

    function playYouTubeClip(ytId, start, duration) {
        var ytFrame = document.getElementById('yt-hidden-player');
        if (!ytFrame) {
            ytFrame = document.createElement('iframe');
            ytFrame.id = 'yt-hidden-player';
            ytFrame.style.width = '1px';
            ytFrame.style.height = '1px';
            ytFrame.style.opacity = '0.01';
            ytFrame.style.position = 'absolute';
            ytFrame.style.left = '-9999px';
            ytFrame.setAttribute('aria-hidden', 'true');
            ytFrame.setAttribute('tabindex', '-1');
            document.body.appendChild(ytFrame);
        }

        var startSeconds = Math.floor(start);
        var src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(ytId) +
                  '?autoplay=1&start=' + startSeconds + '&controls=0&disablekb=1&fs=0&rel=0';
        ytFrame.src = src;

        gameState.playTimeout = setTimeout(function () {
            ytFrame.src = '';
            stopAudio();
        }, duration * 1000);
    }

    function updateReplayDisplay() {
        if (!replayCountEl) return;
        replayCountEl.textContent = gameState.replaysLeft + ' replay' + (gameState.replaysLeft === 1 ? '' : 's') + ' left';
        if (gameState.replaysLeft <= 0 && playAudioBtn) {
            playAudioBtn.disabled = true;
        } else if (playAudioBtn) {
            playAudioBtn.disabled = false;
        }
    }

    // Start Game
    function startGame() {
        stopAudio();
        fetch('/api/start/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf()
            }
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.error) {
                alert(data.message || 'Could not start game.');
                return;
            }
            gameState.totalRounds = data.total_rounds;
            if (totalRoundsEl) totalRoundsEl.textContent = data.total_rounds;
            loadRound();
        })
        .catch(function () {
            alert('Failed to connect to the server. Please check your connection.');
        });
    }

    // Load Round
    function loadRound() {
        stopAudio();
        if (guessInput) {
            guessInput.value = '';
            guessInput.disabled = false;
        }
        if (guessFeedback) {
            guessFeedback.textContent = '';
            guessFeedback.className = 'guess-feedback';
        }
        if (hintDisplay) hintDisplay.innerHTML = '';
        if (autocompleteList) autocompleteList.setAttribute('hidden', '');

        fetch('/api/round/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf()
            }
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.error === 'game_over') {
                renderEndScreen(data);
                return;
            }
            if (data.error === 'song_unavailable') {
                loadRound();
                return;
            }
            if (data.error) {
                alert(data.message || 'Error loading round.');
                return;
            }

            gameState.token = data.token;
            gameState.round = data.round;
            gameState.audio = data.audio;
            gameState.replaysLeft = (data.max_replays - data.replays);
            gameState.totalScore = data.total_score;

            if (roundNumEl) roundNumEl.textContent = data.round;
            if (totalRoundsEl) totalRoundsEl.textContent = data.total_rounds;
            if (currentScoreEl) currentScoreEl.textContent = data.total_score;
            if (attemptsLeftEl) {
                var attemptsLeft = data.max_attempts - data.attempts;
                attemptsLeftEl.textContent = attemptsLeft + ' attempt' + (attemptsLeft === 1 ? '' : 's') + ' left';
            }

            updateReplayDisplay();

            // Hints
            setupHintButtons(data.available_hints, data.hints_used);

            showScreen('activeRound');
            if (guessInput) guessInput.focus();
        })
        .catch(function () {
            alert('Error loading round. Please refresh.');
        });
    }

    function setupHintButtons(available, used) {
        var buttons = [
            { btn: hintArtistBtn, type: 'artist_initial' },
            { btn: hintYearBtn, type: 'year' },
            { btn: hintLangBtn, type: 'language' }
        ];

        buttons.forEach(function (item) {
            if (!item.btn) return;
            if (used && used.indexOf(item.type) !== -1) {
                item.btn.disabled = true;
                item.btn.classList.add('used');
            } else if (available && available.indexOf(item.type) !== -1) {
                item.btn.disabled = false;
                item.btn.classList.remove('used');
            } else {
                item.btn.disabled = true;
                item.btn.classList.remove('used');
            }
        });
    }

    function requestHint(hintType, btnElement) {
        if (!gameState.token) return;

        fetch('/api/hint/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf()
            },
            body: JSON.stringify({
                token: gameState.token,
                hint_type: hintType
            })
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.error) {
                return;
            }
            if (btnElement) {
                btnElement.disabled = true;
                btnElement.classList.add('used');
            }
            var labelMap = {
                artist_initial: 'Artist initial',
                year: 'Release year',
                language: 'Language'
            };
            var badge = document.createElement('div');
            badge.className = 'hint-badge';
            badge.innerHTML = '<strong>' + (labelMap[data.hint_type] || data.hint_type) + ':</strong> ' + escapeHtml(data.hint_value);
            if (hintDisplay) hintDisplay.appendChild(badge);
        });
    }

    // Submit Guess
    function submitGuess() {
        if (!guessInput) return;
        var guess = guessInput.value.trim();
        if (!guess || !gameState.token) return;

        if (autocompleteList) autocompleteList.setAttribute('hidden', '');

        fetch('/api/guess/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf()
            },
            body: JSON.stringify({
                token: gameState.token,
                guess: guess
            })
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.error) {
                if (guessFeedback) {
                    guessFeedback.textContent = data.message || 'Error submitting guess.';
                    guessFeedback.className = 'guess-feedback wrong';
                }
                return;
            }

            if (data.result === 'correct') {
                stopAudio();
                gameState.totalScore = data.total_score;
                if (currentScoreEl) currentScoreEl.textContent = data.total_score;
                showRoundResult(true, data.score, data.credits, data.game_over);
            } else {
                // Wrong guess
                if (data.round_over) {
                    stopAudio();
                    gameState.totalScore = data.total_score;
                    if (currentScoreEl) currentScoreEl.textContent = data.total_score;
                    showRoundResult(false, 0, data.credits, data.game_over);
                } else {
                    if (attemptsLeftEl) {
                        attemptsLeftEl.textContent = data.attempts_left + ' attempt' + (data.attempts_left === 1 ? '' : 's') + ' left';
                    }
                    if (guessFeedback) {
                        guessFeedback.textContent = 'Not that one. Try again.';
                        guessFeedback.className = 'guess-feedback wrong';
                    }
                    if (guessInput) {
                        guessInput.select();
                    }
                }
            }
        });
    }

    // Skip Round
    function skipRound() {
        if (!gameState.token) return;
        stopAudio();

        fetch('/api/skip/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf()
            },
            body: JSON.stringify({
                token: gameState.token
            })
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.error) return;
            gameState.totalScore = data.total_score;
            if (currentScoreEl) currentScoreEl.textContent = data.total_score;
            showRoundResult('skipped', 0, data.credits, data.game_over);
        });
    }

    // Show round result with full credits
    function showRoundResult(resultType, score, credits, isGameOver) {
        if (!resultStatus || !resultCredits) return;

        if (resultType === true) {
            resultStatus.innerHTML = '<h2 class="result-heading correct">Correct</h2>' +
                                     '<p class="result-points">+' + score + ' points</p>';
        } else if (resultType === false) {
            resultStatus.innerHTML = '<h2 class="result-heading wrong">Out of tries</h2>' +
                                     '<p class="result-points">0 points</p>';
        } else {
            resultStatus.innerHTML = '<h2 class="result-heading skipped">Skipped</h2>' +
                                     '<p class="result-points">0 points</p>';
        }

        var artistsStr = (credits.artists && credits.artists.length) ? credits.artists.join(', ') : credits.artist;
        var producersStr = (credits.producers && credits.producers.length) ? credits.producers.join(', ') : '';

        var linkHtml = '';
        if (credits.source_url) {
            linkHtml = '<a href="' + escapeHtml(credits.source_url) + '" class="result-source-link" target="_blank" rel="noopener noreferrer">Listen to the original</a>';
        }

        resultCredits.innerHTML =
            '<h3 class="result-song-title">' + escapeHtml(credits.title) + '</h3>' +
            '<dl class="result-meta-list">' +
                '<dt>Artist</dt><dd>' + escapeHtml(artistsStr) + '</dd>' +
                '<dt>Producer</dt><dd>' + escapeHtml(producersStr) + '</dd>' +
                '<dt>Label</dt><dd>' + escapeHtml(credits.label) + '</dd>' +
                '<dt>Year</dt><dd>' + escapeHtml(credits.year) + '</dd>' +
            '</dl>' +
            linkHtml;

        if (nextRoundBtn) {
            nextRoundBtn.textContent = isGameOver ? 'See final score' : 'Next round';
            nextRoundBtn.onclick = function () {
                if (isGameOver) {
                    finishGame();
                } else {
                    loadRound();
                }
            };
        }

        showScreen('roundResult');
        if (nextRoundBtn) nextRoundBtn.focus();
    }

    function finishGame() {
        fetch('/api/round/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf()
            }
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            renderEndScreen(data);
        });
    }

    function renderEndScreen(data) {
        stopAudio();
        var finalScore = data.total_score || gameState.totalScore;
        if (finalScoreEl) finalScoreEl.textContent = finalScore;

        // LocalStorage best score
        try {
            var currentBest = parseInt(localStorage.getItem('binabar_best_score') || '0', 10);
            if (finalScore > currentBest) {
                currentBest = finalScore;
                localStorage.setItem('binabar_best_score', String(currentBest));
            }
            if (bestScoreDisplay && bestScoreValue) {
                bestScoreValue.textContent = currentBest;
                bestScoreDisplay.removeAttribute('hidden');
            }
        } catch (e) {
            // LocalStorage not available, ignore gracefully
        }

        // Render recap
        if (roundRecap && data.rounds_data) {
            roundRecap.innerHTML = '';
            data.rounds_data.forEach(function (r, idx) {
                var row = document.createElement('div');
                row.className = 'recap-row';

                var info = document.createElement('div');
                info.className = 'recap-info';

                var title = document.createElement('div');
                title.className = 'recap-song-title';
                title.textContent = (idx + 1) + '. ' + (r.title || 'Unknown');

                var sub = document.createElement('div');
                sub.className = 'recap-credits-line';
                var art = (r.artists && r.artists.length) ? r.artists.join(', ') : (r.artist || '');
                var prod = (r.producers && r.producers.length) ? r.producers.join(', ') : '';
                sub.textContent = art + (prod ? ' (Prod: ' + prod + ')' : '') + (r.label ? ' - ' + r.label : '');

                info.appendChild(title);
                info.appendChild(sub);

                if (r.source_url) {
                    var link = document.createElement('a');
                    link.href = r.source_url;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.textContent = 'Listen';
                    link.style.fontSize = '0.8rem';
                    link.style.color = '#facc15';
                    info.appendChild(link);
                }

                var scoreBadge = document.createElement('div');
                scoreBadge.className = 'recap-score' + (r.score === 0 ? ' zero' : '');
                scoreBadge.textContent = '+' + (r.score || 0);

                row.appendChild(info);
                row.appendChild(scoreBadge);
                roundRecap.appendChild(row);
            });
        }

        showScreen('endScreen');
        if (playAgainBtn) playAgainBtn.focus();
    }

    // Autocomplete
    function handleAutocomplete(query) {
        if (!query || query.length < 2) {
            if (autocompleteList) autocompleteList.setAttribute('hidden', '');
            return;
        }

        fetch('/api/search/?q=' + encodeURIComponent(query))
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (!data.results || data.results.length === 0) {
                if (autocompleteList) autocompleteList.setAttribute('hidden', '');
                return;
            }

            renderAutocomplete(data.results);
        });
    }

    function renderAutocomplete(results) {
        if (!autocompleteList) return;
        autocompleteList.innerHTML = '';
        gameState.activeSearchIndex = -1;

        results.forEach(function (item, index) {
            var div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.setAttribute('role', 'option');
            div.setAttribute('id', 'auto-opt-' + index);

            var titleSpan = document.createElement('span');
            titleSpan.className = 'autocomplete-title';
            titleSpan.textContent = item.title;

            var artistSpan = document.createElement('span');
            artistSpan.className = 'autocomplete-artist';
            artistSpan.textContent = item.artist;

            div.appendChild(titleSpan);
            div.appendChild(artistSpan);

            div.addEventListener('click', function () {
                if (guessInput) {
                    guessInput.value = item.title;
                    autocompleteList.setAttribute('hidden', '');
                    submitGuess();
                }
            });

            autocompleteList.appendChild(div);
        });

        autocompleteList.removeAttribute('hidden');
    }

    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Event Listeners
    if (startBtn) {
        startBtn.addEventListener('click', startGame);
    }

    if (playAgainBtn) {
        playAgainBtn.addEventListener('click', startGame);
    }

    if (playAudioBtn) {
        playAudioBtn.addEventListener('click', playClip);
    }

    if (submitGuessBtn) {
        submitGuessBtn.addEventListener('click', submitGuess);
    }

    if (skipBtn) {
        skipBtn.addEventListener('click', skipRound);
    }

    if (hintArtistBtn) {
        hintArtistBtn.addEventListener('click', function () {
            requestHint('artist_initial', hintArtistBtn);
        });
    }

    if (hintYearBtn) {
        hintYearBtn.addEventListener('click', function () {
            requestHint('year', hintYearBtn);
        });
    }

    if (hintLangBtn) {
        hintLangBtn.addEventListener('click', function () {
            requestHint('language', hintLangBtn);
        });
    }

    if (guessInput) {
        guessInput.addEventListener('input', function () {
            clearTimeout(gameState.searchTimer);
            var q = guessInput.value.trim();
            gameState.searchTimer = setTimeout(function () {
                handleAutocomplete(q);
            }, 200);
        });

        guessInput.addEventListener('keydown', function (e) {
            if (!autocompleteList || autocompleteList.hasAttribute('hidden')) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submitGuess();
                }
                return;
            }

            var items = autocompleteList.querySelectorAll('.autocomplete-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                gameState.activeSearchIndex = (gameState.activeSearchIndex + 1) % items.length;
                updateActiveSearchItem(items);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                gameState.activeSearchIndex = (gameState.activeSearchIndex - 1 + items.length) % items.length;
                updateActiveSearchItem(items);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (gameState.activeSearchIndex >= 0 && items[gameState.activeSearchIndex]) {
                    var title = items[gameState.activeSearchIndex].querySelector('.autocomplete-title');
                    if (title) guessInput.value = title.textContent;
                    autocompleteList.setAttribute('hidden', '');
                }
                submitGuess();
            } else if (e.key === 'Escape') {
                autocompleteList.setAttribute('hidden', '');
            }
        });
    }

    function updateActiveSearchItem(items) {
        items.forEach(function (el, idx) {
            if (idx === gameState.activeSearchIndex) {
                el.classList.add('active');
                el.scrollIntoView({ block: 'nearest' });
            } else {
                el.classList.remove('active');
            }
        });
    }

    // Dismiss autocomplete when clicking outside
    document.addEventListener('click', function (e) {
        if (autocompleteList && !autocompleteList.contains(e.target) && e.target !== guessInput) {
            autocompleteList.setAttribute('hidden', '');
        }
    });

})();

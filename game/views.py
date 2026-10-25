"""Game API views. All game state lives server-side in Django sessions."""

import hashlib
import json
import random
import time

from django.conf import settings
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from songs.models import Song

from .engine import calculate_score, check_answer


def _get_game_state(request):
    """Get the current game state from session."""
    return request.session.get("game_state", None)


def _set_game_state(request, state):
    """Save game state to session."""
    request.session["game_state"] = state
    request.session.modified = True


def _clear_game_state(request):
    """Clear game state from session."""
    if "game_state" in request.session:
        del request.session["game_state"]
        request.session.modified = True


def _make_round_token(song_id, round_index, session_key):
    """Create a signed token for a round. Not reversible by the client."""
    data = f"{song_id}:{round_index}:{session_key}:{settings.SECRET_KEY}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def _get_audio_data(song):
    """Get audio data for the client. Never includes song metadata."""
    if song.source_type == "youtube":
        return {
            "type": "youtube",
            "youtube_id": song.youtube_id,
            "start": song.start_seconds,
            "end": song.end_seconds,
        }
    else:
        # Generate signed URL or local URL
        audio_url = song.get_audio_url()
        return {
            "type": "upload",
            "url": audio_url,
            "start": song.start_seconds,
            "end": song.end_seconds,
        }


@require_POST
@csrf_protect
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def start_game(request):
    """Start a new game. Returns game info but no answers."""
    songs = list(Song.objects.published().values_list("id", flat=True))

    if not songs:
        return JsonResponse(
            {
                "error": "no_songs",
                "message": "No songs available yet. Check back soon.",
            },
            status=200,
        )

    # Determine round count
    max_rounds = min(10, len(songs))
    selected = random.sample(songs, max_rounds)

    # Shuffle selected songs
    random.shuffle(selected)

    # Store game state in session (song IDs as strings for JSON serialization)
    game_state = {
        "song_ids": [str(sid) for sid in selected],
        "current_round": 0,
        "total_rounds": max_rounds,
        "scores": [],
        "rounds_data": [],
        "total_score": 0,
        "started_at": time.time(),
        "fewer_than_ten": len(songs) < 10,
    }
    _set_game_state(request, game_state)

    response_data = {
        "total_rounds": max_rounds,
        "fewer_than_ten": len(songs) < 10,
        "total_songs_available": len(songs),
    }

    return JsonResponse(response_data)


@require_POST
@csrf_protect
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def get_round(request):
    """
    Get the current round data.
    Returns: round token, audio data, hints available.
    NEVER returns: title, artist, producers, label.
    """
    state = _get_game_state(request)
    if not state:
        return JsonResponse({"error": "no_game", "message": "No active game."}, status=400)

    current = state["current_round"]
    if current >= state["total_rounds"]:
        return JsonResponse(
            {
                "error": "game_over",
                "message": "Game is over.",
                "total_score": state["total_score"],
                "rounds_data": state["rounds_data"],
            }
        )

    song_id = state["song_ids"][current]
    try:
        song = Song.objects.published().get(id=song_id)
    except Song.DoesNotExist:
        # Skip this song if it was unpublished mid-game
        state["current_round"] += 1
        state["rounds_data"].append({"skipped_unavailable": True})
        state["scores"].append(0)
        _set_game_state(request, state)
        return JsonResponse(
            {
                "error": "song_unavailable",
                "message": "Song no longer available. Moving to next round.",
            }
        )

    # Initialize round state if not present
    round_key = f"round_{current}"
    if round_key not in state:
        state[round_key] = {
            "attempts": 0,
            "max_attempts": 3,
            "hints_used": [],
            "replays": 0,
            "max_replays": 3,
            "completed": False,
            "correct": False,
        }
        _set_game_state(request, state)

    round_state = state[round_key]
    session_key = request.session.session_key or "anonymous"
    token = _make_round_token(song_id, current, session_key)

    # Build response - NO song metadata
    audio = _get_audio_data(song)

    available_hints = []
    if "artist_initial" not in round_state["hints_used"]:
        available_hints.append("artist_initial")
    if "year" not in round_state["hints_used"]:
        available_hints.append("year")
    if "language" not in round_state["hints_used"]:
        available_hints.append("language")

    return JsonResponse(
        {
            "round": current + 1,
            "total_rounds": state["total_rounds"],
            "token": token,
            "audio": audio,
            "available_hints": available_hints,
            "hints_used": round_state["hints_used"],
            "attempts": round_state["attempts"],
            "max_attempts": round_state["max_attempts"],
            "replays": round_state["replays"],
            "max_replays": round_state["max_replays"],
            "total_score": state["total_score"],
        }
    )


@require_POST
@csrf_protect
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def submit_guess(request):
    """
    Submit a guess. Checks on server, returns correct/wrong + attempts left.
    Credits returned ONLY when round ends.
    """
    state = _get_game_state(request)
    if not state:
        return JsonResponse({"error": "no_game"}, status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    token = body.get("token", "")
    guess = body.get("guess", "").strip()

    if not guess:
        return JsonResponse({"error": "empty_guess"}, status=400)

    current = state["current_round"]
    if current >= state["total_rounds"]:
        return JsonResponse({"error": "game_over"}, status=400)

    round_key = f"round_{current}"
    round_state = state.get(round_key)
    if not round_state:
        return JsonResponse({"error": "round_not_started"}, status=400)

    if round_state["completed"]:
        return JsonResponse({"error": "round_completed"}, status=400)

    # Verify token
    song_id = state["song_ids"][current]
    session_key = request.session.session_key or "anonymous"
    expected_token = _make_round_token(song_id, current, session_key)
    if token != expected_token:
        return JsonResponse({"error": "invalid_token"}, status=400)

    # Get the song
    try:
        song = Song.objects.published().get(id=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "song_unavailable"}, status=400)

    # Check the answer
    correct = check_answer(guess, song)
    round_state["attempts"] += 1

    if correct:
        round_state["completed"] = True
        round_state["correct"] = True
        score = calculate_score(True, len(round_state["hints_used"]))
        state["total_score"] += score
        state["scores"].append(score)

        # Build credits (only returned when round ends)
        credits_data = _build_credits(song, score, round_state)
        state["rounds_data"].append(credits_data)
        state["current_round"] += 1

        _set_game_state(request, state)

        return JsonResponse(
            {
                "result": "correct",
                "score": score,
                "total_score": state["total_score"],
                "credits": credits_data,
                "game_over": state["current_round"] >= state["total_rounds"],
            }
        )

    else:
        attempts_left = round_state["max_attempts"] - round_state["attempts"]

        if attempts_left <= 0:
            # Round over, answer revealed
            round_state["completed"] = True
            round_state["correct"] = False
            score = 0
            state["scores"].append(score)

            credits_data = _build_credits(song, score, round_state)
            state["rounds_data"].append(credits_data)
            state["current_round"] += 1

            _set_game_state(request, state)

            return JsonResponse(
                {
                    "result": "wrong",
                    "attempts_left": 0,
                    "round_over": True,
                    "score": score,
                    "total_score": state["total_score"],
                    "credits": credits_data,
                    "game_over": state["current_round"] >= state["total_rounds"],
                }
            )

        _set_game_state(request, state)

        return JsonResponse(
            {
                "result": "wrong",
                "attempts_left": attempts_left,
                "round_over": False,
            }
        )


@require_POST
@csrf_protect
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def get_hint(request):
    """Return a single hint and record the penalty server-side."""
    state = _get_game_state(request)
    if not state:
        return JsonResponse({"error": "no_game"}, status=400)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    hint_type = body.get("hint_type", "")
    token = body.get("token", "")

    current = state["current_round"]
    if current >= state["total_rounds"]:
        return JsonResponse({"error": "game_over"}, status=400)

    round_key = f"round_{current}"
    round_state = state.get(round_key)
    if not round_state or round_state["completed"]:
        return JsonResponse({"error": "round_completed"}, status=400)

    # Verify token
    song_id = state["song_ids"][current]
    session_key = request.session.session_key or "anonymous"
    expected_token = _make_round_token(song_id, current, session_key)
    if token != expected_token:
        return JsonResponse({"error": "invalid_token"}, status=400)

    # Check hint type
    valid_hints = ["artist_initial", "year", "language"]
    if hint_type not in valid_hints:
        return JsonResponse({"error": "invalid_hint_type"}, status=400)

    if hint_type in round_state["hints_used"]:
        return JsonResponse({"error": "hint_already_used"}, status=400)

    # Get song for hint data
    try:
        song = Song.objects.published().get(id=song_id)
    except Song.DoesNotExist:
        return JsonResponse({"error": "song_unavailable"}, status=400)

    # Record hint usage
    round_state["hints_used"].append(hint_type)
    _set_game_state(request, state)

    # Return only the requested hint value
    hint_value = ""
    if hint_type == "artist_initial":
        hint_value = song.hint_artist_initial or (song.artist[0].upper() if song.artist else "?")
    elif hint_type == "year":
        hint_value = str(song.hint_year or song.year)
    elif hint_type == "language":
        hint_value = song.hint_language or song.language

    return JsonResponse(
        {
            "hint_type": hint_type,
            "hint_value": hint_value,
            "hints_used": round_state["hints_used"],
            "penalty": 25,
        }
    )


@require_POST
@csrf_protect
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def skip_round(request):
    """Skip the current round. Score is 0. Credits are revealed."""
    state = _get_game_state(request)
    if not state:
        return JsonResponse({"error": "no_game"}, status=400)

    current = state["current_round"]
    if current >= state["total_rounds"]:
        return JsonResponse({"error": "game_over"}, status=400)

    round_key = f"round_{current}"
    round_state = state.get(round_key)
    if not round_state:
        return JsonResponse({"error": "round_not_started"}, status=400)

    if round_state["completed"]:
        return JsonResponse({"error": "round_completed"}, status=400)

    # Mark round as completed with skip
    round_state["completed"] = True
    round_state["correct"] = False
    score = 0
    state["scores"].append(score)

    # Get song for credits
    song_id = state["song_ids"][current]
    try:
        song = Song.objects.published().get(id=song_id)
        credits_data = _build_credits(song, score, round_state)
    except Song.DoesNotExist:
        credits_data = {"unavailable": True, "score": 0}

    state["rounds_data"].append(credits_data)
    state["current_round"] += 1
    _set_game_state(request, state)

    return JsonResponse(
        {
            "result": "skipped",
            "score": score,
            "total_score": state["total_score"],
            "credits": credits_data,
            "game_over": state["current_round"] >= state["total_rounds"],
        }
    )


@require_GET
@ratelimit(key="ip", rate="30/m", method="GET", block=True)
def search_songs(request):
    """
    Autocomplete search. Returns only title and artist strings.
    Minimum 2 characters. Never indicates which is the current answer.
    """
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})

    songs = (
        Song.objects.published()
        .filter(models.Q(title__icontains=query) | models.Q(artist__icontains=query))
        .values("title", "artist")
        .distinct()[:15]
    )

    results = [{"title": s["title"], "artist": s["artist"]} for s in songs]
    return JsonResponse({"results": results})


def _build_credits(song, score, round_state):
    """Build credits data for a completed round. Only called after round ends."""
    return {
        "title": song.title,
        "artist": song.artist,
        "artists": song.artists if song.artists else [song.artist],
        "producers": song.producers,
        "label": song.label,
        "year": song.year,
        "source_url": song.source_url,
        "score": score,
        "correct": round_state["correct"],
        "hints_used": len(round_state["hints_used"]),
        "attempts": round_state["attempts"],
    }

"""Tests for Game API, leak protection, and flow."""

import json

import pytest
from django.urls import reverse

from songs.models import Song


@pytest.fixture
def sample_songs(db):
    songs = []
    # Create 3 published, verified songs
    for i in range(3):
        song = Song.objects.create(
            title=f"Published Song {i + 1}",
            artist=f"Artist {i + 1}",
            artists=[f"Artist {i + 1}"],
            producers=[f"Producer {i + 1}"],
            label="Test Label",
            year=2020 + i,
            language="Hindi",
            accepted_answers=[f"Song {i + 1}", f"Track {i + 1}"],
            source_type="youtube",
            youtube_id=f"ytid_{i + 1}_123",
            start_seconds=10,
            end_seconds=22,
            source_url=f"https://example.com/song-{i + 1}",
            verified=True,
            status="published",
        )
        songs.append(song)

    # Create 1 draft song (MUST NEVER LEAK)
    Song.objects.create(
        title="Secret Draft Track",
        artist="Hidden Artist",
        producers=["Secret Producer"],
        label="Secret Label",
        year=2022,
        language="Hindi",
        source_type="youtube",
        youtube_id="secret_draft_yt",
        start_seconds=10,
        end_seconds=22,
        source_url="https://example.com/secret",
        verified=False,
        status="draft",
    )

    # Create 1 published but unverified song (MUST NEVER LEAK)
    Song.objects.create(
        title="Unverified Track",
        artist="Unverified Artist",
        producers=["Unverified Producer"],
        label="Test Label",
        year=2021,
        language="Hindi",
        source_type="youtube",
        youtube_id="unverified_yt",
        start_seconds=10,
        end_seconds=22,
        source_url="https://example.com/unverified",
        verified=False,
        status="draft",  # kept draft since unverified can't be saved as published
    )
    return songs


@pytest.mark.django_db
class TestAnswerLeakProtection:
    def test_round_endpoint_never_leaks_answer(self, client, sample_songs):
        # 1. Start game
        start_res = client.post(reverse("game:start"))
        assert start_res.status_code == 200
        start_data = start_res.json()
        assert start_data["total_rounds"] == 3

        # 2. Get round data
        round_res = client.post(reverse("game:round"))
        assert round_res.status_code == 200
        round_data = round_res.json()

        # LEAK CHECK:
        # None of the published song titles, artists, producers, or labels should appear in response
        response_text = round_res.content.decode("utf-8").lower()
        for song in sample_songs:
            assert song.title.lower() not in response_text
            assert song.artist.lower() not in response_text
            assert song.label.lower() not in response_text

        # Draft song must never leak
        assert "secret draft track" not in response_text
        assert "hidden artist" not in response_text

        # Token must be present
        assert "token" in round_data
        assert "audio" in round_data

    def test_autocomplete_never_returns_drafts(self, client, sample_songs):
        # Search query matching draft song
        res = client.get(reverse("game:search") + "?q=secret")
        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) == 0

        # Search query matching published song
        res_pub = client.get(reverse("game:search") + "?q=Published")
        assert res_pub.status_code == 200
        data_pub = res_pub.json()
        assert len(data_pub["results"]) > 0
        for item in data_pub["results"]:
            assert "Secret" not in item["title"]


@pytest.mark.django_db
class TestFullGameFlow:
    def test_complete_game_mechanics(self, client, sample_songs):
        # Start game
        client.post(reverse("game:start"))

        # Round 1: Correct guess on first attempt with 1 hint
        round1_res = client.post(reverse("game:round")).json()
        token1 = round1_res["token"]

        # Request artist initial hint
        hint_res = client.post(
            reverse("game:hint"),
            data=json.dumps({"token": token1, "hint_type": "artist_initial"}),
            content_type="application/json",
        )
        assert hint_res.status_code == 200
        hint_data = hint_res.json()
        assert hint_data["hint_type"] == "artist_initial"
        assert len(hint_data["hint_value"]) == 1

        # Submit guess using session state's current song
        state = client.session["game_state"]
        song_id = state["song_ids"][0]
        song1 = Song.objects.get(id=song_id)

        guess_res = client.post(
            reverse("game:guess"),
            data=json.dumps({"token": token1, "guess": song1.title}),
            content_type="application/json",
        )
        assert guess_res.status_code == 200
        guess_data = guess_res.json()
        assert guess_data["result"] == "correct"
        # 100 - 25 = 75
        assert guess_data["score"] == 75
        assert guess_data["total_score"] == 75
        # Full credits returned after round ends
        assert "credits" in guess_data
        assert guess_data["credits"]["title"] == song1.title

        # Round 2: Skip round
        round2_res = client.post(reverse("game:round")).json()
        token2 = round2_res["token"]

        skip_res = client.post(
            reverse("game:skip"),
            data=json.dumps({"token": token2}),
            content_type="application/json",
        )
        assert skip_res.status_code == 200
        skip_data = skip_res.json()
        assert skip_data["result"] == "skipped"
        assert skip_data["score"] == 0
        assert skip_data["total_score"] == 75

        # Round 3: 3 wrong attempts, answer revealed
        round3_res = client.post(reverse("game:round")).json()
        token3 = round3_res["token"]

        # Wrong guess 1
        w1 = client.post(
            reverse("game:guess"),
            data=json.dumps({"token": token3, "guess": "Wrong guess 1"}),
            content_type="application/json",
        ).json()
        assert w1["result"] == "wrong"
        assert w1["attempts_left"] == 2
        assert w1["round_over"] is False

        # Wrong guess 2
        w2 = client.post(
            reverse("game:guess"),
            data=json.dumps({"token": token3, "guess": "Wrong guess 2"}),
            content_type="application/json",
        ).json()
        assert w2["result"] == "wrong"
        assert w2["attempts_left"] == 1
        assert w2["round_over"] is False

        # Wrong guess 3 (exhausts attempts)
        w3 = client.post(
            reverse("game:guess"),
            data=json.dumps({"token": token3, "guess": "Wrong guess 3"}),
            content_type="application/json",
        ).json()
        assert w3["result"] == "wrong"
        assert w3["attempts_left"] == 0
        assert w3["round_over"] is True
        assert w3["score"] == 0
        assert w3["game_over"] is True
        assert "credits" in w3

        # Final check: getting round now returns game_over
        over_res = client.post(reverse("game:round")).json()
        assert over_res["error"] == "game_over"
        assert over_res["total_score"] == 75

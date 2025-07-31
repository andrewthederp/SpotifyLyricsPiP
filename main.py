from __future__ import annotations

import pyglet.libs.win32.constants
pyglet.libs.win32.constants.HWND_NOTOPMOST = pyglet.libs.win32.constants.HWND_TOPMOST  # make window always on-top. Is there a better way?

import re
import arcade
import pyglet
import typing
import spotipy
import sqlite3
import requests
import threading

from arcade import clock
from typing import TYPE_CHECKING
from spotipy.oauth2 import SpotifyOAuth
from config import get_config, save_config
from Pylette import extract_colors, Color as ColorLette
from utilities.arcade_utilities import DebugScreen, PiPWindow, CommandView
from lyric_views import LyricsView, LyricErrorView
from commands import CustomCommandView

# Setup
arcade.enable_timings()

config = get_config()
print(config)

database = sqlite3.connect("lyrics.db", check_same_thread=False)
database.execute("CREATE TABLE IF NOT EXISTS lyrics (artist_names TEXT, album_name TEXT, track_name TEXT, duration FLOAT, synced_lyrics TEXT, PRIMARY KEY(artist_names, album_name, track_name, duration))")
database.execute("CREATE TABLE IF NOT EXISTS colors (song_id TEXT PRIMARY KEY, color TEXT)")

_data = database.execute("SELECT song_id, color FROM colors")
COLORS = {song_id: int(color) for song_id, color in _data.fetchall()}


arcade.resources.add_resource_handle("fonts", r"C:\Users\gomaa\PycharmProjects\SpotifyTest")
arcade.load_font(r"C:\Users\gomaa\PycharmProjects\SpotifyTest\CircularStd_Black.otf")

spotify = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        scope="user-read-private,user-read-email,user-read-currently-playing",
        client_id=config["spotify client id"],
        client_secret=config["spotify client secret"],
        redirect_uri="http://localhost:5173/callback"
    )
)
# Setup end


int_to_rgb = lambda num: ((num >> 16) & 0xFF, (num >> 8) & 0xFF, num & 0xFF)
rgb_to_int = lambda rgb: (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]

def get_luminance(color: tuple[int, int, int] | ColorLette):
    if isinstance(color, ColorLette):
        color = color.rgb

    return 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]

def get_saturation(color: tuple[int, int, int] | ColorLette):
    if isinstance(color, ColorLette):
        color = color.rgb

    r, g, b = color
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    if r == g == b:
        return 0

    return (max_c - min_c) / max_c


class Song:
    data: dict | None
    id:   str  | None

    def __init__(self, song_data):
        self.lyric_data = {}
        if song_data is None:
            self.data = None
            self.id = None
            self.paused = False
            self.progress_ms = float("inf")
            self.pallete: list[tuple[int, int, int]] = []
            return

        self.data = song_data
        self.id = song_data["item"]["id"]
        self.time = clock.GLOBAL_CLOCK.time
        self.paused = not song_data["is_playing"]

        self.progress_ms = int(song_data["progress_ms"])

        self.pallete: list[tuple[int, int, int]] = []

    def update(self, song_data) -> bool | None:
        if song_data is None:
            self.lyric_data = {}
            self.data = None
            self.id = None
            self.paused = False
            self.progress_ms = float("inf")
            return

        song_changed = False

        self.data = song_data

        if song_data["item"]["id"] != self.id:
            song_changed = True
            self.time = clock.GLOBAL_CLOCK.time
            self.lyric_data = {}

        self.id = song_data["item"]["id"]
        self.progress_ms = int(song_data["progress_ms"])
        self.paused = not song_data["is_playing"]

        return song_changed

    def __repr__(self) -> str:
        return str(self.id)

    def _set_lyric_data(self, data: list):
        assert self.data is not None

        synced_lyrics = ""

        for line in data:
            start_time_ms = line["start"]
            text = line["text"]

            start_time = start_time_ms / 1000
            minutes, seconds = divmod(start_time, 60)
            milliseconds = str(seconds - int(seconds)).split(".")[1][:2]
            seconds = int(seconds)

            synced_lyrics += f"[{int(minutes):02}:{int(seconds):02}.{milliseconds:02}] {text}\n"

        self.lyric_data = {
            "track_name": self.data["item"]["name"],
            "artist_names": "-".join(artist["name"] for artist in self.data["item"]["artists"]),
            "album_name": self.data["item"]["album"]["name"],
            "duration": self.data["item"]["duration_ms"] / 1000,
            "synced_lyrics": synced_lyrics[:-1]
        }

    def _get_colors(self) -> dict[typing.Literal["background", "text"], tuple[int, int, int]]:
        if self.data is None:
            return {
                "background": (51, 51, 51),
                "text": (230, 230, 230)
            }

        image_url: str = self.data["item"]["album"]["images"][0]["url"]
        response = requests.get(image_url)
        if response.status_code != 200:
            print("FUCK?")
            return {
                "background": (51, 51, 51),
                "text": (230, 230, 230)
            }

        # bytes = data.text.encode()
        # pallete = extract_dominant_color(io.BytesIO(response.content))

        self.pallete: list[tuple[int, int, int]] = [tuple(color.rgb) for color in extract_colors(image_url, palette_size=10).colors]  # type: ignore

        if self.id in COLORS:
            rgb = int_to_rgb(COLORS[self.id])
            print("Got color from the database")
        else:
            print("Got the highest saturation color")
            rgb = max(self.pallete, key=get_saturation)
            self._save_color(rgb)  # type: ignore

        if TYPE_CHECKING:
            rgb = typing.cast(tuple[int, int, int], rgb)


        luma = get_luminance(rgb)
        text = (230, 230, 230) if luma < 40 else (25, 25, 25)
        print("Pallete", self.pallete)
        return {
            "background": rgb,
            "text": text,
        }

    def _save_color(self, rgb: tuple[int, int, int]):
        print("Saving color", rgb)
        num = rgb_to_int(rgb)
        COLORS[self.id] = num
        cur = database.cursor()
        cur.execute("INSERT INTO colors (song_id, color) VALUES (?, ?) ON CONFLICT(song_id) DO UPDATE SET color = EXCLUDED.color", (self.id, str(num)))
        database.commit()
        cur.close()

    def set_color(self, rgb: tuple[int, int, int]):
        COLORS[self.id] = rgb_to_int(rgb)
        self._save_color(rgb)

        luma = get_luminance(rgb)
        text = (230, 230, 230) if luma < 40 else (25, 25, 25)

        return {
            "background": rgb,
            "text": text,
        }

    def change_color(self, background, direction: typing.Literal[1, -1]) -> dict | None:
        if self.data is None or self.id is None:
            return None

        try:
            index = self.pallete.index(background.rgb)
        except ValueError:
            index = -direction

        new_index = index + direction
        if new_index >= len(self.pallete):
            new_index = 0
        elif new_index < 0:
            new_index = len(self.pallete) - 1

        new_rgb: tuple[int, int, int] = self.pallete[new_index]
        COLORS[self.id] = rgb_to_int(new_rgb)
        self._save_color(new_rgb)

        luma = get_luminance(new_rgb)
        text = (230, 230, 230) if luma < 40 else (25, 25, 25)

        return {
            "background": new_rgb,
            "text": text,
        }
        

    @staticmethod
    def _parse_lyrics_string(synced_lyrics: str) -> dict:
        lyric_data: dict = {
            "lyrics": (lines := [])
        }

        pattern = r"\[(?P<minutes>\d{2}):(?P<seconds>\d{2}.\d{2})] (?P<text>([^\[\\])*)?"
        for match in re.finditer(pattern, synced_lyrics, re.RegexFlag.MULTILINE):
            start = (int(match["minutes"]) * 60 + float(match["seconds"])) * 1000
            text = match["text"].strip() or "♪"
            lines.append({
                "start": start,
                "text": text
            })

        return lyric_data

    def _get_local_data(self) -> dict | None:  # I wanted this to search through files instead of a local db but that was a bit difficult
        assert self.data is not None

        track_name = self.data["item"]["name"]
        artist_names = "-".join(artist["name"] for artist in self.data["item"]["artists"])
        album_name = self.data["item"]["album"]["name"]
        duration = self.data["item"]["duration_ms"] / 1000

        cur = database.cursor()
        cur.execute("""SELECT synced_lyrics 
                                  FROM lyrics 
                                  WHERE 
                                    track_name = ? AND
                                    artist_names = ? AND
                                    album_name = ? AND
                                    duration >= ? AND
                                    duration <= ?
                                """, (track_name, artist_names, album_name, duration - 2, duration + 2)
        )

        data = cur.fetchone()
        cur.close()
        if data is None:
            return None

        print("Got data from local db")
        return self._parse_lyrics_string(data[0])

    def _get_lrclib_data(self) -> dict | None:
        assert self.data is not None

        params = {
            "track_name": self.data["item"]["name"],
            "artist_name": "-".join(artist["name"] for artist in self.data["item"]["artists"]),
            "album_name": self.data["item"]["album"]["name"],
            "duration": self.data["item"]["duration_ms"] / 1000
        }

        data = requests.get(
            "https://lrclib.net/api/get",
            params=params
        )

        if data.status_code != 200:
            print("NOT BUENO", data.status_code)
            return

        json = data.json()
        if json["instrumental"]:
            print("INSTRUMENTAL")
            return

        synced_lyrics = json["syncedLyrics"]
        if synced_lyrics is None:
            print("No Synced lyrics")
            return

        print("Got data from lrclib")
        return self._parse_lyrics_string(synced_lyrics)

    def get_lyric_data(self):
        for func in (self._get_local_data, self._get_lrclib_data):
            data = func()
            if data:
                break

        if isinstance(data, dict):
            self._set_lyric_data(data["lyrics"])
            if config["save lyrics"]:
                self.save_lyric_data()

            data["colors"] = self._get_colors()

        return data

    def save_lyric_data(self) -> bool:
        if not self.lyric_data:
            print("No lyric data")
            return False

        values = (self.lyric_data["artist_names"], self.lyric_data["album_name"], self.lyric_data["track_name"], self.lyric_data["duration"], self.lyric_data["synced_lyrics"])

        cur = database.cursor()
        cur.execute("INSERT OR IGNORE INTO lyrics (artist_names, album_name, track_name, duration, synced_lyrics) VALUES (?, ?, ?, ?, ?)", values)
        database.commit()
        cur.close()

        return True


class Window(PiPWindow):
    current_view: LyricsView | CustomCommandView  # type: ignore

    def __init__(self):
        super().__init__((int(100 * 1.78), 100), *config["window size"], "Spotify Lyrics")
        self.current_song = Song(None)
        self.last_check = 0
        self.checking: bool = False

        x, y = config["window center pos"]
        x -= self.width // 2
        y -= self.height // 2

        self.set_location(int(x), int(y))

        self.debug_screen = DebugScreen(
            font_name="Circular Std Black",
            font_size=10,
            color=(255, 255, 255),
            bg_color=(0, 0, 0),
            do_draw=config["debug mode"]
        )
        self.debug_screen["FPS"] = lambda: int(arcade.get_fps())
        self.debug_screen["Progress"] = lambda: round(self.current_song.progress_ms / 1000) if self.current_song.progress_ms != float('inf') else "infinite"
        self.debug_screen["Song"] = lambda: self.current_song
        self.debug_screen["Color"] = lambda: self.current_view.background_color if self.current_view else None

        self.command_view = CustomCommandView(self, font="Circular Std Black", font_size=15, config=config, database=database)

    def exit_command_view(self, view):
        super().show_view(view)

    def show_view(self, view):
        if isinstance(self.current_view, CustomCommandView):
            self.current_view.background_view = view
            return
        elif view == self.command_view:
            self.current_view: LyricsView
            self.command_view.background_view = self.current_view

        super().show_view(view)

    def on_key_press(self, symbol: int, modifiers: int):
        if not isinstance(self.current_view, CommandView):
            if TYPE_CHECKING:
                assert isinstance(self.current_view, LyricsView)

            if symbol == arcade.key.R and modifiers & arcade.key.MOD_CTRL:
                self.last_check = 0
            elif symbol == arcade.key.S and modifiers & arcade.key.MOD_CTRL:
                print("Saving")
                success = self.current_song.save_lyric_data()
                print("Saved" if success else "Failed to save")
            elif symbol == arcade.key.F5:
                self.debug_screen.do_draw = not self.debug_screen.do_draw
            elif not isinstance(self.current_view, LyricErrorView) and modifiers & arcade.key.MOD_SHIFT:
                if symbol == arcade.key.LEFT:
                    data = self.current_song.change_color(self.current_view.background_color, -1)
                    self.current_view.update_colors(data)
                elif symbol == arcade.key.RIGHT:
                    data = self.current_song.change_color(self.current_view.background_color, 1)
                    self.current_view.update_colors(data)
            elif self.current_view and symbol == arcade.key.SLASH:
                self.command_view.on_resize(*self.size)
                self.show_view(self.command_view)
                self.command_view.input_area.text = "/"

    def resized(self):
        view = self.current_view

        w, h = self.size
        if view:
            view.resized(w, h)
        self.debug_screen.adjust_positions() 

    def save_config(self):
        x, y = self.get_location()
        w, h = self.get_size()
        config["window center pos"] = (x + w // 2, y + h // 2)
        config["window size"] = (w, h)
        save_config(config)

    def on_draw(self):
        pass

    def on_close(self):
        self.save_config()
        database.close()
        super().on_close()

    def update_view(self):
        self.checking = True
        try:
            print("Getting the song")
            current_song = spotify.current_user_playing_track()  # sends a request and can take a while
        except (requests.ConnectionError, requests.ReadTimeout):
            print("Timed out")
            if self.current_view is None:
                f = lambda _: self.show_view(LyricErrorView(self, "Can't detect a spotify song..."))
                arcade.schedule_once(f, 0)

            self.checking = False
            self.last_check = clock.GLOBAL_CLOCK.time

            return

        if (self.current_view is None or not isinstance(self.current_view, LyricErrorView)) and not current_song:
            print("Can't detect song")
            f = lambda _: self.show_view(LyricErrorView(self, "Can't detect a spotify song..."))
            arcade.schedule_once(f, 0)
        else:
            song_changed = self.current_song.update(current_song)  # sends a request/uses the db and can take a while

            if song_changed:
                # TODO: Loading lyrics view
                print("Song Changed")
                data = self.current_song.get_lyric_data()
                if data is None:
                    print("No Lyrics")
                    f = lambda _: self.show_view(LyricErrorView(self, "Sorry, can't find the lyrics for this song..."))
                    arcade.schedule_once(f, 0)
                else:
                    f = lambda _: self.show_view(LyricsView.from_data(data))
                    arcade.schedule_once(f, 0)

        self.checking = False
        self.last_check = clock.GLOBAL_CLOCK.time

    def on_update(self, td):
        super().on_update(td)

        if clock.GLOBAL_CLOCK.time - self.last_check < config["update seconds"]:
            if hasattr(self.current_song, "progress_ms") and not getattr(self.current_song, "paused", False):
                self.current_song.progress_ms += td * 850
            return

        if self.checking is False:
            if self.current_view:
                self.current_view.readjust(*self.size)

            threading.Thread(target=self.update_view, daemon=True).start()


if __name__ == "__main__":
    try:
        window = Window()
        window.run()
    except KeyboardInterrupt:
        window.save_config()

from __future__ import annotations

import arcade
import pyglet

from typing import TYPE_CHECKING
from config import get_config
from arcade import clock

if TYPE_CHECKING:
    from main import Window


config = get_config()


class LyricLine(arcade.Text):
    def __init__(self, start_time_ms, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time_ms = int(start_time_ms)

        self.lyric_view: LyricsView | None = None

    def __repr__(self):
        return f"<LyricLine start={round(self.start_time_ms / 1000, 2)}, text={self.text}>"

    def update(self):
        assert self.lyric_view is not None

        window: Window = arcade.get_window()  # type: ignore
        current_song = window.current_song

        if current_song.progress_ms >= self.start_time_ms:
            self.color = (*self.lyric_view.text_color, 255)
        else:
            self.color = (*self.lyric_view.text_color, 140)

class LyricsView(arcade.View):
    window: Window

    def __init__(self, window: Window, lyrics: list[LyricLine], background_color: tuple[int, int, int], text_color: tuple[int, int, int]):
        super().__init__(window, background_color)
        self.text_color = text_color

        self.lyrics = sorted(lyrics, key=lambda l: l.start_time_ms)
        self.batch = pyglet.graphics.Batch()

        for lyric_line in self.lyrics:
            lyric_line.batch = self.batch
            lyric_line.lyric_view = self

        self.latest_lyric_line: LyricLine = lyrics[0]
        self.readjust(*window.size)

    def update_colors(self, data):
        self.background_color = data["background"]
        self.text_color: tuple[int, int, int] = data["text"]

    def on_update(self, _):
        window: Window = self.window  # type: ignore
        progress = window.current_song.progress_ms

        current_line = self.lyrics[0]
        for i, lyric_line in enumerate(self.lyrics, start=1):
            lyric_line.update()
            if lyric_line.start_time_ms <= progress:
                current_line = self.lyrics[i - 1]
                # print(lyric_line.start_time_ms, progress, current_line.start_time_ms)

        # if progress < self.lyrics[0].start_time_ms:
        #     current_line = self.lyrics[0]
        # else:
        #     current_line = max(self.lyrics, key=lambda l: (l.start_time_ms <= progress, l.start_time_ms))

        if current_line == self.latest_lyric_line:
            return
        elif current_line.y >= (window.height // 2 + current_line.content_height // 2):
            self.latest_lyric_line = current_line
            return

        num = min(8, window.height // 2 - (current_line.y - current_line.content_height // 2))
        for lyric_line in self.lyrics:
            lyric_line.y += num

    @classmethod
    def from_data(cls, data):
        window: Window = arcade.get_window()  # type: ignore

        lyrics = []
        text_color = data["colors"]["text"]

        y = window.height
        for i, line in enumerate(data["lyrics"]):
            lyric_line = LyricLine(
                line["start"],
                text=line["text"],
                x=0,
                y=y,
                font_name="Circular Std Black",
                font_size=config["font size"],
                multiline=True,
                width=arcade.get_window().width,
                # anchor_x="center",
                anchor_y="top",
                color=(*text_color, 140)
            )

            y -= lyric_line.content_height + 15

            lyrics.append(lyric_line)

        return cls(
            window,
            lyrics,
            background_color=data["colors"]["background"],
            text_color=text_color
        )

    def readjust(self, width, height):
        window: Window = self.window  # type: ignore
        progress = window.current_song.progress_ms

        if progress < self.lyrics[0].start_time_ms:
            current_line = self.lyrics[0]
        else:
            current_line = max(self.lyrics, key=lambda l: (l.start_time_ms <= progress, l.start_time_ms))

        self.latest_lyric_line = current_line

        y = height
        for lyric_line in self.lyrics:
            lyric_line.x = width // 16
            lyric_line.width = width - lyric_line.x * 2
            lyric_line.y = y
            y -= lyric_line.content_height + config["seperation size"]

        wanted_y = height // 2 + current_line.content_height // 2
        current_y = current_line.y

        diff = wanted_y - current_y

        for lyric_line in self.lyrics:
            lyric_line.y += diff

    def resized(self, width, height):
        self.readjust(width, height)

    def on_draw(self):
        self.clear()

        radius = 10
        perc = min(1, (clock.GLOBAL_CLOCK.time - self.window.last_check) / config["update seconds"])
        arcade.draw_arc_outline(
            center_x=self.width - radius,
            center_y=self.height - radius,
            width=radius,
            height=radius,
            color=(*self.text_color, 140),
            start_angle=-360 * perc,
            end_angle=0,
            tilt_angle=270,
            border_width=radius / 2,
            num_segments=256
        )

        self.batch.draw()

        if config["debug line"]:
            arcade.draw_line(0, self.height // 2, self.width, self.height // 2, (0, 0, 0), 3)
            arcade.draw_line(0, self.height // 2, self.width, self.height // 2, (255, 255, 255), 1)

        # if song and song.data:
        #     arcade.draw_lbwh_rectangle_filled(0, 0, self.width * (song.progress_ms / song.data["item"]["duration_ms"]), self.height / 32, (*self.text_color, 100))

        self.window.debug_screen.draw()


class LyricErrorView(LyricsView):
    def __init__(self, window: Window, message: str):
        lyrics = [
            LyricLine(
                0,
                text=message,
                x=window.width // 2,
                y=window.height // 2,
                font_name="Circular Std Black",
                font_size=35,
                # multiline=True,
                # width=arcade.get_window().width,
                anchor_x="center",
                anchor_y="center",
                color=(230, 230, 230)
            )
        ]

        super().__init__(window, lyrics=lyrics, background_color=(51, 51, 51), text_color=(230, 230, 230))

    def resized(self, width, height):
        lyric_line = self.lyrics[0]
        lyric_line.x = width // 2
        lyric_line.y = height // 2

    def on_update(self, _):
        self.resized(*self.size)

    @classmethod
    def from_data(cls, message):
        return cls(arcade.get_window(), message)  # type: ignore

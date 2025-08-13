from __future__ import annotations


import pyglet
from utilities.arcade_utilities import CommandView, CommandContext  # type: ignore
from utilities.commands import ColorConverter, command
from lyric_views import LyricsView, LyricErrorView
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import Window


class CommandContext(CommandContext): # type: ignore
    def __init__(self, window: Window, command_view: CommandView, config, database) -> None:
        super().__init__(window, command_view)
        self.config = config
        self.database = database


class CustomCommandView(CommandView):
    background_view: LyricsView

    def __init__(self, *args, config, database, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.database = database

    def get_context(self) -> CommandContext:
        context = CommandContext(
            self.window,  # type: ignore
            command_view=self,
            config=self.config,
            database=self.database
        )

        return context

    def readjust(self, width, height):
        self.background_view.readjust(width, height)

    def resized(self, width, height):
        self.background_view.resized(width, height)


@command()
def exit(ctx: CommandContext):
    window: Window = ctx.window  # type: ignore
    window.save_config()
    ctx.database.close()
    window.on_close()

@command()
def set_color(ctx: CommandContext, *, color: ColorConverter):
    rgb = color.rgb

    view: LyricsView = ctx.command_view.background_view  # type: ignore
    if isinstance(view, LyricErrorView):
        ctx.send("❌ No lyrics currently showing")
        return

    window: Window = ctx.window  # type: ignore
    data = window.current_song.set_color(rgb)
    view.update_colors(data)

    ctx.send("Changed the color to ", end="")
    ctx.send(color.rgba, color=color.rgba)

@command()
def set_font_size(ctx: CommandContext, font_size: int):
    view: LyricsView = ctx.command_view.background_view  # type: ignore
    ctx.config["font size"] = font_size

    for lyric_line in view.lyrics:
        lyric_line.font_size = font_size

    view.readjust(*ctx.window.size)
    ctx.send("Changed the font size to ", end="")
    ctx.send(font_size, weight=pyglet.text.Weight.BOLD, underline=(255, 255, 255, 255))

@command()
def set_seperation_size(ctx: CommandContext, seperation_size: int):
    view: LyricsView = ctx.command_view.background_view  # type: ignore
    ctx.config["seperation size"] = seperation_size

    view.readjust(*ctx.window.size)
    ctx.send("Changed the seperation size to ", end="")
    ctx.send(seperation_size, weight=pyglet.text.Weight.BOLD, underline=(255, 255, 255, 255))


@command()
def get_song_data(ctx: CommandContext):
    window: Window = ctx.window  # type: ignore
    print(window.current_song.data)

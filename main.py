import asyncio
import curses
import os
import random
import time
from itertools import cycle

from curses_tools import draw_frame, get_frame_size, read_controls, update_speed
from obstacles import Obstacle

coroutines, obstacles, obstacles_in_last_collisions = [], [], []
year = 1957
EXPLOSION_FRAMES = [
    """\
           (_)
       (  (   (  (
      () (  (  )
        ( )  ()
    """,
    """\
           (_)
       (  (   (
         (  (  )
          )  (
    """,
    """\
            (
          (   (
         (     (
          )  (
    """,
    """\
            (
              (
            (
    """,
]
PHRASES = {
    1957: "First Sputnik",
    1961: "Gagarin flew!",
    1969: "Armstrong got on the moon!",
    1971: "First orbital space station Salute-1",
    1981: "Flight of the Shuttle Columbia",
    1998: 'ISS start building',
    2011: 'Messenger launch to Mercury',
    2020: "Take the plasma gun! Shoot the garbage!",
}


def get_animations_frames(path):
    file_names = os.listdir(path)
    animations_frames = []
    for file_name in file_names:
        with open(os.path.join(path, file_name), 'r') as file:
            animations_frames.append(file.read())
    return animations_frames


async def sleep(tics=1):
    for _ in range(tics):
        await asyncio.sleep(0)


async def blink(canvas, row, column, symbol='*', offset_tics=0):
    while True:
        canvas.addstr(row, column, symbol, curses.A_DIM)
        await sleep(tics=20)
        await sleep(tics=offset_tics)
        canvas.addstr(row, column, symbol)
        await sleep(tics=3)
        canvas.addstr(row, column, symbol, curses.A_BOLD)
        await sleep(tics=5)
        canvas.addstr(row, column, symbol)
        await sleep(tics=3)


async def fire(canvas, start_row, start_column, rows_speed=-0.3, columns_speed=0):
    row, column = start_row, start_column

    canvas.addstr(round(row), round(column), '*')
    await asyncio.sleep(0)

    canvas.addstr(round(row), round(column), 'O')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), ' ')

    row += rows_speed
    column += columns_speed

    symbol = '-' if columns_speed else '|'

    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - 1, columns - 1

    curses.beep()

    while 0 < row < max_row and 0 < column < max_column:
        for obstacle in obstacles:
            if obstacle.has_collision(row, column):
                obstacles_in_last_collisions.append(obstacle)
                return
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


def get_new_rocket_coordinates(canvas, rocket_frame, rocket_row, rocket_column, rows_direction,
                               columns_direction, canvas_border_indent, row_speed, column_speed):
    frame_rows, frame_columns = curses.window.getmaxyx(canvas)
    row_speed, column_speed = update_speed(row_speed, column_speed, rows_direction, columns_direction)
    rocket_row += row_speed
    rocket_column += column_speed
    rocket_height, rocket_width = get_frame_size(rocket_frame)
    rocket_row = max(rocket_row, canvas_border_indent)
    rocket_row = min(rocket_row, frame_rows - rocket_height - canvas_border_indent)
    rocket_column = max(rocket_column, canvas_border_indent)
    rocket_column = min(rocket_column, frame_columns - rocket_width - canvas_border_indent)
    return rocket_row, rocket_column, row_speed, column_speed


async def animate_spaceship(canvas, rocket_frames, rocket_column, rocket_row, canvas_border_indent):
    row_speed = column_speed = 0
    for rocket_frame in cycle(rocket_frames):
        rocket_height, rocket_width = get_frame_size(rocket_frame)
        for obstacle in obstacles:
            if obstacle.has_collision(rocket_row, rocket_column, obj_size_rows=rocket_height,
                                      obj_size_columns=rocket_width):
                right_border, bottom_border = curses.window.getmaxyx(canvas)
                center_row, center_column = right_border / 2, bottom_border / 2
                await show_game_over(canvas, center_row, center_column)
                return
        rows_direction, columns_direction, space_pressed = read_controls(canvas)
        rocket_row, rocket_column, row_speed, column_speed = get_new_rocket_coordinates(
            canvas,
            rocket_frame,
            rocket_row,
            rocket_column,
            rows_direction,
            columns_direction,
            canvas_border_indent,
            row_speed,
            column_speed
        )
        draw_frame(canvas, rocket_row, rocket_column, rocket_frame)
        await asyncio.sleep(0)
        draw_frame(canvas, rocket_row, rocket_column, rocket_frame, negative=True)
        if year < 2020:
            continue
        if space_pressed:
            fire_column = rocket_column + rocket_width / 2
            coroutines.append(fire(canvas, rocket_row, fire_column, rows_speed=-2))


async def explode(canvas, center_row, center_column):
    rows, columns = get_frame_size(EXPLOSION_FRAMES[0])
    corner_row = center_row - rows / 2
    corner_column = center_column - columns / 2

    curses.beep()
    for frame in EXPLOSION_FRAMES:
        draw_frame(canvas, corner_row, corner_column, frame)

        await asyncio.sleep(0)
        draw_frame(canvas, corner_row, corner_column, frame, negative=True)
        await asyncio.sleep(0)


async def fly_garbage(canvas, column, garbage_frame, speed=0.5):
    rows_number, columns_number = canvas.getmaxyx()
    column = max(column, 0)
    column = min(column, columns_number - 1)
    garbage_row_size, garbage_column_size = get_frame_size(garbage_frame)
    row = 0
    while row < rows_number:
        obstacle = Obstacle(row, column, garbage_row_size, garbage_column_size)
        obstacles.append(obstacle)
        draw_frame(canvas, row, column, garbage_frame)
        await asyncio.sleep(0)
        draw_frame(canvas, row, column, garbage_frame, negative=True)
        obstacles.remove(obstacle)
        if obstacle in obstacles_in_last_collisions:
            await explode(canvas, row + garbage_row_size / 2, column + garbage_column_size / 2)
            obstacles_in_last_collisions.remove(obstacle)
            return
        row += speed


async def show_game_over(canvas, center_row, center_column):
    space_game_over_path = os.path.join('animations_frames', 'game_over')
    game_over_frame = get_animations_frames(space_game_over_path)[0]
    rows, columns = get_frame_size(game_over_frame)
    corner_row = center_row - rows / 2
    corner_column = center_column - columns / 2
    curses.beep()
    while True:
        await asyncio.sleep(0)
        draw_frame(canvas, corner_row, corner_column, game_over_frame)


def get_garbage_delay_tics(current_year):
    if current_year < 1961:
        return None
    if current_year < 1969:
        return 20
    if current_year < 1981:
        return 14
    if current_year < 1995:
        return 10
    if current_year < 2010:
        return 8
    if current_year < 2020:
        return 6
    return 2


async def fill_orbit_with_garbage(canvas, space_garbage_frames, canvas_border_indent):
    _, frame_columns = curses.window.getmaxyx(canvas)
    while True:
        garbage_delay_tics = get_garbage_delay_tics(year)
        if not garbage_delay_tics:
            await sleep(tics=1)
            continue
        await sleep(tics=garbage_delay_tics)
        garbage_frame = random.choice(space_garbage_frames)
        _, garbage_width = get_frame_size(garbage_frame)
        garbage_column = random.randint(canvas_border_indent, frame_columns - garbage_width - canvas_border_indent)
        coroutines.append(fly_garbage(canvas, garbage_column, garbage_frame, speed=0.5))


async def change_year():
    global year
    while True:
        await sleep(tics=15)
        year += 1


async def show_year(canvas, bottom_border, right_border):
    right_indent = 52
    bottom_indent = 2
    while True:
        await asyncio.sleep(0)
        draw_frame(canvas, bottom_border - bottom_indent, right_border - right_indent, f'Year {year}.')


async def add_space_event(canvas, bottom_border, right_border):
    right_indent = 41
    bottom_indent = 2
    text = ''
    while True:
        await asyncio.sleep(0)
        if year in PHRASES:
            text = PHRASES[year]
            draw_frame(canvas, bottom_border - bottom_indent, right_border - right_indent, text)
        else:
            draw_frame(canvas, bottom_border - bottom_indent, right_border - right_indent, text, negative=True)


def draw(canvas):
    rocket_frames_path = os.path.join('animations_frames', 'rocket')
    space_garbage_path = os.path.join('animations_frames', 'space_debris')
    rocket_frames = get_animations_frames(rocket_frames_path)
    space_garbage_frames = get_animations_frames(space_garbage_path)

    canvas.border()
    curses.curs_set(False)
    canvas.nodelay(True)
    bottom_border, right_border = curses.window.getmaxyx(canvas)

    stars_symbols = ['+', '*', '.', ':']
    canvas_border_indent = 1
    stars_count = 50

    for _ in range(stars_count):
        row = random.choice(range(canvas_border_indent, bottom_border - canvas_border_indent))
        column = random.choice(range(canvas_border_indent, right_border - canvas_border_indent))
        symbol = random.choice(stars_symbols)
        offset_tics = random.randint(0, 10)
        coroutines.append(blink(canvas, row, column, symbol=symbol, offset_tics=offset_tics))

    _, rocket_width = get_frame_size(rocket_frames[0])
    rocket_row = right_border / 2 - int(rocket_width / 2)
    rocket_column = bottom_border / 2
    coroutines.append(animate_spaceship(canvas, rocket_frames, rocket_column, rocket_row, canvas_border_indent))
    coroutines.append(fill_orbit_with_garbage(canvas, space_garbage_frames, canvas_border_indent))
    coroutines.append(show_year(canvas, bottom_border, right_border))
    coroutines.append(change_year())
    coroutines.append(add_space_event(canvas, bottom_border, right_border))

    while True:

        for coroutine in coroutines.copy():
            try:
                coroutine.send(None)
            except StopIteration:
                coroutines.remove(coroutine)

        canvas.refresh()
        time.sleep(0.1)


def main():
    curses.update_lines_cols()
    curses.wrapper(draw)


if __name__ == '__main__':
    main()
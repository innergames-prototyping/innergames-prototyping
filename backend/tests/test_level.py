import json
import math

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.extraction.images import level, text_tilt, trim
from app.extraction.layout import crop_items
from app.extraction.workspace import Workspace


def text_card(size=(420, 300)) -> Image.Image:
    """A white card with a coloured band and lines of printed text."""
    card = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(card)
    draw.rectangle([0, 0, size[0], 40], fill=(40, 90, 160))
    font = ImageFont.load_default(size=20)
    for n, line in enumerate(["Draw two cards now", "Pay three gold coins", "Move your pawn on"]):
        draw.text((30, 70 + n * 60), line, fill="black", font=font)
    return card


def tilted(card: Image.Image, degrees: float) -> Image.Image:
    return card.rotate(degrees, expand=True, resample=Image.Resampling.BICUBIC, fillcolor="white")


@pytest.mark.parametrize("degrees", [-40, -17, -3, 3, 12, 25, 40])
def test_text_tilt_measures_the_angle(degrees):
    assert text_tilt(tilted(text_card(), degrees)) == pytest.approx(degrees, abs=1)


@pytest.mark.parametrize("degrees", [-25, 8, 33])
def test_level_turns_the_text_back(degrees):
    levelled, tilt = level(tilted(text_card(), degrees))

    assert tilt == pytest.approx(degrees, abs=1)
    assert abs(text_tilt(levelled)) <= 1


def test_a_straight_crop_comes_back_as_the_same_image():
    card = text_card()

    levelled, tilt = level(card)

    assert tilt == 0.0
    assert levelled is card


def test_a_blank_crop_is_left_alone():
    blank = Image.new("RGB", (200, 200), "white")
    assert level(blank) == (blank, 0.0)


def ring_board(labels: int, size=900) -> Image.Image:
    """Labels printed round a ring, each running along its own radius."""
    board = Image.new("RGB", (size, size), "white")
    font = ImageFont.load_default(size=22)
    for n in range(labels):
        angle = 360 * n / labels
        label = Image.new("RGB", (190, 36), "white")
        ImageDraw.Draw(label).text((4, 4), f"Space number {n}", fill="black", font=font)
        turned = tilted(label, -angle - 90)
        x = size / 2 + 340 * math.cos(math.radians(angle)) - turned.width / 2
        y = size / 2 + 340 * math.sin(math.radians(angle)) - turned.height / 2
        board.paste(turned, (int(x), int(y)))
    return board


@pytest.mark.parametrize("labels", [8, 12, 24])
def test_text_round_a_ring_is_left_alone(labels):
    board = ring_board(labels)
    assert level(board) == (board, 0.0)


def test_crop_levels_a_tilted_item_and_records_the_angle(ws: Workspace):
    page = Image.new("RGB", (900, 700), "white")
    page.paste(tilted(text_card(), 20), (120, 80))
    path = ws.page_image("board", 1)
    path.parent.mkdir(parents=True)
    page.save(path)
    ws.update_config(
        {"layouts": [{"file": "board.pdf", "page": 1, "method": "boxes", "boxes": [[0, 0, 1, 1]]}]}
    )

    crop_items(ws)

    item = json.loads((ws.work / "items.json").read_text())[0]
    assert item["level"] == pytest.approx(20, abs=1)
    front = Image.open(ws.item_dir(item["key"]) / "front.png")
    assert abs(text_tilt(front)) <= 1


def test_crop_keeps_a_straight_item_byte_identical(ws: Workspace):
    page = Image.new("RGB", (900, 700), "white")
    card = text_card()
    page.paste(card, (120, 80))
    path = ws.page_image("board", 1)
    path.parent.mkdir(parents=True)
    page.save(path)
    box = [120, 80, 120 + card.width, 80 + card.height]
    ws.update_config(
        {"layouts": [{"file": "board.pdf", "page": 1, "method": "boxes", "boxes": [box]}]}
    )

    crop_items(ws)

    item = json.loads((ws.work / "items.json").read_text())[0]
    assert item["level"] == 0.0
    front = Image.open(ws.item_dir(item["key"]) / "front.png").convert("RGB")
    assert front.tobytes() == trim(page.crop(tuple(box))).tobytes()


def test_crop_files_levels_fronts_and_backs(ws: Workspace):
    tilted(text_card(), 15).save(ws.input / "card_a_front.png")
    tilted(text_card(), -10).save(ws.input / "card_a_back.png")
    ws.update_config(
        {"layouts": [{"method": "files", "fronts": "card_*_front.png", "backs": "card_*_back.png"}]}
    )

    crop_items(ws)

    item = json.loads((ws.work / "items.json").read_text())[0]
    assert item["level"] == pytest.approx(15, abs=1)
    back = Image.open(ws.item_dir(item["key"]) / "back.png")
    assert abs(text_tilt(back)) <= 1

"""videotools.sheet: a frame scaled into a cell above its label strip, and the sheets' names."""

from videotools import sheet


def test_a_frame_fits_the_cell_above_the_label_strip_keeping_its_proportions():
    assert sheet.frame_size((400, 236)) == (355, 199)              # the height binds: 236 - 36 = 200 tall at most
    assert sheet.frame_size((360, 677), (480, 854)) == (360, 640)  # the width binds: a vertical frame 360 wide


def test_one_sheet_keeps_its_name_and_several_are_numbered():
    assert sheet.names("out/s.png", 1) == ["out/s.png"]
    assert sheet.names("out/s.png", 3) == ["out/s-1.png", "out/s-2.png", "out/s-3.png"]

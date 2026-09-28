from src.transform import div
def test_div():
    assert div(10,2)==5
    assert div(1,0) is None

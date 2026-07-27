from pi.collect.logger import CsvLogger

HEADER = "timestamp_ms,ax,ay,az,gx,gy,gz,wheel_pulse"


def _sample(t, base=0):
    return {"t_ms": t, "ax": base + 1, "ay": base + 2, "az": base + 3,
            "gx": base + 4, "gy": base + 5, "gz": base + 6, "wheel_pulse": base + 7}


def test_open_creates_file_with_header(tmp_path):
    logger = CsvLogger(out_dir=tmp_path)
    logger.open("gravel")
    logger.close()
    files = list(tmp_path.glob("run_gravel_*.csv"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8").splitlines()[0] == HEADER


def test_write_appends_rows_in_schema_order(tmp_path):
    logger = CsvLogger(out_dir=tmp_path)
    logger.open("asphalt")
    logger.write(_sample(100, base=0))
    logger.write(_sample(105, base=10))
    logger.close()
    lines = list(tmp_path.glob("run_asphalt_*.csv"))[0].read_text(encoding="utf-8").splitlines()
    assert lines[0] == HEADER
    assert lines[1] == "100,1,2,3,4,5,6,7"
    assert lines[2] == "105,11,12,13,14,15,16,17"
    assert len(lines) == 3


def test_empty_label_falls_back_to_unlabeled(tmp_path):
    logger = CsvLogger(out_dir=tmp_path)
    logger.open("")
    logger.close()
    assert len(list(tmp_path.glob("run_unlabeled_*.csv"))) == 1

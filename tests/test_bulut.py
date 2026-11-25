"""Bulut köprüsü: manifest ve fark hesabı (ağ yok)."""

from src import bulut


def test_farklar():
    kaynak = {"fiyat/A.parquet": "1", "fiyat/B.parquet": "2", "model/t.parquet": "3"}
    hedef = {"fiyat/A.parquet": "1", "fiyat/B.parquet": "eski", "fiyat/SILINEN.parquet": "9"}
    aktar, sil = bulut.farklar(kaynak, hedef)
    assert aktar == ["fiyat/B.parquet", "model/t.parquet"]
    assert sil == ["fiyat/SILINEN.parquet"]


def test_yerel_manifest_sadece_izinli_klasorler(tmp_path):
    (tmp_path / "fiyat").mkdir()
    (tmp_path / "fiyat" / "A.parquet").write_bytes(b"abc")
    (tmp_path / "ham").mkdir()
    (tmp_path / "ham" / "gizli.parquet").write_bytes(b"x")       # buluta gitmemeli
    (tmp_path / "uygulama.db").write_bytes(b"x")                  # buluta gitmemeli
    m = bulut.yerel_manifest(tmp_path)
    assert list(m) == ["fiyat/A.parquet"]
    assert m["fiyat/A.parquet"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

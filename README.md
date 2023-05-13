# Inverted File Index Module

Bagian dari arsitektur mesin pencari [Telusuri](https://github.com/lazuardyk/search-engine).
Implementasi lengkap dapat dilihat dari [_fork_ proyek](https://github.com/etrnal70/search-engine/tree/inverted).

Implementasi struktur _inverted index_ sebagai modul _indexer_ untuk mesin
pencari _Telusuri_.

Terdapat opsi untuk menggunakan integrasi dengan struktur _Generalized Suffix
Tree_ untuk mendapatkan peningkatan performa yang signifikan dengan kekurangan
pada penggunaan memori dua kali lipat lebih banyak. (Digunakan secara _default_)

## Development Tools

Sebagai bagian dari dokumentasi (sekaligus mempermudah penulis dalam penulisan
kode program), seluruh kode akan dituliskan dengan _type annotation_ yang sudah
tersedia pada modul `typing`. Pengecekan penggunaan tipe data yang tepat
dilakukan dengan [mypy](https://github.com/python/mypy), sementara untuk
pengecekan penulisan kode secara general dilakukan dengan [ruff](https://github.com/charliermarsh/ruff).

Untuk instalasi _development tools_ dapat digunakan perintah berikut

```bash
pip install -r requirements/dev.txt
```

Apabila terdapat pesan error tentang `*missing type stub*`, perintah berikut
dapat digunakan untuk mengunduh _type annotation_ untuk library yang sesuai

```bash
mypy --install--types
```

# Naskah Skripsi LaTeX

<details>
<summary>Template Information</summary>

Template Naskah Skripsi dengan typesetting LaTeX untuk JTETI Universitas Gadjah Mada. Template ini merupakan hasil modifikasi dari versi pak Pekik Nurwantoro (FMIPA UGM) dan mas Yohan (JTETI UGM 2008).

Diedit dan digunakan untuk keperluan SKRIPSI SARJANA ILMU KOMPUTER.

Diunggah oleh:  
Gregorius Andito Herjuno  
ILMU KOMPUTER 2013  
UNIVERSITAS NEGERI JAKARTA  
3145136218

Modifikasi lebih lanjut oleh:  
MOCHAMMAD HANIF RAMADHAN  
ILMU KOMPUTER 2019  
UNIVERSITAS NEGERI JAKARTA

</details>

## Pembuatan Dokumen

Pembuatan dokumen dapat dilakukan dengan menggunakan [tectonic](https://github.com/tectonic-typesetting/tectonic) yang lebih modern
ketimbang melakukan instalasi `TeXLive` yang memakan _storage_ cukup besar. Referensi
instalasi `tectonic` dapat dilihat pada link diatas.

Pada template ini, digunakan package `biber` untuk mengelola daftar pustaka. Pada
sistem operasi Linux, `biber` bisa didapatkan pada _repository_ distribusi masing-masing
dengan mudah. Sementara untuk Windows dan macOS, untuk menghindari instalasi `perl`
yang cukup merepotkan, dapat mengunduh file `executable binary` yang tersedia di
[Sourceforge](https://sourceforge.net/projects/biblatex-biber/files/).

Karena `tectonic` tidak dapat mendeteksi _LaTeX magic comments_ (yang menunjukkan _root_ dokumen),
maka hanya ada satu perintah yang dapat digunakan untuk pembuatan file PDF.

```bash
tectonic template-skripsi.tex
```

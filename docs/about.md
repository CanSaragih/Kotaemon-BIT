# About Kotaemon

SIPADU (Sistem manajemen data dan metadata terpusat, terstruktur dan terdokumentasi ) adalah sebuah alat sumber terbuka untuk berinteraksi dengan dokumen Anda. Dibangun dengan mempertimbangkan pengguna akhir dan pengembang.

[Source Code](https://github.com/Cinnamon/kotaemon) |
[HF Space](https://huggingface.co/spaces/cin-model/kotaemon-demo)

[Installation Guide](https://github.com/Cinnamon/kotaemon/blob/main/docs/installation.md) |
[Developer Guide](https://github.com/Cinnamon/kotaemon/blob/main/docs/development.md) |
[Feedback](https://github.com/Cinnamon/kotaemon/issues)

## Tentang SIPADU

SIPADU (Sistem manajemen data dan metadata terpusat, terstruktur dan terdokumentasi ) adalah sebuah alat sumber terbuka untuk berinteraksi dengan dokumen Anda. Dibangun dengan mempertimbangkan pengguna akhir dan pengembang.

[Kode Sumber](https://github.com/Cinnamon/kotaemon) | [Ruang HF](https://huggingface.co/spaces/cin-model/kotaemon-demo)

[Panduan Instalasi](https://github.com/Cinnamon/kotaemon/blob/main/docs/installation.md) | [Panduan Pengembang](https://github.com/Cinnamon/kotaemon/blob/main/docs/development.md) | [Umpan Balik](https://github.com/Cinnamon/kotaemon/issues)

## Panduan Pengguna

### 1. Tambahkan model AI Anda

![tab sumber daya](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/resources-tab.png)

- Alat ini menggunakan Model Bahasa Besar (LLM) untuk melakukan berbagai tugas dalam pipeline QA. Jadi, Anda perlu menyediakan aplikasi dengan akses ke LLM yang ingin Anda gunakan.
- Disarankan untuk menyertakan semua LLM yang Anda miliki akses, sehingga Anda dapat beralih di antara mereka saat menggunakan aplikasi.

Untuk menambahkan model:

1. Navigasi ke tab `Sumber Daya`.
2. Pilih sub-tab `LLMs`.
3. Pilih sub-tab `Tambah`.
4. Konfigurasi model yang akan ditambahkan:
   - Beri nama model
   - Pilih vendor/penyedia (misalnya `ChatOpenAI`)
   - Berikan spesifikasi yang diperlukan
   - (Opsional) Tetapkan model sebagai default
5. Klik `Tambah` untuk menambahkan model.
6. Pilih sub-tab `Model Embedding` dan ulangi langkah untuk menambahkan model embedding.

Spesifikasi yang diperlukan berbeda-beda tergantung penyedia LLM. Beberapa memerlukan:

- **Kunci API**: untuk autentikasi
- **URL Endpoint**: untuk model yang di-host sendiri
- **Nama Model**: identifier model spesifik
- **Parameter**: seperti temperature, max tokens, dll.

Selalu lindungi kunci API Anda dan jangan bagikan dengan orang lain.

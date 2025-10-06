# Penggunaan Dasar

## 1. Tambahkan model AI Anda

![tab sumber daya](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/resources-tab.png)

- Alat ini menggunakan Model Bahasa Besar (LLM) untuk melakukan berbagai tugas dalam pipeline QA.
  Jadi, Anda perlu menyediakan aplikasi dengan akses ke LLM yang ingin Anda gunakan.
- Anda hanya perlu menyediakan setidaknya satu. Namun, disarankan agar Anda menyertakan semua LLM
  yang Anda miliki akses, Anda akan dapat beralih di antara mereka saat menggunakan aplikasi.

Untuk menambahkan model:

1. Navigasi ke tab `Sumber Daya`.
2. Pilih sub-tab `LLMs`.
3. Pilih sub-tab `Tambah`.
4. Konfigurasi model yang akan ditambahkan:
   - Beri nama.
   - Pilih vendor/penyedia (misalnya `ChatOpenAI`).
   - Berikan spesifikasi.
   - (Opsional) Tetapkan model sebagai default.
5. Klik `Tambah` untuk menambahkan model.
6. Pilih sub-tab `Model Embedding` dan ulangi langkah 3 hingga 5 untuk menambahkan model embedding.

<details markdown>

<summary>(Opsional) Konfigurasi model melalui file .env</summary>

Alternatif lain, Anda dapat mengkonfigurasi model melalui file `.env` dengan informasi yang diperlukan untuk terhubung ke LLM. File ini terletak di
folder aplikasi. Jika Anda tidak melihatnya, Anda dapat membuatnya.

Saat ini, penyedia berikut didukung:

### OpenAI

Dalam file `.env`, atur variabel `OPENAI_API_KEY` dengan kunci API OpenAI Anda untuk
mengaktifkan akses ke model OpenAI. Ada variabel lain yang dapat dimodifikasi,
silakan edit sesuai kebutuhan Anda. Jika tidak, parameter default seharusnya
berfungsi untuk kebanyakan orang.

```shell
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=<kunci API OpenAI Anda di sini>
OPENAI_CHAT_MODEL=gpt-3.5-turbo
OPENAI_EMBEDDINGS_MODEL=text-embedding-ada-002
```

### Azure OpenAI

Untuk model OpenAI melalui platform Azure, Anda perlu menyediakan endpoint Azure dan kunci API
Anda. Anda mungkin juga perlu menyediakan nama development untuk model chat dan
model embedding tergantung bagaimana Anda menyiapkan development Azure.

```shell
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-35-turbo
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-ada-002
```

### Model lokal

- Keuntungan:
- Privasi. Dokumen Anda akan disimpan dan diproses secara lokal.
- Pilihan. Ada berbagai macam LLM dari segi ukuran, domain, bahasa untuk dipilih.
- Biaya. Gratis.
- Kerugian:
- Kualitas. Model lokal jauh lebih kecil dan dengan demikian memiliki kualitas generatif yang lebih rendah dibandingkan
  API berbayar.
- Kecepatan. Model lokal digunakan menggunakan mesin Anda sehingga kecepatan pemrosesan
  dibatasi oleh perangkat keras Anda.

#### Cari dan unduh LLM

Anda dapat mencari dan mengunduh LLM untuk dijalankan secara lokal dari [Hugging Face
Hub](https://huggingface.co/models). Saat ini, format model berikut didukung:

- GGUF

Anda harus memilih model yang ukurannya kurang dari memori perangkat Anda dan harus meninggalkan
sekitar 2 GB. Misalnya, jika Anda memiliki 16 GB RAM secara total, di mana 12 GB tersedia,
maka Anda harus memilih model yang menggunakan paling banyak 10 GB RAM. Model yang lebih besar cenderung
memberikan generasi yang lebih baik tetapi juga membutuhkan waktu pemrosesan lebih lama.

Berikut beberapa rekomendasi dan ukurannya dalam memori:

- [Qwen1.5-1.8B-Chat-GGUF](https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q8_0.gguf?download=true):
  sekitar 2 GB

#### Aktifkan model lokal

Untuk menambahkan model lokal ke pool model, atur variabel `LOCAL_MODEL` dalam file `.env`
ke path file model.

```shell
LOCAL_MODEL=<path lengkap ke file model Anda>
```

Berikut cara mendapatkan path lengkap file model Anda:

- Di Windows 11: klik kanan file dan pilih `Copy as Path`.
</details>

## 2. Unggah dokumen Anda

![tab indeks file](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/file-index-tab.png)

Untuk melakukan QA pada dokumen Anda, Anda perlu mengunggahnya ke aplikasi terlebih dahulu.
Navigasi ke tab `Indeks File` dan Anda akan melihat 2 bagian:

1. Unggah file:
   - Seret dan lepas file Anda ke UI atau pilih dari sistem file Anda.
     Lalu klik `Unggah dan Indeks`.
   - Aplikasi akan membutuhkan waktu untuk memproses file dan menampilkan pesan setelah selesai.
2. Daftar file:
   - Bagian ini menampilkan daftar file yang telah diunggah ke aplikasi dan memungkinkan pengguna untuk menghapusnya.

## 3. Chat dengan dokumen Anda

![tab chat](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/docs/images/chat-tab.png)

Sekarang navigasi kembali ke tab `Chat`. Tab chat dibagi menjadi 3 wilayah:

1. Panel Pengaturan Percakapan
   - Di sini Anda dapat memilih, membuat, mengganti nama, dan menghapus percakapan.
     - Secara default, percakapan baru dibuat secara otomatis jika tidak ada percakapan yang dipilih.
   - Di bawahnya Anda memiliki indeks file, di mana Anda dapat memilih apakah akan menonaktifkan, memilih semua file, atau memilih file mana yang akan diambil referensinya.
     - Jika Anda memilih "Nonaktif", tidak ada file yang akan dipertimbangkan sebagai konteks selama chat.
     - Jika Anda memilih "Cari Semua", semua file akan dipertimbangkan selama chat.
     - Jika Anda memilih "Pilih", dropdown akan muncul untuk Anda pilih
       file yang akan dipertimbangkan selama chat. Jika tidak ada file yang dipilih, maka tidak ada
       file yang akan dipertimbangkan selama chat.
2. Panel Chat
   - Di sini Anda dapat mengobrol dengan chatbot.
3. Panel Informasi
   - Informasi pendukung seperti bukti dan referensi yang diperoleh akan
     ditampilkan di sini.
4. Information Panel
   - Supporting information such as the retrieved evidence and reference will be
     displayed here.

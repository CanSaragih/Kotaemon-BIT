from importlib.metadata import version
from pathlib import Path

import gradio as gr
import requests
from decouple import config
from theflow.settings import settings

KH_DEMO_MODE = getattr(settings, "KH_DEMO_MODE", False)
HF_SPACE_URL = config("HF_SPACE_URL", default="")


def get_remote_doc(url: str) -> str:
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"Failed to fetch document from {url}: {e}")
        return ""


def download_changelogs(release_url: str) -> str:
    try:
        res = requests.get(release_url).json()
        changelogs = res.get("body", "")

        return changelogs
    except Exception as e:
        print(f"Failed to fetch changelogs from {release_url}: {e}")
        return ""


class HelpPage:
    def __init__(
        self,
        app,
        doc_dir: str = settings.KH_DOC_DIR,
        remote_content_url: str = "https://raw.githubusercontent.com/Cinnamon/kotaemon",
        app_version: str | None = settings.KH_APP_VERSION,
        changelogs_cache_dir: str
        | Path = (Path(settings.KH_APP_DATA_DIR) / "changelogs"),
    ):
        self._app = app
        self.doc_dir = Path(doc_dir)
        self.remote_content_url = remote_content_url
        self.app_version = app_version
        self.changelogs_cache_dir = Path(changelogs_cache_dir)

        self.changelogs_cache_dir.mkdir(parents=True, exist_ok=True)

        about_md_dir = self.doc_dir / "about.md"
        if about_md_dir.exists():
            with (self.doc_dir / "about.md").open(encoding="utf-8") as fi:
                about_md = fi.read()
        else:  # fetch from remote
            about_md = get_remote_doc(
                f"{self.remote_content_url}/v{self.app_version}/docs/about.md"
            )
        if about_md:
            with gr.Accordion("Tentang SIPADU"):
                if self.app_version:
                    about_md = f"Versi: {self.app_version}\n\n{about_md}"
                # Translate the about content to Indonesian
                about_md_translated = about_md.replace(
                    "About Kotaemon", "Tentang SIPADU"
                ).replace(
                    "An open-source tool for chatting with your documents. Built with both end users and developers in mind.",
                    "Sebuah alat sumber terbuka untuk berinteraksi dengan dokumen Anda. Dibangun dengan mempertimbangkan pengguna akhir dan pengembang."
                ).replace(
                    "Source Code", "Kode Sumber"
                ).replace(
                    "HF Space", "Ruang HF"
                ).replace(
                    "Installation Guide", "Panduan Instalasi"
                ).replace(
                    "Developer Guide", "Panduan Pengembang"
                ).replace(
                    "Feedback", "Umpan Balik"
                ).replace(
                    "User Guide", "Panduan Pengguna"
                ).replace(
                    "Add your AI models", "Tambahkan model AI Anda"
                )
                gr.Markdown(about_md_translated)

        if KH_DEMO_MODE:
            with gr.Accordion("Buat Ruang Anda Sendiri"):
                gr.Markdown(
                    "Ini adalah demo dengan fungsionalitas terbatas. "
                    "Gunakan tombol **Buat ruang** untuk menginstal SIPADU "
                    "di ruang Anda sendiri dengan semua fitur "
                    "(termasuk mengunggah dan mengelola dokumen pribadi "
                    "Anda dengan aman)."
                )
                gr.Button(
                    value="Buat Ruang Anda Sendiri",
                    link=HF_SPACE_URL,
                    variant="primary",
                    size="lg",
                )

        user_guide_md_dir = self.doc_dir / "usage.md"
        if user_guide_md_dir.exists():
            with (self.doc_dir / "usage.md").open(encoding="utf-8") as fi:
                user_guide_md = fi.read()
        else:  # fetch from remote
            user_guide_md = get_remote_doc(
                f"{self.remote_content_url}/v{self.app_version}/docs/usage.md"
            )
        if user_guide_md:
            with gr.Accordion("Panduan Pengguna", open=not KH_DEMO_MODE):
                # Translate user guide content to Indonesian
                user_guide_md_translated = user_guide_md.replace(
                    "Basic Usage", "Penggunaan Dasar"
                ).replace(
                    "Add your AI models", "Tambahkan model AI Anda"
                ).replace(
                    "Upload your documents", "Unggah dokumen Anda"
                ).replace(
                    "Chat with your documents", "Chat dengan dokumen Anda"
                ).replace(
                    "file index tab", "tab indeks file"
                ).replace(
                    "chat tab", "tab chat"
                ).replace(
                    "Resources tab", "tab Konfigurasi AI"
                ).replace(
                    "File Index tab", "tab Indeks File"
                ).replace(
                    "Chat tab", "tab Chat"
                ).replace(
                    "The tool uses Large Language Model", "Alat ini menggunakan Model Bahasa Besar"
                ).replace(
                    "In order to do QA on your documents, you need to upload them to the application first.",
                    "Untuk melakukan tanya jawab pada dokumen Anda, Anda perlu mengunggahnya ke aplikasi terlebih dahulu."
                ).replace(
                    "Navigate to the", "Navigasi ke"
                ).replace(
                    "File upload:", "Unggah file:"
                ).replace(
                    "File list:", "Daftar file:"
                ).replace(
                    "Drag and drop your file to the UI or select it from your file system.",
                    "Seret dan lepas file Anda ke UI atau pilih dari sistem file Anda."
                ).replace(
                    "Then click", "Lalu klik"
                ).replace(
                    "Upload and Index", "Unggah dan Indeks"
                ).replace(
                    "The application will take some time to process the file and show a message once it is done.",
                    "Aplikasi akan membutuhkan waktu untuk memproses file dan menampilkan pesan setelah selesai."
                ).replace(
                    "This section shows the list of files that have been uploaded to the application and allows users to delete them.",
                    "Bagian ini menampilkan daftar file yang telah diunggah ke aplikasi dan memungkinkan pengguna untuk menghapusnya."
                ).replace(
                    "Now navigate back to the", "Sekarang navigasi kembali ke"
                ).replace(
                    "The chat tab is divided into 3 regions:", "Tab chat dibagi menjadi 3 wilayah:"
                ).replace(
                    "Conversation Settings Panel", "Panel Pengaturan Percakapan"
                ).replace(
                    "Chat Panel", "Panel Chat"
                ).replace(
                    "Information Panel", "Panel Informasi"
                ).replace(
                    "Here you can select, create, rename, and delete conversations.",
                    "Di sini Anda dapat memilih, membuat, mengganti nama, dan menghapus percakapan."
                ).replace(
                    "By default, a new conversation is created automatically if no conversation is selected.",
                    "Secara default, percakapan baru dibuat secara otomatis jika tidak ada percakapan yang dipilih."
                ).replace(
                    "Below that you have the file index, where you can choose whether to disable, select all files, or select which files to retrieve references from.",
                    "Di bawahnya Anda memiliki indeks file, di mana Anda dapat memilih apakah akan menonaktifkan, memilih semua file, atau memilih file mana yang akan diambil referensinya."
                ).replace(
                    "This is where you can chat with the chatbot.", 
                    "Di sini Anda dapat mengobrol dengan chatbot."
                ).replace(
                    "Supporting information such as the retrieved evidence and reference will be displayed here.",
                    "Informasi pendukung seperti bukti dan referensi yang diperoleh akan ditampilkan di sini."
                )
                gr.Markdown(user_guide_md_translated)

        if self.app_version:
            # try retrieve from cache
            changelogs = ""

            if (self.changelogs_cache_dir / f"{self.app_version}.md").exists():
                with open(self.changelogs_cache_dir / f"{self.app_version}.md", "r") as fi:
                    changelogs = fi.read()
            else:
                release_url_base = (
                    "https://api.github.com/repos/Cinnamon/kotaemon/releases"
                )
                changelogs = download_changelogs(
                    release_url=f"{release_url_base}/tags/v{self.app_version}"
                )

                # cache the changelogs
                if not self.changelogs_cache_dir.exists():
                    self.changelogs_cache_dir.mkdir(parents=True, exist_ok=True)
                with open(
                    self.changelogs_cache_dir / f"{self.app_version}.md", "w"
                ) as fi:
                    fi.write(changelogs)

            if changelogs:
                with gr.Accordion(f"Log Perubahan (v{self.app_version})"):
                    gr.Markdown(changelogs)

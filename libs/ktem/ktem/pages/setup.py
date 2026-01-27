import json

import gradio as gr
import requests
from decouple import config
from ktem.app import BasePage
from ktem.embeddings.manager import embedding_models_manager as embeddings
from ktem.llms.manager import llms
from ktem.rerankings.manager import reranking_models_manager as rerankers
from theflow.settings import settings as flowsettings

KH_OLLAMA_URL = getattr(flowsettings, "KH_OLLAMA_URL", "http://localhost:11434/v1/")
DEFAULT_OLLAMA_URL = KH_OLLAMA_URL.replace("v1", "api")
if DEFAULT_OLLAMA_URL.endswith("/"):
    DEFAULT_OLLAMA_URL = DEFAULT_OLLAMA_URL[:-1]


DEMO_MESSAGE = (
    "Ini adalah ruang publik. Silakan gunakan "
    'fungsi "Duplicate Space" di pojok kanan atas '
    "untuk mengatur ruang Anda sendiri."
)


def pull_model(name: str, stream: bool = True):
    payload = {"name": name}
    headers = {"Content-Type": "application/json"}

    response = requests.post(
        DEFAULT_OLLAMA_URL + "/pull", json=payload, headers=headers, stream=stream
    )

    # Check if the request was successful
    response.raise_for_status()

    if stream:
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                yield data
                if data.get("status") == "success":
                    break
    else:
        data = response.json()

    return data


class SetupPage(BasePage):

    public_events = ["onFirstSetupComplete"]

    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        gr.Markdown(f"# Selamat datang di pengaturan awal SIPADU!")
        self.radio_model = gr.Radio(
            [
                ("Cohere API (*registrasi gratis*) - direkomendasikan", "cohere"),
                ("Google API (*registrasi gratis*)", "google"),
                ("OpenAI API (untuk model berbasis GPT)", "openai"),
                ("LLM Lokal (untuk RAG yang *sepenuhnya pribadi*)", "ollama"),
            ],
            label="Pilih penyedia model Anda",
            value="cohere",
            info=(
                "Catatan: Anda dapat mengubah ini nanti. "
                "Jika Anda tidak yakin, pilih opsi pertama "
                "yang cocok untuk sebagian besar pengguna normal."
            ),
            interactive=True,
        )

        with gr.Column(visible=False) as self.openai_option:
            gr.Markdown(
                (
                    "#### Kunci API OpenAI\n\n"
                    "(buat di https://platform.openai.com/api-keys)"
                )
            )
            self.openai_api_key = gr.Textbox(
                show_label=False, placeholder="Kunci API OpenAI"
            )

        with gr.Column(visible=True) as self.cohere_option:
            gr.Markdown(
                (
                    "#### Kunci API Cohere\n\n"
                    "(daftarkan kunci API gratis Anda "
                    "di https://dashboard.cohere.com/api-keys)"
                )
            )
            self.cohere_api_key = gr.Textbox(
                show_label=False, placeholder="Kunci API Cohere"
            )

        with gr.Column(visible=False) as self.google_option:
            gr.Markdown(
                (
                    "#### Kunci API Google\n\n"
                    "(daftarkan kunci API gratis Anda "
                    "di https://aistudio.google.com/app/apikey)"
                )
            )
            self.google_api_key = gr.Textbox(
                show_label=False, placeholder="Kunci API Google"
            )

        with gr.Column(visible=False) as self.ollama_option:
            gr.Markdown(
                (
                    "#### Pengaturan Ollama\n\n"
                    "Unduh dan instal Ollama dari "
                    "https://ollama.com/. Lihat model terbaru di "
                    "https://ollama.com/library. "
                )
            )
            self.ollama_model_name = gr.Textbox(
                label="Nama model LLM",
                value=config("LOCAL_MODEL", default="qwen2.5:7b"),
            )
            self.ollama_emb_model_name = gr.Textbox(
                label="Nama model embedding",
                value=config("LOCAL_MODEL_EMBEDDINGS", default="nomic-embed-text"),
            )

        self.setup_log = gr.HTML(
            show_label=False,
        )

        with gr.Row():
            self.btn_finish = gr.Button("Lanjutkan", variant="primary")
            self.btn_skip = gr.Button(
                "Saya pengguna tingkat lanjut. Lewati ini.", variant="stop"
            )

    def on_register_events(self):
        onFirstSetupComplete = gr.on(
            triggers=[
                self.btn_finish.click,
                self.cohere_api_key.submit,
                self.openai_api_key.submit,
            ],
            fn=self.update_model,
            inputs=[
                self.cohere_api_key,
                self.openai_api_key,
                self.google_api_key,
                self.ollama_model_name,
                self.ollama_emb_model_name,
                self.radio_model,
            ],
            outputs=[self.setup_log],
            show_progress="hidden",
        )
        onSkipSetup = gr.on(
            triggers=[self.btn_skip.click],
            fn=lambda: None,
            inputs=[],
            show_progress="hidden",
            outputs=[self.radio_model],
        )

        for event in self._app.get_event("onFirstSetupComplete"):
            onSkipSetup = onSkipSetup.success(**event)

        onFirstSetupComplete = onFirstSetupComplete.success(
            fn=self.update_default_settings,
            inputs=[self.radio_model, self._app.settings_state],
            outputs=self._app.settings_state,
        )
        for event in self._app.get_event("onFirstSetupComplete"):
            onFirstSetupComplete = onFirstSetupComplete.success(**event)

        self.radio_model.change(
            fn=self.switch_options_view,
            inputs=[self.radio_model],
            show_progress="hidden",
            outputs=[
                self.cohere_option,
                self.openai_option,
                self.ollama_option,
                self.google_option,
            ],
        )

    def update_model(
        self,
        cohere_api_key,
        openai_api_key,
        google_api_key,
        ollama_model_name,
        ollama_emb_model_name,
        radio_model_value,
    ):
        log_content = ""
        if not radio_model_value:
            gr.Info("Lewati pengaturan model.")
            yield gr.value(visible=False)
            return

        if radio_model_value == "cohere":
            if cohere_api_key:
                llms.update(
                    name="cohere",
                    spec={
                        "__type__": "kotaemon.llms.chats.LCCohereChat",
                        "model_name": "command-r-plus-08-2024",
                        "api_key": cohere_api_key,
                    },
                    default=True,
                )
                embeddings.update(
                    name="cohere",
                    spec={
                        "__type__": "kotaemon.embeddings.LCCohereEmbeddings",
                        "model": "embed-multilingual-v3.0",
                        "cohere_api_key": cohere_api_key,
                        "user_agent": "default",
                    },
                    default=True,
                )
                rerankers.update(
                    name="cohere",
                    spec={
                        "__type__": "kotaemon.rerankings.CohereReranking",
                        "model_name": "rerank-multilingual-v2.0",
                        "cohere_api_key": cohere_api_key,
                    },
                    default=True,
                )
        elif radio_model_value == "openai":
            if openai_api_key:
                llms.update(
                    name="openai",
                    spec={
                        "__type__": "kotaemon.llms.ChatOpenAI",
                        "base_url": "https://api.openai.com/v1",
                        "model": "gpt-4o",
                        "api_key": openai_api_key,
                        "timeout": 20,
                    },
                    default=True,
                )
                embeddings.update(
                    name="openai",
                    spec={
                        "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                        "base_url": "https://api.openai.com/v1",
                        "model": "text-embedding-3-large",
                        "api_key": openai_api_key,
                        "timeout": 10,
                        "context_length": 8191,
                    },
                    default=True,
                )
        elif radio_model_value == "google":
            if google_api_key:
                llms.update(
                    name="google",
                    spec={
                        "__type__": "kotaemon.llms.chats.LCGeminiChat",
                        "model_name": "gemini-1.5-flash",
                        "api_key": google_api_key,
                    },
                    default=True,
                )
                embeddings.update(
                    name="google",
                    spec={
                        "__type__": "kotaemon.embeddings.LCGoogleEmbeddings",
                        "model": "models/text-embedding-004",
                        "google_api_key": google_api_key,
                    },
                    default=True,
                )
        elif radio_model_value == "ollama":
            llms.update(
                name="ollama",
                spec={
                    "__type__": "kotaemon.llms.ChatOpenAI",
                    "base_url": KH_OLLAMA_URL,
                    "model": ollama_model_name,
                    "api_key": "ollama",
                },
                default=True,
            )
            embeddings.update(
                name="ollama",
                spec={
                    "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                    "base_url": KH_OLLAMA_URL,
                    "model": ollama_emb_model_name,
                    "api_key": "ollama",
                },
                default=True,
            )

            # download required models through ollama
            llm_model_name = llms.get("ollama").model  # type: ignore
            emb_model_name = embeddings.get("ollama").model  # type: ignore

            try:
                for model_name in [emb_model_name, llm_model_name]:
                    log_content += f"- Mengunduh model `{model_name}` dari Ollama<br>"
                    yield log_content

                    pre_download_log = log_content

                    for response in pull_model(model_name):
                        complete = response.get("completed", 0)
                        total = response.get("total", 0)
                        if complete > 0 and total > 0:
                            ratio = int(complete / total * 100)
                            log_content = (
                                pre_download_log
                                + f"- {response.get('status')}: {ratio}%<br>"
                            )
                        else:
                            if "pulling" not in response.get("status", ""):
                                log_content += f"- {response.get('status')}<br>"

                        yield log_content
            except Exception as e:
                log_content += (
                    "Pastikan Anda telah mengunduh dan menginstal Ollama dengan benar. "
                    f"Terjadi kesalahan: {str(e)}"
                )
                yield log_content
                raise gr.Error("Gagal mengunduh model dari Ollama.")

        # test models connection
        llm_output = emb_output = None

        # LLM model
        log_content += f"- Menguji model LLM: {radio_model_value}<br>"
        yield log_content

        llm = llms.get(radio_model_value)
        log_content += "- Mengirim pesan `Halo`<br>"
        yield log_content
        try:
            llm_output = llm("Halo")
        except Exception as e:
            log_content += (
                f"<mark style='color: yellow; background: red'>- Koneksi gagal. "
                f"Terjadi kesalahan:\n {str(e)}</mark>"
            )

        if llm_output:
            log_content += (
                "<mark style='background: green; color: white'>- Koneksi berhasil. "
                "</mark><br>"
            )
        yield log_content

        if llm_output:
            # embedding model
            log_content += f"- Menguji model Embedding: {radio_model_value}<br>"
            yield log_content

            emb = embeddings.get(radio_model_value)
            assert emb, f"Model embedding {radio_model_value} tidak ditemukan."

            log_content += "- Mengirim pesan `Halo`<br>"
            yield log_content
            try:
                emb_output = emb("Halo")
            except Exception as e:
                log_content += (
                    f"<mark style='color: yellow; background: red'>"
                    "- Koneksi gagal. "
                    f"Terjadi kesalahan:\n {str(e)}</mark>"
                )

            if emb_output:
                log_content += (
                    "<mark style='background: green; color: white'>"
                    "- Koneksi berhasil. "
                    "</mark><br>"
                )
            yield log_content

        if llm_output and emb_output:
            gr.Info("Pengaturan model berhasil diselesaikan!")
        else:
            raise gr.Error(
                "Pengaturan model gagal. Silakan verifikasi koneksi dan kunci API Anda."
            )

    def update_default_settings(self, radio_model_value, default_settings):
        # revise default settings
        # reranking llm
        default_settings["index.options.1.reranking_llm"] = radio_model_value
        if radio_model_value == "ollama":
            default_settings["index.options.1.use_llm_reranking"] = False

        return default_settings

    def switch_options_view(self, radio_model_value):
        components_visible = [gr.update(visible=False) for _ in range(4)]

        values = ["cohere", "openai", "ollama", "google", None]
        assert radio_model_value in values, f"Invalid value {radio_model_value}"

        if radio_model_value is not None:
            idx = values.index(radio_model_value)
            components_visible[idx] = gr.update(visible=True)

        return components_visible

import os
from importlib.metadata import version
from inspect import currentframe, getframeinfo
from pathlib import Path

from decouple import config
from ktem.utils.lang import SUPPORTED_LANGUAGE_MAP
from theflow.settings.default import *  # noqa

cur_frame = currentframe()
if cur_frame is None:
    raise ValueError("Cannot get the current frame.")
this_file = getframeinfo(cur_frame).filename
this_dir = Path(this_file).parent

# change this if your app use a different name
KH_PACKAGE_NAME = "kotaemon_app"

KH_APP_VERSION = config("KH_APP_VERSION", None)
if not KH_APP_VERSION:
    try:
        # Caution: This might produce the wrong version
        # https://stackoverflow.com/a/59533071
        KH_APP_VERSION = version(KH_PACKAGE_NAME)
    except Exception:
        KH_APP_VERSION = "local"

KH_GRADIO_SHARE = config("KH_GRADIO_SHARE", default=False, cast=bool)
KH_ENABLE_FIRST_SETUP = config("KH_ENABLE_FIRST_SETUP", default=True, cast=bool)
KH_DEMO_MODE = config("KH_DEMO_MODE", default=False, cast=bool)
KH_USE_LOW_LLM_REQUESTS = config("KH_USE_LOW_LLM_REQUESTS", default=True, cast=bool)
KH_OLLAMA_URL = config("KH_OLLAMA_URL", default="http://localhost:11434/v1/")

# App can be ran from anywhere and it's not trivial to decide where to store app data.
# So let's use the same directory as the flowsetting.py file.
KH_APP_DATA_DIR = this_dir / "ktem_app_data"
KH_APP_DATA_EXISTS = KH_APP_DATA_DIR.exists()
KH_APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# User data directory
KH_USER_DATA_DIR = KH_APP_DATA_DIR / "user_data"
KH_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# markdown output directory
KH_MARKDOWN_OUTPUT_DIR = KH_APP_DATA_DIR / "markdown_cache_dir"
KH_MARKDOWN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# chunks output directory
KH_CHUNKS_OUTPUT_DIR = KH_APP_DATA_DIR / "chunks_cache_dir"
KH_CHUNKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# zip output directory
KH_ZIP_OUTPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir"
KH_ZIP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# zip input directory
KH_ZIP_INPUT_DIR = KH_APP_DATA_DIR / "zip_cache_dir_in"
KH_ZIP_INPUT_DIR.mkdir(parents=True, exist_ok=True)

# HF models can be big, let's store them in the app data directory so that it's easier
# for users to manage their storage.
# ref: https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache
os.environ["HF_HOME"] = str(KH_APP_DATA_DIR / "huggingface")
os.environ["HF_HUB_CACHE"] = str(KH_APP_DATA_DIR / "huggingface")

# doc directory
KH_DOC_DIR = this_dir / "docs"

KH_MODE = "dev"
KH_SSO_ENABLED = config("KH_SSO_ENABLED", default=False, cast=bool)

KH_FEATURE_CHAT_SUGGESTION = config(
    "KH_FEATURE_CHAT_SUGGESTION", default=False, cast=bool
)
KH_FEATURE_USER_MANAGEMENT = config(
    "KH_FEATURE_USER_MANAGEMENT", default=True, cast=bool
)
KH_USER_CAN_SEE_PUBLIC = None
KH_FEATURE_USER_MANAGEMENT_ADMIN = str(
    config("KH_FEATURE_USER_MANAGEMENT_ADMIN", default="admin")
)
KH_FEATURE_USER_MANAGEMENT_PASSWORD = str(
    config("KH_FEATURE_USER_MANAGEMENT_PASSWORD", default="admin")
)
KH_ENABLE_ALEMBIC = False
KH_DATABASE = f"sqlite:///{KH_USER_DATA_DIR / 'sql.db'}"
KH_FILESTORAGE_PATH = str(KH_USER_DATA_DIR / "files")
KH_WEB_SEARCH_BACKEND = (
    "kotaemon.indices.retrievers.tavily_web_search.WebSearch"
    # "kotaemon.indices.retrievers.jina_web_search.WebSearch"
)

KH_DOCSTORE = {
    # "__type__": "kotaemon.storages.ElasticsearchDocumentStore",
    # "__type__": "kotaemon.storages.SimpleFileDocumentStore",
    "__type__": "kotaemon.storages.LanceDBDocumentStore",
    "path": str(KH_USER_DATA_DIR / "docstore"),
}
# KH_VECTORSTORE = {
# #     # "__type__": "kotaemon.storages.LanceDBVectorStore",
    # "__type__": "kotaemon.storages.ChromaVectorStore",
# #     # "__type__": "kotaemon.storages.MilvusVectorStore",
# #     # "__type__": "kotaemon.storages.QdrantVectorStore",
    # "path": str(KH_USER_DATA_DIR / "vectorstore"),
# }

SUPABASE_DB_URL = config(
    "SUPABASE_DB_URL", 
    default="postgresql://user:pass@host:5432/dbname"
)

KH_TABLE_CHUNK_SIZE = config("KH_TABLE_CHUNK_SIZE", default=4096, cast=int)
KH_TABLE_OVERLAP = config("KH_TABLE_OVERLAP", default=100, cast=int)

KH_VECTORSTORE = {
    "__type__": "kotaemon.storages.SupabaseVectorStore",  
    "connection_string": SUPABASE_DB_URL,
    "table_name": "vector_embeddings",
    "embedding_dim": 3072,
}

KH_LLMS = {}
KH_EMBEDDINGS = {}
KH_RERANKINGS = {}

# populate options from config
# if config("AZURE_OPENAI_API_KEY", default="") and config(
#     "AZURE_OPENAI_ENDPOINT", default=""
# ):
#     if config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""):
#         KH_LLMS["azure"] = {
#             "spec": {
#                 "__type__": "kotaemon.llms.AzureChatOpenAI",
#                 "temperature": 0,
#                 "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
#                 "api_key": config("AZURE_OPENAI_API_KEY", default=""),
#                 "api_version": config("OPENAI_API_VERSION", default="")
#                 or "2024-02-15-preview",
#                 "azure_deployment": config("AZURE_OPENAI_CHAT_DEPLOYMENT", default=""),
#                 "timeout": 20,
#             },
#             "default": False,
#         }
#     if config("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""):
#         KH_EMBEDDINGS["azure"] = {
#             "spec": {
#                 "__type__": "kotaemon.embeddings.AzureOpenAIEmbeddings",
#                 "azure_endpoint": config("AZURE_OPENAI_ENDPOINT", default=""),
#                 "api_key": config("AZURE_OPENAI_API_KEY", default=""),
#                 "api_version": config("OPENAI_API_VERSION", default="")
#                 or "2024-02-15-preview",
#                 "azure_deployment": config(
#                     "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", default=""
#                 ),
#                 "timeout": 10,
#             },
#             "default": False,
#         }

OPENAI_DEFAULT = "<YOUR_OPENAI_KEY>"
OPENAI_API_KEY = config("OPENAI_API_KEY", default=OPENAI_DEFAULT)
GOOGLE_API_KEY = config("GOOGLE_API_KEY", default="AIzaSyAioEI55BGFu1QgubdAbNoedrmPBHuYH7w")
IS_OPENAI_DEFAULT = True

if OPENAI_API_KEY:
    KH_LLMS["openai"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "temperature": 0,
            "base_url": config("OPENAI_API_BASE", default="")
            or "https://api.openai.comj/v1",
            "api_key": OPENAI_API_KEY,
            "model": config("OPENAI_CHAT_MODEL", default="gpt-4o-mini"),
            "timeout": 20,
        },
        "default": IS_OPENAI_DEFAULT,
    }
    KH_EMBEDDINGS["openai"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": config("OPENAI_API_BASE", default="https://api.openai.com/v1"),
            "api_key": OPENAI_API_KEY,
            "model": config(
                "OPENAI_EMBEDDINGS_MODEL", default="text-embedding-3-small"
            ),
            "timeout": 10,
            "context_length": 8191,
        },
        "default": IS_OPENAI_DEFAULT,
    }

# VOYAGE_API_KEY = config("VOYAGE_API_KEY", default="")
# if VOYAGE_API_KEY:
#     KH_EMBEDDINGS["voyageai"] = {
#         "spec": {
#             "__type__": "kotaemon.embeddings.VoyageAIEmbeddings",
#             "api_key": VOYAGE_API_KEY,
#             "model": config("VOYAGE_EMBEDDINGS_MODEL", default="voyage-3-large"),
#         },
#         "default": False,
#     }
#     KH_RERANKINGS["voyageai"] = {
#         "spec": {
#             "__type__": "kotaemon.rerankings.VoyageAIReranking",
#             "model_name": "rerank-2",
#             "api_key": VOYAGE_API_KEY,
#         },
#         "default": False,
#     }

# Local Model Configuration for RunPod endpoint
# Optimized for handling large datasets (30+ columns, 435+ rows)
LOCAL_MODEL = config("LOCAL_MODEL", default="openai/gpt-oss-20b")
LOCAL_MODEL_API_BASE = config("LOCAL_MODEL_API_BASE", default="")
LOCAL_MODEL_API_KEY = config("LOCAL_MODEL_API_KEY", default="")

if LOCAL_MODEL:
    KH_LLMS["GPT-OSS-20b"] = {
        "spec": {
            "__type__": "kotaemon.llms.ChatOpenAI",
            "temperature": 0.4,  # Consistent with OpenAI for deterministic outputs
            "base_url": LOCAL_MODEL_API_BASE or "https://tp9la25qwt7std-8000.proxy.runpod.net/v1",
            "model": LOCAL_MODEL,
            "api_key": LOCAL_MODEL_API_KEY or "",
            "timeout": 180,  # Increased from 60s to handle large context
            "max_tokens": 8192,  # Increased from 2048 for comprehensive responses
            "max_retries": 3,  # Retry logic for unstable RunPod connections
        },
        "default": False,
    }
    # KH_LLMS["ollama-long-context"] = {
    #     "spec": {
    #         "__type__": "kotaemon.llms.LCOllamaChat",
    #         "base_url": KH_OLLAMA_URL.replace("v1/", ""),
    #         "model": config("LOCAL_MODEL", default="qwen2.5:3b"),
    #         "num_ctx": 32768,
    #     },
    #     "default": False,
    # }

    KH_EMBEDDINGS["ollama"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
            "base_url": KH_OLLAMA_URL,
            "model": config("LOCAL_MODEL_EMBEDDINGS", default="nomic-embed-text"),
            "api_key": "ollama",
        },
        "default": False,
    }
    KH_EMBEDDINGS["fast_embed"] = {
        "spec": {
            "__type__": "kotaemon.embeddings.FastEmbedEmbeddings",
            "model_name": "BAAI/bge-base-en-v1.5",
        },
        "default": False,
    }

# HF_TOKEN = config("HF_TOKEN", default="")
# HF_MODEL = config("HF_MODEL", default="openai/gpt-oss-120b:novita")
# HF_EMBEDDING_MODEL = config("HF_EMBEDDING_MODEL", default="BAAI/bge-m3")

# if HF_TOKEN:
#     KH_LLMS["huggingface"] = {
#         "spec": {
#             "__type__": "kotaemon.llms.ChatOpenAI",
#             "base_url": "https://router.huggingface.co/v1",
#             "model": HF_MODEL,
#             "api_key": HF_TOKEN,
#             "timeout": 60,
#         },
#         "default": False,
#     }

# # additional LLM configurations
# KH_LLMS["claude"] = {
#     "spec": {
#         "__type__": "kotaemon.llms.chats.LCAnthropicChat",
#         "model_name": "claude-3-5-sonnet-20240620",
#         "api_key": "your-key",
#     },
#     "default": False,
# }
# KH_LLMS["google"] = {
#     "spec": {
#         "__type__": "kotaemon.llms.chats.LCGeminiChat",
#         "model_name": "gemini-2.0-flash",
#         "api_key": GOOGLE_API_KEY,
#     },
#     "default": not IS_OPENAI_DEFAULT,
# }
# KH_LLMS["groq"] = {
#     "spec": {
#         "__type__": "kotaemon.llms.ChatOpenAI",
#         "base_url": "https://api.groq.com/openai/v1",
#         "model": "llama-3.1-8b-instant",
#         "api_key": "your-key",
#     },
#     "default": False,
# }
# KH_LLMS["cohere"] = {
#     "spec": {
#         "__type__": "kotaemon.llms.chats.LCCohereChat",
#         "model_name": "command-r-plus-08-2024",
#         "api_key": config("COHERE_API_KEY", default="your-key"),
#     },
#     "default": False,
# }
# KH_LLMS["mistral"] = {
#     "spec": {
#         "__type__": "kotaemon.llms.ChatOpenAI",
#         "base_url": "https://api.mistral.ai/v1",
#         "model": "ministral-8b-latest",
#         "api_key": config("MISTRAL_API_KEY", default="your-key"),
#     },
#     "default": False,
# }

# additional embeddings configurations
KH_EMBEDDINGS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCCohereEmbeddings",
        "model": "embed-multilingual-v3.0",
        "cohere_api_key": config("COHERE_API_KEY", default="your-key"),
        "user_agent": "default",
    },
    "default": False,
}
KH_EMBEDDINGS["google"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCGoogleEmbeddings",
        "model": "models/text-embedding-004",
        "google_api_key": GOOGLE_API_KEY,
    },
    "default": not IS_OPENAI_DEFAULT,
}
KH_EMBEDDINGS["mistral"] = {
    "spec": {
        "__type__": "kotaemon.embeddings.LCMistralEmbeddings",
        "model": "mistral-embed",
        "api_key": config("MISTRAL_API_KEY", default="your-key"),
    },
    "default": False,
}


KH_RERANKINGS["cohere"] = {
    "spec": {
        "__type__": "kotaemon.rerankings.CohereReranking",
        "model_name": "rerank-multilingual-v2.0",
        "cohere_api_key": config("COHERE_API_KEY", default=""),
    },
    "default": True,
}

KH_REASONINGS = [
    "ktem.reasoning.simple.FullQAPipeline",
    "ktem.reasoning.simple.FullDecomposeQAPipeline",
    "ktem.reasoning.react.ReactAgentPipeline",
    "ktem.reasoning.rewoo.RewooAgentPipeline",
]
KH_REASONINGS_USE_MULTIMODAL = config("USE_MULTIMODAL", default=False, cast=bool)
KH_VLM_ENDPOINT = "{0}/openai/deployments/{1}/chat/completions?api-version={2}".format(
    config("AZURE_OPENAI_ENDPOINT", default=""),
    config("OPENAI_VISION_DEPLOYMENT_NAME", default="gpt-4o"),
    config("OPENAI_API_VERSION", default=""),
)


SETTINGS_APP: dict[str, dict] = {}


SETTINGS_REASONING = {
    "use": {
        "name": "Pilihan Penalaran",
        "value": None,
        "choices": [],
        "component": "radio",
    },
    "lang": {
        "name": "Bahasa",
        "value": "id",
        "choices": [(lang, code) for code, lang in SUPPORTED_LANGUAGE_MAP.items()],
        "component": "dropdown",
    },
    "max_context_length": {
        "name": "Panjang konteks maksimal (LLM)",
        "value": 32000,
        "component": "number",
    },
    "top_k": {
        "name": "Jumlah dokumen yang diambil",
        "value": 30, 
        "component": "number",
    },
    "use_reranking": {
        "name": "Gunakan Reranking",
        "value": True,
        "component": "checkbox",
    },
    "rerank_top_k": {
        "name": "Jumlah dokumen setelah reranking",
        "value": 15,
        "component": "number",
    },
    "use_query_rewriting": {
        "name": "Gunakan Query Rewriting",
        "value": True,
        "component": "checkbox",
    },
}

USE_GLOBAL_GRAPHRAG = config("USE_GLOBAL_GRAPHRAG", default=True, cast=bool)
USE_NANO_GRAPHRAG = config("USE_NANO_GRAPHRAG", default=False, cast=bool)
USE_LIGHTRAG = config("USE_LIGHTRAG", default=False, cast=bool)
USE_MS_GRAPHRAG = config("USE_MS_GRAPHRAG", default=False, cast=bool)


GRAPHRAG_INDICES = []

if USE_MS_GRAPHRAG:
    GRAPHRAG_INDICES.append({
        "name": "GraphRAG Collection",
        "config": {
            "supported_file_types": (
                ".pdf, .xls, .xlsx, .doc, .docx, "
                ".pptx, .csv, .html"
            ),
            "private": True,
        },
        "index_type": "ktem.index.file.graph.GraphRAGIndex",
    })

if USE_LIGHTRAG:
    GRAPHRAG_INDICES.append({
        "name": "LightRAG Collection",
        "config": {
            "supported_file_types": (
                ".pdf, .xls, .xlsx, .doc, .docx, "
                ".pptx, .csv, .html"
            ),
            "private": True,
        },
        "index_type": "ktem.index.file.graph.LightRAGIndex",
    })

if USE_NANO_GRAPHRAG:
    GRAPHRAG_INDICES.append({
        "name": "NanoGraphRAG Collection",
        "config": {
            "supported_file_types": (
                ".pdf, .xls, .xlsx, .doc, .docx, "
                ".pptx, .csv, .html"
            ),
            "private": True,
        },
        "index_type": "ktem.index.file.graph.NanoGraphRAGIndex",
    })

KH_INDEX_TYPES = [
    "ktem.index.file.FileIndex",
    *[idx["index_type"] for idx in GRAPHRAG_INDICES],
]

# ✅ CRITICAL FIX: KH_INDICES hanya berisi yang diperlukan
KH_INDICES = [
    {
        "name": "Koleksi File",
        "config": {
            "supported_file_types": (
                ".pdf, .xls, .xlsx, .doc, .docx, "
                ".pptx, .csv, .html"
            ),
            "private": True,
        },
        "index_type": "ktem.index.file.FileIndex",
    },
    *GRAPHRAG_INDICES,  # Hanya tambahkan yang aktif
] 



# Application settings
KH_APP_NAME = "SIPADU AI TOOLS - Sistem manajemen data dan metadata terpusat, terstruktur dan terdokumentasi"

# SIPADU Integration Settings - FROM ENVIRONMENT VARIABLES
SIPADU_API_BASE = config("SIPADU_API_BASE", default="http://localhost.sipadubapelitbangor")
SIPADU_HOME_URL = f"{SIPADU_API_BASE}/home"
SIPADU_LOGO_PATH = "libs/ktem/ktem/assets/img/logo.png"


# Application settings
KH_APP_NAME = "SIPADU AI TOOLS - Sistem manajemen data dan metadata terpusat, terstruktur dan terdokumentasi"

# SIPADU Integration Settings - FROM ENVIRONMENT VARIABLES
SIPADU_API_BASE = config("SIPADU_API_BASE", default="http://localhost.sipadubapelitbangor")
SIPADU_HOME_URL = f"{SIPADU_API_BASE}/home"
SIPADU_LOGO_PATH = "libs/ktem/ktem/assets/img/logo.png"

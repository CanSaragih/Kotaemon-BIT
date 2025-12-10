import logging
import threading
from textwrap import dedent
from typing import Generator

from decouple import config
from ktem.embeddings.manager import embedding_models_manager as embeddings
from ktem.llms.manager import llms
from ktem.reasoning.prompt_optimization import (
    DecomposeQuestionPipeline,
    RewriteQuestionPipeline,
)
from ktem.utils.render import Render
from ktem.utils.visualize_cited import CreateCitationVizPipeline
from plotly.io import to_json

from kotaemon.base import (
    AIMessage,
    BaseComponent,
    Document,
    HumanMessage,
    Node,
    RetrievedDocument,
    SystemMessage,
)
from kotaemon.indices.qa.citation_qa import (
    CONTEXT_RELEVANT_WARNING_SCORE,
    DEFAULT_QA_TEXT_PROMPT,
    AnswerWithContextPipeline,
)
from kotaemon.indices.qa.citation_qa_inline import AnswerWithInlineCitation
from kotaemon.indices.qa.format_context import PrepareEvidencePipeline
from kotaemon.indices.qa.utils import replace_think_tag_with_details
from kotaemon.llms import ChatLLM

from ..utils import SUPPORTED_LANGUAGE_MAP
from .base import BaseReasoning

logger = logging.getLogger(__name__)


class AddQueryContextPipeline(BaseComponent):

    n_last_interactions: int = 5
    llm: ChatLLM = Node(default_callback=lambda _: llms.get_default())

    def run(self, question: str, history: list) -> Document:
        messages = [
            SystemMessage(
                content="Berikut adalah riwayat percakapan sejauh ini, dan pertanyaan baru "
                "yang diajukan oleh pengguna yang perlu dijawab dengan mencari "
                "di basis pengetahuan.\nAnda memiliki akses ke indeks Pencarian "
                "dengan ratusan dokumen.\nBuat kueri pencarian berdasarkan "
                "percakapan dan pertanyaan baru.\nJangan sertakan nama file sumber "
                "yang dikutip dan nama dokumen seperti info.txt atau doc.pdf dalam "
                "istilah kueri pencarian.\nJangan sertakan teks apa pun di dalam [] "
                "atau <<>> dalam istilah kueri pencarian.\nJangan sertakan karakter "
                "khusus seperti '+'.\nJika pertanyaan tidak dalam bahasa Indonesia, "
                "tulis ulang kueri dalam bahasa yang digunakan dalam pertanyaan.\n "
                "Jika pertanyaan mengandung informasi yang cukup, kembalikan angka 1\n "
                "Jika tidak perlu melakukan pencarian, kembalikan angka 0."
            ),
            HumanMessage(content="Bagaimana kinerja crypto tahun lalu?"),
            AIMessage(
                content="Rangkum Dinamika Pasar Cryptocurrency dari tahun lalu"
            ),
            HumanMessage(content="Apa rencana kesehatan saya?"),
            AIMessage(content="Tampilkan rencana kesehatan yang tersedia"),
        ]
        for human, ai in history[-self.n_last_interactions :]:
            messages.append(HumanMessage(content=human))
            messages.append(AIMessage(content=ai))

        messages.append(HumanMessage(content=f"Generate search query for: {question}"))

        resp = self.llm(messages).text
        if resp == "0":
            return Document(content="")

        if resp == "1":
            return Document(content=question)

        return Document(content=resp)


class FullQAPipeline(BaseReasoning):
    """Question answering pipeline. Handle from question to answer"""

    class Config:
        allow_extra = True

    # configuration parameters
    trigger_context: int = 150
    use_rewrite: bool = False

    retrievers: list[BaseComponent]

    evidence_pipeline: PrepareEvidencePipeline = PrepareEvidencePipeline.withx()
    answering_pipeline: AnswerWithContextPipeline
    rewrite_pipeline: RewriteQuestionPipeline | None = None
    create_citation_viz_pipeline: CreateCitationVizPipeline = Node(
        default_callback=lambda _: CreateCitationVizPipeline(
            embedding=embeddings.get_default()
        )
    )
    add_query_context: AddQueryContextPipeline = AddQueryContextPipeline.withx()

    def retrieve(
        self, message: str, history: list
    ) -> tuple[list[RetrievedDocument], list[Document]]:
        """Retrieve the documents based on the message"""

        import re

        # Extract keywords (remove filler words)
        stopwords = {'ini', 'itu', 'yang', 'dan', 'atau', 'dari', 'ke', 'di', 'untuk', 
                    'dengan', 'pada', 'adalah', 'secara', 'dapat', 'akan', 'telah',
                    'deskripsikan', 'jelaskan', 'ringkas', 'uraikan', 'gambarkan'}
        
        tokens = re.findall(r'\w+', message.lower())
        keywords = [t for t in tokens if t not in stopwords and len(t) > 2]
        
        # Build better query
        enhanced_query = ' '.join(keywords)

        print(f"📝 Original message: {message}")
        print(f"🔑 Keywords extracted: {keywords}")
        print(f"🔍 Enhanced query: {enhanced_query}")

        # ✅ FIX: Fallback jika enhanced_query kosong
        if not enhanced_query or len(enhanced_query.strip()) < 3:
            print("⚠️ Enhanced query too short, using original message")
            enhanced_query = message

        retrieval_kwargs = {
            "query_text": enhanced_query,  # ✅ Use enhanced query
            "top_k": self.trigger_context * 2,
        }
        
        retrieved_documents = []
        for retriever in self.retrievers:
            try:
                docs = retriever(message, **retrieval_kwargs)
                retrieved_documents.extend(docs)
                print(f"✅ Retriever returned {len(docs)} documents")
            except Exception as e:
                print(f"❌ Error in retriever: {e}")
                import traceback
                traceback.print_exc()
        
        # ✅ Reranking jika aktif
        if hasattr(self, 'reranker') and self.reranker:
            from kotaemon.rerankings import BaseReranking
            if isinstance(self.reranker, BaseReranking):
                try:
                    print(f"🔄 Reranking {len(retrieved_documents)} documents...")
                    retrieved_documents = self.reranker.run(
                        documents=retrieved_documents,
                        query=message
                    )[:self.trigger_context]
                except Exception as e:
                    print(f"⚠️ Reranking failed: {e}")

        query = message  # Use original message for display

        docs, doc_ids = [], []
        plot_docs = []

        for idx, retriever in enumerate(self.retrievers):
            retriever_node = self._prepare_child(retriever, f"retriever_{idx}")
            try:
                retriever_docs = retriever_node(text=query)

                retriever_docs_text = []
                retriever_docs_plot = []

                for doc in retriever_docs:
                    if doc.metadata.get("type", "") == "plot":
                        retriever_docs_plot.append(doc)
                    else:
                        retriever_docs_text.append(doc)

                for doc in retriever_docs_text:
                    if doc.doc_id not in doc_ids:
                        docs.append(doc)
                        doc_ids.append(doc.doc_id)

                plot_docs.extend(retriever_docs_plot)
            except Exception as e:
                print(f"❌ Error in retriever node {idx}: {e}")

        info = [
            Document(
                channel="info",
                content=Render.collapsible_with_header(doc, open_collapsible=True),
            )
            for doc in docs
        ] + [
            Document(
                channel="plot",
                content=doc.metadata.get("data", ""),
            )
            for doc in plot_docs
        ]

        return docs, info

    def prepare_mindmap(self, answer) -> Document | None:
        mindmap = answer.metadata["mindmap"]
        if mindmap:
            mindmap_text = mindmap.text
            mindmap_svg = dedent(
                """
                <div class="markmap">
                <script type="text/template">
                ---
                markmap:
                    colorFreezeLevel: 2
                    activeNode:
                        placement: center
                    initialExpandLevel: 4
                    maxWidth: 200
                ---
                {}
                </script>
                </div>
                """
            ).format(mindmap_text)

            mindmap_content = Document(
                channel="info",
                content=Render.collapsible(
                    header="""
                    <i>Mindmap</i>
                    <a href="#" id='mindmap-toggle'>
                        [Expand]</a>
                    <a href="#" id='mindmap-export'>
                        [Export]</a>""",
                    content=mindmap_svg,
                    open=True,
                ),
            )
        else:
            mindmap_content = None

        return mindmap_content

    def prepare_citation_viz(self, answer, question, docs) -> Document | None:
        doc_texts = [doc.text for doc in docs]
        citation_plot = None
        plot_content = None

        if answer.metadata["citation_viz"] and len(docs) > 1:
            try:
                citation_plot = self.create_citation_viz_pipeline(doc_texts, question)
            except Exception as e:
                print("Failed to create citation plot:", e)

            if citation_plot:
                plot = to_json(citation_plot)
                plot_content = Document(channel="plot", content=plot)

        return plot_content

    def show_citations_and_addons(self, answer, docs, question):
        # show the evidence
        with_citation, without_citation = self.answering_pipeline.prepare_citations(
            answer, docs
        )
        mindmap_output = self.prepare_mindmap(answer)
        citation_plot_output = self.prepare_citation_viz(answer, question, docs)

        if not with_citation and not without_citation:
            yield Document(channel="info", content="<h5><b>Tidak ada bukti yang ditemukan.</b></h5>")
        else:
            # clear the Info panel
            max_llm_rerank_score = max(
                doc.metadata.get("llm_trulens_score", 0.0) for doc in docs
            )
            has_llm_score = any("llm_trulens_score" in doc.metadata for doc in docs)
            # clear previous info
            yield Document(channel="info", content=None)

            # yield mindmap output
            if mindmap_output:
                yield mindmap_output

            # yield citation plot output
            if citation_plot_output:
                yield citation_plot_output

            # yield warning message
            if has_llm_score and max_llm_rerank_score < CONTEXT_RELEVANT_WARNING_SCORE:
                yield Document(
                    channel="info",
                    content=(
                        "<h5>PERINGATAN! Skor relevansi konteks rendah. "
                        "Periksa kembali jawaban model untuk memastikan kebenaran.</h5>"
                    ),
                )

            # show QA score
            qa_score = (
                round(answer.metadata["qa_score"], 2)
                if answer.metadata.get("qa_score")
                else None
            )
            if qa_score:
                yield Document(
                    channel="info",
                    content=f"<h5>Tingkat kepercayaan jawaban: {qa_score}</h5>",
                )

            yield from with_citation
            if without_citation:
                yield from without_citation

    async def ainvoke(  # type: ignore
        self, message: str, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Document:  # type: ignore
        raise NotImplementedError

    def stream(  # type: ignore
        self, message: str, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Generator[Document, None, Document]:
        if self.use_rewrite and self.rewrite_pipeline:
            print("Chosen rewrite pipeline", self.rewrite_pipeline)
            message = self.rewrite_pipeline(question=message).text
            print("Rewrite result", message)

        print(f"Retrievers {self.retrievers}")
        # should populate the context
        docs, infos = self.retrieve(message, history)
        print(f"Got {len(docs)} retrieved documents")
        yield from infos

        evidence_mode, evidence, images = self.evidence_pipeline(docs).content

        def generate_relevant_scores():
            nonlocal docs
            docs = self.retrievers[0].generate_relevant_scores(message, docs)

        # generate relevant score using
        if evidence and self.retrievers:
            scoring_thread = threading.Thread(target=generate_relevant_scores)
            scoring_thread.start()
        else:
            scoring_thread = None

        answer = yield from self.answering_pipeline.stream(
            question=message,
            history=history,
            evidence=evidence,
            evidence_mode=evidence_mode,
            images=images,
            conv_id=conv_id,
            **kwargs,
        )

        # check <think> tag from reasoning models
        processed_answer = replace_think_tag_with_details(answer.text)
        if processed_answer != answer.text:
            # clear the chat message and render again
            yield Document(channel="chat", content=None)
            yield Document(channel="chat", content=processed_answer)

        # show the evidence
        if scoring_thread:
            scoring_thread.join()

        yield from self.show_citations_and_addons(answer, docs, message)

        return answer

    @classmethod
    def prepare_pipeline_instance(cls, settings, retrievers):
        return cls(
            retrievers=retrievers,
            rewrite_pipeline=None,
        )

    @classmethod
    def get_pipeline(cls, settings, states, retrievers):
        """Get the reasoning pipeline

        Args:
            settings: the settings for the pipeline
            retrievers: the retrievers to use
        """
        max_context_length_setting = settings.get("reasoning.max_context_length", 32000)

        pipeline = cls.prepare_pipeline_instance(settings, retrievers)

        prefix = f"reasoning.options.{cls.get_info()['id']}"
        llm_name = settings.get(f"{prefix}.llm", None)
        llm = llms.get(llm_name, llms.get_default())

        # prepare evidence pipeline configuration
        evidence_pipeline = pipeline.evidence_pipeline
        evidence_pipeline.max_context_length = max_context_length_setting

        # answering pipeline configuration
        use_inline_citation = settings[f"{prefix}.highlight_citation"] == "inline"

        if use_inline_citation:
            answer_pipeline = pipeline.answering_pipeline = AnswerWithInlineCitation()
        else:
            answer_pipeline = pipeline.answering_pipeline = AnswerWithContextPipeline()

        answer_pipeline.llm = llm
        answer_pipeline.citation_pipeline.llm = llm
        answer_pipeline.n_last_interactions = settings[f"{prefix}.n_last_interactions"]
        answer_pipeline.enable_citation = (
            settings[f"{prefix}.highlight_citation"] != "off"
        )
        answer_pipeline.enable_mindmap = settings[f"{prefix}.create_mindmap"]
        answer_pipeline.enable_citation_viz = settings[f"{prefix}.create_citation_viz"]
        answer_pipeline.use_multimodal = settings[f"{prefix}.use_multimodal"]
        answer_pipeline.system_prompt = settings[f"{prefix}.system_prompt"]
        answer_pipeline.qa_template = settings[f"{prefix}.qa_prompt"]
        answer_pipeline.lang = SUPPORTED_LANGUAGE_MAP.get(
            settings["reasoning.lang"], "English"
        )

        pipeline.add_query_context.llm = llm
        pipeline.add_query_context.n_last_interactions = settings[
            f"{prefix}.n_last_interactions"
        ]

        pipeline.trigger_context = settings[f"{prefix}.trigger_context"]
        pipeline.use_rewrite = states.get("app", {}).get("regen", False)
        if pipeline.rewrite_pipeline:
            pipeline.rewrite_pipeline.llm = llm
            pipeline.rewrite_pipeline.lang = SUPPORTED_LANGUAGE_MAP.get(
                settings["reasoning.lang"], "English"
            )
        return pipeline

    @classmethod
    def get_user_settings(cls) -> dict:
        from ktem.llms.manager import llms

        llm = ""
        choices = [("(default)", "")]
        try:
            choices += [(_, _) for _ in llms.options().keys()]
        except Exception as e:
            logger.exception(f"Failed to get LLM options: {e}")

        return {
            "llm": {
                "name": "Model bahasa",
                "value": llm,
                "component": "dropdown",
                "choices": choices,
                "special_type": "llm",
                "info": (
                    "Model bahasa yang digunakan untuk menghasilkan jawaban. "
                    "Jika tidak ada, model bahasa default aplikasi akan digunakan."
                ),
            },
            "highlight_citation": {
                "name": "Gaya kutipan",
                "value": (
                    "highlight"
                    if not config("USE_LOW_LLM_REQUESTS", default=False, cast=bool)
                    else "off"
                ),
                "component": "radio",
                "choices": [
                    ("kutipan: sorot", "highlight"),
                    ("kutipan: sebaris", "inline"),
                    ("tanpa kutipan", "off"),
                ],
            },
            "create_mindmap": {
                "name": "Buat Peta Pikiran",
                "value": False,
                "component": "checkbox",
            },
            "create_citation_viz": {
                "name": "Buat Visualisasi Embeddings",
                "value": False,
                "component": "checkbox",
            },
            "use_multimodal": {
                "name": "Gunakan Input Multimodal",
                "value": False,
                "component": "checkbox",
            },
            "system_prompt": {
                "name": "Prompt Sistem",
                "value": (
                    "Anda adalah asisten ahli perencanaan pembangunan daerah berbasis data. "
                    "Berikan jawaban yang lengkap, detail, dan berbasis bukti dengan penjelasan yang memadai. "
                    "Gunakan bullet points untuk struktur yang jelas. "
                    "Sertakan contoh konkret dan data relevan jika tersedia. "
                    "Jika tidak tahu jawabannya, jelaskan dengan detail mengapa informasi tidak tersedia."
                ),
            },
            "qa_prompt": {
                "name": "Prompt QA (berisi {context}, {question}, {lang})",
                "value": (
                    "Berdasarkan konteks berikut, jawab pertanyaan dengan lengkap dan detail. "
                    "Berikan penjelasan yang komprehensif dengan struktur yang jelas:\n"
                    "Jika informasi tidak lengkap, jelaskan apa yang tersedia dan apa yang masih perlu dicari. "
                    "Berikan jawaban dalam {lang}.\n\n"
                    "{context}\n\n"
                    "Pertanyaan: {question}\n\n"
                    "Jawaban lengkap:"
                ),
            },
            "n_last_interactions": {
                "name": "Jumlah interaksi yang disertakan",
                "value": 2,
                "component": "number",
                "info": "Jumlah maksimum interaksi chat yang disertakan dalam LLM",
            },
            "trigger_context": {
                "name": "Panjang pesan maksimum untuk penulisan ulang konteks",
                "value": 150,
                "component": "number",
                "info": (
                    "Panjang maksimum pesan untuk memicu penambahan konteks. "
                    "Melebihi panjang ini, pesan akan digunakan apa adanya."
                ),
            },
        }

    @classmethod
    def get_info(cls) -> dict:
        return {
            "id": "simple",
            "name": "QA Sederhana",
            "description": (
                "Pipeline tanya jawab berbasis RAG sederhana. Pipeline ini dapat "
                "melakukan pencarian kata kunci dan pencarian kemiripan untuk mengambil "
                "konteks. Setelah itu, konteks tersebut disertakan untuk menghasilkan jawaban."
            ),
        }


class FullDecomposeQAPipeline(FullQAPipeline):
    def answer_sub_questions(
        self, messages: list, conv_id: str, history: list, **kwargs
    ):
        output_str = ""
        for idx, message in enumerate(messages):
            yield Document(
                channel="chat",
                content=f"<br><b>Sub-pertanyaan {idx + 1}</b>"
                f"<br>{message}<br><b>Jawaban</b><br>",
            )
            
            # should populate the context
            docs, infos = self.retrieve(message, history)
            print(f"Got {len(docs)} retrieved documents")

            yield from infos

            evidence_mode, evidence, images = self.evidence_pipeline(docs).content
            answer = yield from self.answering_pipeline.stream(
                question=message,
                history=history,
                evidence=evidence,
                evidence_mode=evidence_mode,
                images=images,
                conv_id=conv_id,
                **kwargs,
            )

            output_str += (
                f"Sub-pertanyaan ke-{idx + 1}: '{message}'\nJawaban: '{answer.text}'\n\n"
            )

        return output_str

    def stream(self, message: str, conv_id: str, history: list, **kwargs) -> Generator[Document, None, Document]:
        sub_question_answer_output = ""
        if self.rewrite_pipeline:
            print("Chosen rewrite pipeline", self.rewrite_pipeline)
            result = self.rewrite_pipeline(question=message)
            print("Rewrite result", result)
            if isinstance(result, Document):
                message = result.text
            elif (
                isinstance(result, list)
                and len(result) > 0
                and isinstance(result[0], Document)
            ):
                yield Document(
                    channel="chat",
                    content="<h4>Sub-pertanyaan dan jawabannya</h4>",
                )
                sub_question_answer_output = yield from self.answer_sub_questions(
                    [r.text for r in result], conv_id, history, **kwargs
                )

        yield Document(
            channel="chat",
            content=f"<h4>Pertanyaan utama</h4>{message}<br><b>Jawaban</b><br>",
        )

        # should populate the context
        docs, infos = self.retrieve(message, history)
        print(f"Got {len(docs)} retrieved documents")
        yield from infos

        evidence_mode, evidence, images = self.evidence_pipeline(docs).content
        answer = yield from self.answering_pipeline.stream(
            question=message,
            history=history,
            evidence=evidence + "\n" + sub_question_answer_output,
            evidence_mode=evidence_mode,
            images=images,
            conv_id=conv_id,
            **kwargs,
        )

        # show the evidence
        with_citation, without_citation = self.answering_pipeline.prepare_citations(
            answer, docs
        )
        if not with_citation and not without_citation:
            yield Document(channel="info", content="<h5><b>Tidak ada bukti yang ditemukan.</b></h5>")
        else:
            yield Document(channel="info", content=None)
            yield from with_citation
            yield from without_citation

        return answer

    @classmethod
    def get_user_settings(cls) -> dict:
        user_settings = super().get_user_settings()
        user_settings["decompose_prompt"] = {
            "name": "Prompt Uraian",
            "value": DecomposeQuestionPipeline.DECOMPOSE_SYSTEM_PROMPT_TEMPLATE,
        }
        return user_settings

    @classmethod
    def prepare_pipeline_instance(cls, settings, retrievers):
        prefix = f"reasoning.options.{cls.get_info()['id']}"
        pipeline = cls(
            retrievers=retrievers,
            rewrite_pipeline=DecomposeQuestionPipeline(
                prompt_template=settings.get(f"{prefix}.decompose_prompt")
            ),
        )
        return pipeline

    @classmethod
    def get_info(cls) -> dict:
        return {
            "id": "complex",
            "name": "QA Kompleks",
            "description": (
                "Menggunakan penalaran multi-langkah untuk menguraikan pertanyaan kompleks "
                "menjadi beberapa sub-pertanyaan. Pipeline ini dapat "
                "melakukan pencarian kata kunci dan pencarian kemiripan untuk mengambil "
                "konteks. Setelah itu, konteks tersebut disertakan untuk menghasilkan jawaban."
            ),
        }
        

import html
import logging
from typing import AnyStr, Optional, Type

from ktem.llms.manager import llms
from ktem.reasoning.base import BaseReasoning
from ktem.utils.generator import Generator
from ktem.utils.render import Render
from langchain.text_splitter import CharacterTextSplitter
from pydantic import BaseModel, Field

from kotaemon.agents import (
    BaseTool,
    GoogleSearchTool,
    LLMTool,
    ReactAgent,
    WikipediaTool,
)
from kotaemon.base import BaseComponent, Document, HumanMessage, Node, SystemMessage
from kotaemon.llms import ChatLLM, PromptTemplate

from ..utils import SUPPORTED_LANGUAGE_MAP

logger = logging.getLogger(__name__)
DEFAULT_AGENT_STEPS = 4


class DocSearchArgs(BaseModel):
    query: str = Field(..., description="a search query as input to the doc search")


class DocSearchTool(BaseTool):
    name: str = "pencarian_dokumen"
    description: str = (
        "Penyimpanan yang berisi dokumen internal. Jika Anda kekurangan informasi pribadi spesifik "
        "untuk menjawab pertanyaan, Anda dapat mencari di penyimpanan dokumen ini. "
        "Selain itu, jika Anda tidak yakin tentang dokumen mana yang dimaksud pengguna, "
        "kemungkinan pengguna sudah memilih dokumen target di penyimpanan dokumen ini, "
        "Anda hanya perlu melakukan pencarian normal. Jika memungkinkan, "
        "rumuskan kueri pencarian sekhusus mungkin."
    )
    args_schema: Optional[Type[BaseModel]] = DocSearchArgs
    retrievers: list[BaseComponent] = []

    def _run_tool(self, query: AnyStr) -> AnyStr:
        docs = []
        doc_ids = []
        for retriever in self.retrievers:
            for doc in retriever(text=query):
                if doc.doc_id not in doc_ids:
                    docs.append(doc)
                    doc_ids.append(doc.doc_id)

        return self.prepare_evidence(docs)

    def prepare_evidence(self, docs, trim_len: int = 4000):
        evidence = ""
        table_found = 0

        for _id, retrieved_item in enumerate(docs):
            retrieved_content = ""
            page = retrieved_item.metadata.get("page_label", None)
            source = filename = retrieved_item.metadata.get("file_name", "-")
            if page:
                source += f" (Page {page})"
            if retrieved_item.metadata.get("type", "") == "table":
                if table_found < 5:
                    retrieved_content = retrieved_item.metadata.get("table_origin", "")
                    if retrieved_content not in evidence:
                        table_found += 1
                        evidence += (
                            f"<br><b>Table from {source}</b>\n"
                            + retrieved_content
                            + "\n<br>"
                        )
            elif retrieved_item.metadata.get("type", "") == "chatbot":
                retrieved_content = retrieved_item.metadata["window"]
                evidence += (
                    f"<br><b>Chatbot scenario from {filename} (Row {page})</b>\n"
                    + retrieved_content
                    + "\n<br>"
                )
            elif retrieved_item.metadata.get("type", "") == "image":
                retrieved_content = retrieved_item.metadata.get("image_origin", "")
                retrieved_caption = html.escape(retrieved_item.get_content())
                evidence += (
                    f"<br><b>Figure from {source}</b>\n" + retrieved_caption + "\n<br>"
                )
            else:
                if "window" in retrieved_item.metadata:
                    retrieved_content = retrieved_item.metadata["window"]
                else:
                    retrieved_content = retrieved_item.text
                retrieved_content = retrieved_content.replace("\n", " ")
                if retrieved_content not in evidence:
                    evidence += (
                        f"<br><b>Content from {source}: </b> "
                        + retrieved_content
                        + " \n<br>"
                    )

            print("Retrieved #{}: {}".format(_id, retrieved_content[:100]))
            print("Score", retrieved_item.metadata.get("reranking_score", None))

        # trim context by trim_len
        if evidence:
            text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
                chunk_size=trim_len,
                chunk_overlap=0,
                separator=" ",
                model_name="gpt-3.5-turbo",
            )
            texts = text_splitter.split_text(evidence)
            evidence = texts[0]

        return Document(content=evidence)


TOOL_REGISTRY = {
    "Google": GoogleSearchTool(),
    "Wikipedia": WikipediaTool(),
    "LLM": LLMTool(),
    "SearchDoc": DocSearchTool(),
}

DEFAULT_QA_PROMPT = (
    "Jawab pertanyaan berikut sebaik mungkin. Berikan jawaban dalam {lang}. "
    "Anda memiliki akses ke alat-alat berikut:\n"
    "{tool_description}\n"
    "Gunakan format berikut:\n\n"
    "Pertanyaan: pertanyaan input yang harus Anda jawab\n"
    "Pemikiran: Anda harus selalu memikirkan apa yang harus dilakukan\n\n"
    "Tindakan: tindakan yang akan diambil, harus salah satu dari [{tool_names}]\n\n"
    "Input Tindakan: input untuk tindakan, harus berbeda dari input tindakan "
    "dari tindakan yang sama di langkah sebelumnya.\n\n"
    "Observasi: hasil dari tindakan\n\n"
    "... (Pemikiran/Tindakan/Input Tindakan/Observasi ini dapat diulang N kali)\n"
    "#Pemikiran: Sekarang saya tahu jawaban akhirnya\n"
    "Jawaban Akhir: jawaban akhir untuk pertanyaan input asli\n\n"
    "Mulai! Setelah setiap Input Tindakan.\n\n"
    "Pertanyaan: {instruction}\n"
    "Pemikiran: {agent_scratchpad}\n"
)

DEFAULT_REWRITE_PROMPT = (
    "Diberikan pertanyaan berikut, rumuskan ulang dan kembangkan "
    "untuk membantu Anda menjawab dengan lebih baik. Pertahankan semua informasi "
    "dalam pertanyaan asli. Buat pertanyaan sesingkat mungkin. "
    "Berikan jawaban dalam {lang}\n"
    "Pertanyaan asli: {question}\n"
    "Pertanyaan yang dirumuskan ulang: "
)


class RewriteQuestionPipeline(BaseComponent):
    """Rewrite user question

    Args:
        llm: the language model to rewrite question
        rewrite_template: the prompt template for llm to paraphrase a text input
        lang: the language of the answer. Currently support English and Japanese
    """

    llm: ChatLLM = Node(default_callback=lambda _: llms.get_default())
    rewrite_template: str = DEFAULT_REWRITE_PROMPT

    lang: str = "English"

    def run(self, question: str) -> Document:  # type: ignore
        prompt_template = PromptTemplate(self.rewrite_template)
        prompt = prompt_template.populate(question=question, lang=self.lang)
        messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content=prompt),
        ]
        return self.llm(messages)


class ReactAgentPipeline(BaseReasoning):
    """Question answering pipeline using ReAct agent."""

    class Config:
        allow_extra = True

    retrievers: list[BaseComponent]
    agent: ReactAgent = ReactAgent.withx()
    rewrite_pipeline: RewriteQuestionPipeline = RewriteQuestionPipeline.withx()
    use_rewrite: bool = False

    def prepare_citation(self, step_id, step, output, status) -> Document:
        header = "<b>Step {id}</b>: {log}".format(id=step_id, log=step.log)
        content = (
            "<b>Action</b>: <em>{tool}[{input}]</em>\n\n<b>Output</b>: {output}"
        ).format(
            tool=step.tool if status == "thinking" else "",
            input=step.tool_input.replace("\n", "").replace('"', "")
            if status == "thinking"
            else "",
            output=output if status == "thinking" else "Finished",
        )
        return Document(
            channel="info",
            content=Render.collapsible(
                header=header,
                content=Render.table(content),
                open=True,
            ),
        )

    async def ainvoke(  # type: ignore
        self, message, conv_id: str, history: list, **kwargs  # type: ignore
    ) -> Document:
        if self.use_rewrite:
            rewrite = await self.rewrite_pipeline(question=message)
            message = rewrite.text

        answer = self.agent(message)
        self.report_output(Document(content=answer.text, channel="chat"))

        intermediate_steps = answer.intermediate_steps
        for _, step_output in intermediate_steps:
            self.report_output(Document(content=step_output, channel="info"))

        self.report_output(None)
        return answer

    def stream(self, message, conv_id: str, history: list, **kwargs):
        if self.use_rewrite:
            rewrite = self.rewrite_pipeline(question=message)
            message = rewrite.text
            yield Document(
                channel="info",
                content=f"Rewrote the message to: {rewrite.text}",
            )

        output_stream = Generator(self.agent.stream(message))
        idx = 0
        for item in output_stream:
            idx += 1
            if item.status == "thinking":
                step, step_output = item.intermediate_steps
                yield Document(
                    channel="info",
                    content=self.prepare_citation(idx, step, step_output, item.status),
                )
            else:
                yield Document(
                    channel="chat",
                    content=item.text,
                )
                step, step_output = item.intermediate_steps
                yield Document(
                    channel="info",
                    content=self.prepare_citation(idx, step, step_output, item.status),
                )

        return output_stream.value

    @classmethod
    def get_pipeline(
        cls, settings: dict, states: dict, retrievers: list | None = None
    ) -> BaseReasoning:
        _id = cls.get_info()["id"]
        prefix = f"reasoning.options.{_id}"

        llm_name = settings[f"{prefix}.llm"]
        llm = llms.get(llm_name, llms.get_default())

        max_context_length_setting = settings.get("reasoning.max_context_length", None)

        pipeline = ReactAgentPipeline(retrievers=retrievers)
        pipeline.agent.llm = llm
        pipeline.agent.max_iterations = settings[f"{prefix}.max_iterations"]

        if max_context_length_setting:
            pipeline.agent.max_context_length = (
                max_context_length_setting // DEFAULT_AGENT_STEPS
            )

        tools = []
        for tool_name in settings[f"reasoning.options.{_id}.tools"]:
            tool = TOOL_REGISTRY[tool_name]
            if tool_name == "SearchDoc":
                tool.retrievers = retrievers
            elif tool_name == "LLM":
                tool.llm = llm
            tools.append(tool)
        pipeline.agent.plugins = tools
        pipeline.agent.output_lang = SUPPORTED_LANGUAGE_MAP.get(
            settings["reasoning.lang"], "English"
        )
        pipeline.use_rewrite = states.get("app", {}).get("regen", False)
        pipeline.agent.prompt_template = PromptTemplate(settings[f"{prefix}.qa_prompt"])

        return pipeline

    @classmethod
    def get_user_settings(cls) -> dict:
        llm = ""
        llm_choices = [("(default)", "")]
        try:
            llm_choices += [(_, _) for _ in llms.options().keys()]
        except Exception as e:
            logger.exception(f"Failed to get LLM options: {e}")

        tool_choices = ["Wikipedia", "Google", "LLM", "PencarianDokumen"]

        return {
            "llm": {
                "name": "Model bahasa",
                "value": llm,
                "component": "dropdown",
                "choices": llm_choices,
                "special_type": "llm",
                "info": (
                    "Model bahasa yang digunakan untuk menghasilkan jawaban. Jika Tidak Ada, "
                    "model bahasa default aplikasi akan digunakan."
                ),
            },
            "tools": {
                "name": "Alat untuk pengambilan pengetahuan",
                "value": ["PencarianDokumen", "LLM"],
                "component": "checkboxgroup",
                "choices": tool_choices,
            },
            "max_iterations": {
                "name": "Jumlah maksimum iterasi yang dapat dilakukan LLM",
                "value": 5,
                "component": "number",
            },
            "qa_prompt": {
                "name": "Prompt QA",
                "value": DEFAULT_QA_PROMPT,
            },
        }

    @classmethod
    def get_info(cls) -> dict:
        return {
            "id": "ReAct",
            "name": "Agen ReAct",
            "description": (
                "Mengimplementasikan paradigma ReAct: https://arxiv.org/abs/2210.03629. "
                "Agen ReAct menjawab permintaan pengguna dengan berulang kali merumuskan "
                "rencana dan menjalankannya. Agen dapat menggunakan beberapa alat untuk mengumpulkan "
                "informasi dan menghasilkan jawaban akhir."
            ),
        }

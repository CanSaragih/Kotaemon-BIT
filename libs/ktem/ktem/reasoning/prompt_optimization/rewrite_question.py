from ktem.llms.manager import llms

from kotaemon.base import BaseComponent, Document, HumanMessage, Node, SystemMessage
from kotaemon.llms import ChatLLM, PromptTemplate

DEFAULT_REWRITE_PROMPT = (
    "Diberikan pertanyaan berikut, rumuskan ulang dan kembangkan "
    "untuk membantu Anda menjawab dengan lebih baik. Pertahankan semua informasi "
    "dalam pertanyaan asli. Buat pertanyaan sesingkat mungkin. "
    "Hanya keluarkan pertanyaan yang dirumuskan ulang tanpa informasi tambahan. "
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

    lang: str = "Indonesian"

    def run(self, question: str) -> Document:  # type: ignore
        prompt_template = PromptTemplate(self.rewrite_template)
        prompt = prompt_template.populate(question=question, lang=self.lang)
        messages = [
            SystemMessage(content="You are a helpful assistant"),
            HumanMessage(content=prompt),
        ]
        return self.llm(messages)

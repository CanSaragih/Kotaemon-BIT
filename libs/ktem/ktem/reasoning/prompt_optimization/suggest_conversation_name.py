import logging

from ktem.llms.manager import llms

from kotaemon.base import AIMessage, BaseComponent, Document, HumanMessage, Node
from kotaemon.llms import ChatLLM, PromptTemplate

logger = logging.getLogger(__name__)


class SuggestConvNamePipeline(BaseComponent):
    """Suggest a good conversation name based on the chat history."""

    llm: ChatLLM = Node(default_callback=lambda _: llms.get_default())
    SUGGEST_NAME_PROMPT_TEMPLATE = (
        "Anda adalah ahli dalam menyarankan nama percakapan yang baik dan mudah diingat. "
        "Berdasarkan riwayat chat di atas, "
        "sarankan nama percakapan yang baik (maksimal 10 kata). "
        "Berikan jawaban dalam {lang}. Cukup keluarkan nama percakapan "
        "tanpa tambahan lainnya."
    )
    prompt_template: str = SUGGEST_NAME_PROMPT_TEMPLATE
    lang: str = "Indonesian"

    def run(self, chat_history: list[tuple[str, str]]) -> Document:  # type: ignore
        prompt_template = PromptTemplate(self.prompt_template)
        prompt = prompt_template.populate(lang=self.lang)

        messages = []
        for human, ai in chat_history:
            messages.append(HumanMessage(content=human))
            messages.append(AIMessage(content=ai))

        messages.append(HumanMessage(content=prompt))

        return self.llm(messages)

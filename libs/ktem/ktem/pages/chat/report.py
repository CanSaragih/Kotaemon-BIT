from typing import Optional

import gradio as gr
from ktem.app import BasePage
from ktem.db.models import IssueReport, engine
from sqlmodel import Session


class ReportIssue(BasePage):
    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Accordion(label="Umpan Balik", open=False, elem_id="report-accordion"):
            self.correctness = gr.Radio(
                choices=[
                    ("Jawaban sesuai", "correct"),
                    ("Jawaban tidak sesuai", "incorrect"),
                ],
                label="Kesesuaian Jawaban:",
            )
            self.issues = gr.CheckboxGroup(
                choices=[
                    ("Jawaban menyinggung", "offensive"),
                    ("Bukti yang diberikan salah", "wrong-evidence"),
                ],
                label="Masalah Lainnya:",
            )
            self.more_detail = gr.Textbox(
                placeholder=(
                    "Detail lebih lanjut (misalnya, seberapa salah itu, apa "
                    "jawaban yang benar, dll...)"
                ),
                container=False,
                lines=3,
            )
            gr.Markdown(
                "Percakapan dan pengaturan pengguna saat ini akan dikirim untuk membantu investigasi."
            )
            self.report_btn = gr.Button("Laporkan")

    def report(
        self,
        correctness: str,
        issues: list[str],
        more_detail: str,
        conv_id: str,
        chat_history: list,
        settings: dict,
        user_id: Optional[int],
        info_panel: str,
        chat_state: dict,
        *selecteds,
    ):
        selecteds_ = {}
        for index in self._app.index_manager.indices:
            if index.selector is not None:
                if isinstance(index.selector, int):
                    selecteds_[str(index.id)] = selecteds[index.selector]
                elif isinstance(index.selector, tuple):
                    selecteds_[str(index.id)] = [selecteds[_] for _ in index.selector]
                else:
                    print(f"Unknown selector type: {index.selector}")

        with Session(engine) as session:
            issue = IssueReport(
                issues={
                    "correctness": correctness,
                    "issues": issues,
                    "more_detail": more_detail,
                },
                chat={
                    "conv_id": conv_id,
                    "chat_history": chat_history,
                    "info_panel": info_panel,
                    "chat_state": chat_state,
                    "selecteds": selecteds_,
                },
                settings=settings,
                user=user_id,
            )
            session.add(issue)
            session.commit()
        gr.Info("Terima kasih atas umpan balik Anda")

import gradio as gr
from decouple import config
from ktem.app import BaseApp
from ktem.pages.chat import ChatPage
from ktem.pages.help import HelpPage
from ktem.pages.resources import ResourcesTab
from ktem.pages.settings import SettingsPage
from ktem.pages.setup import SetupPage
from theflow.settings import settings as flowsettings

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)
KH_ENABLE_FIRST_SETUP = getattr(flowsettings, "KH_ENABLE_FIRST_SETUP", False)
KH_APP_DATA_EXISTS = getattr(flowsettings, "KH_APP_DATA_EXISTS", True)

# override first setup setting
if config("KH_FIRST_SETUP", default=False, cast=bool):
    KH_APP_DATA_EXISTS = False


def toggle_first_setup_visibility():
    global KH_APP_DATA_EXISTS
    is_first_setup = not KH_DEMO_MODE and not KH_APP_DATA_EXISTS
    KH_APP_DATA_EXISTS = True
    return gr.update(visible=is_first_setup), gr.update(visible=not is_first_setup)


class App(BaseApp):
    """The main app of Kotaemon

    The main application contains app-level information:
        - setting state
        - user id

    App life-cycle:
        - Render
        - Declare public events
        - Subscribe public events
        - Register events
    """

    def ui(self):
        """Render the UI"""
        self._tabs = {}

        with gr.Tabs() as self.tabs:
            # ALWAYS show welcome/login tab for SIPADU SSO
            from ktem.pages.login import LoginPage

            with gr.Tab(
                "Selamat Datang!", elem_id="login-tab", id="login-tab"
            ) as self._tabs["login-tab"]:
                self.login_page = LoginPage(self)
                # Tambahkan ini agar LoginPage tahu tabs utama
                self.login_page._app.tabs = self.tabs

            with gr.Tab(
                "Chat",
                elem_id="chat-tab",
                id="chat-tab",
                visible=False,  # Hidden until authenticated
            ) as self._tabs["chat-tab"]:
                self.chat_page = ChatPage(self)

            if len(self.index_manager.indices) == 1:
                for index in self.index_manager.indices:
                    with gr.Tab(
                        f"{index.name}",
                        elem_id="indices-tab",
                        elem_classes=[
                            "fill-main-area-height",
                            "scrollable",
                            "indices-tab",
                        ],
                        id="indices-tab",
                        visible=False,  # Hidden until authenticated
                    ) as self._tabs[f"{index.id}-tab"]:
                        page = index.get_index_page_ui()
                        setattr(self, f"_index_{index.id}", page)
            elif len(self.index_manager.indices) > 1:
                with gr.Tab(
                    "File",
                    elem_id="indices-tab",
                    elem_classes=["fill-main-area-height", "scrollable", "indices-tab"],
                    id="indices-tab",
                    visible=False,  # Hidden until authenticated
                ) as self._tabs["indices-tab"]:
                    for index in self.index_manager.indices:
                        with gr.Tab(
                            index.name,
                            elem_id=f"{index.id}-tab",
                        ) as self._tabs[f"{index.id}-tab"]:
                            page = index.get_index_page_ui()
                            setattr(self, f"_index_{index.id}", page)

            if not KH_DEMO_MODE:
                if not KH_SSO_ENABLED:
                    with gr.Tab(
                        "Sumber Daya",
                        elem_id="resources-tab",
                        id="resources-tab",
                        visible=False,  # Hidden until authenticated
                        elem_classes=["fill-main-area-height", "scrollable", "hidden-tab-ui"],
                    ) as self._tabs["resources-tab"]:
                        self.resources_page = ResourcesTab(self)

                with gr.Tab(
                    "Pengaturan",
                    elem_id="settings-tab", 
                    id="settings-tab",
                    visible=False,  # Hidden until authenticated
                    elem_classes=["fill-main-area-height", "scrollable", "hidden-tab-ui"],
                ) as self._tabs["settings-tab"]:
                    self.settings_page = SettingsPage(self)

            with gr.Tab(
                "Bantuan",
                elem_id="help-tab",
                id="help-tab", 
                visible=False,  # Hidden until authenticated
                elem_classes=["fill-main-area-height", "scrollable", "hidden-tab-ui"],
            ) as self._tabs["help-tab"]:
                self.help_page = HelpPage(self)

        if KH_ENABLE_FIRST_SETUP:
            with gr.Column(visible=False) as self.setup_page_wrapper:
                self.setup_page = SetupPage(self)

    def on_subscribe_public_events(self):
        # SIPADU SSO - Enhanced visibility logic with conversation loading
        from ktem.db.engine import engine
        from ktem.db.models import User
        from sqlmodel import Session, select

        def toggle_login_visibility(user_id):
            print(f"🔄 toggle_login_visibility called with user_id: {user_id}")
            
            if not user_id:
                # Not authenticated - show only login tab
                return list(
                    (
                        gr.update(visible=True)
                        if k == "login-tab"
                        else gr.update(visible=False)
                    )
                    for k in self._tabs.keys()
                ) + [gr.update(selected="login-tab")]

            # ✅ ENHANCED: Authenticated - load conversations and files immediately
            with Session(engine) as session:
                user = session.exec(select(User).where(User.id == user_id)).first()
                if user is None:
                    print(f"❌ User {user_id} not found in database")
                    return list(
                        (
                            gr.update(visible=True)
                            if k == "login-tab"
                            else gr.update(visible=False)
                        )
                        for k in self._tabs.keys()
                    ) + [gr.update(selected="login-tab")]

                is_admin = getattr(user, 'admin', False)
                print(f"✅ User {user_id} authenticated, is_admin: {is_admin}")

            # ✅ CRITICAL: Load conversations using existing chat_control
            try:
                if hasattr(self, 'chat_page') and hasattr(self.chat_page, 'chat_control'):
                    conv_control = self.chat_page.chat_control
                    chat_history = conv_control.load_chat_history(user_id)
                    print(f"🎯 Loaded {len(chat_history)} conversations for authenticated user")
                    
                    # Auto-select first conversation if available
                    selected_conv = chat_history[0][1] if chat_history else None
                    print(f"🎯 Auto-selecting conversation: {selected_conv}")
                    
                    conversation_update = gr.update(
                        choices=chat_history, 
                        value=selected_conv
                    )
                else:
                    print("❌ Chat control not available in main app")
                    conversation_update = gr.update(choices=[], value=None)
            except Exception as e:
                print(f"❌ Error loading conversations in main: {e}")
                conversation_update = gr.update(choices=[], value=None)

            # ✅ NEW: Load files immediately after authentication
            try:
                if hasattr(self, 'index_manager') and self.index_manager.indices:
                    first_index = self.index_manager.indices[0]
                    if hasattr(first_index, '_page') and hasattr(first_index._page, 'list_file'):
                        file_list_state, file_list_df = first_index._page.list_file(user_id, "")
                        print(f"📁 Loaded {len(file_list_state)} files for authenticated user")
                        
                        # Prepare file list update
                        file_list_update = gr.update(value=file_list_df)
                        file_selector_update = gr.update(choices=[(f["name"], f["id"]) for f in file_list_state])
                    else:
                        print("❌ File index page not available in main app")
                        file_list_update = gr.update()
                        file_selector_update = gr.update()
                else:
                    print("❌ Index manager not available in main app")
                    file_list_update = gr.update()
                    file_selector_update = gr.update()
            except Exception as e:
                print(f"❌ Error loading files in main: {e}")
                file_list_update = gr.update()
                file_selector_update = gr.update()

            tabs_update = []
            for k in self._tabs.keys():
                if k == "login-tab":
                    tabs_update.append(gr.update(visible=False))
                elif k == "resources-tab":
                    tabs_update.append(gr.update(visible=is_admin))
                else:
                    tabs_update.append(gr.update(visible=True))

            tabs_update.append(gr.update(selected="chat-tab"))
            tabs_update.append(conversation_update)  # ✅ Add conversation update
            
            print("🚀 Authentication complete - chat tab selected with conversations and files loaded")
            return tabs_update

        # ✅ ENHANCED: Subscribe event dengan conversation dan file loading
        self.subscribe_event(
            name="onSignIn",
            definition={
                "fn": toggle_login_visibility,
                "inputs": [self.user_id],
                "outputs": list(self._tabs.values()) + [
                    self.tabs,
                    self.chat_page.chat_control.conversation  # ✅ Direct conversation update
                ],
                "show_progress": "hidden",
            },
        )

        # ✅ FIXED: onSignOut event
        self.subscribe_event(
            name="onSignOut",
            definition={
                "fn": lambda: (
                    [gr.update(visible=(k == "login-tab")) for k in self._tabs.keys()] +
                    [gr.update(selected="login-tab")] +
                    [gr.update(choices=[], value=None)]  # Clear conversations
                ),
                "outputs": list(self._tabs.values()) + [
                    self.tabs,
                    self.chat_page.chat_control.conversation
                ],
                "show_progress": "hidden",
            },
        )

        if KH_ENABLE_FIRST_SETUP:
            self.subscribe_event(
                name="onFirstSetupComplete",
                definition={
                    "fn": toggle_first_setup_visibility,
                    "inputs": [],
                    "outputs": [self.setup_page_wrapper, self.tabs],
                    "show_progress": "hidden",
                },
            )

    def _on_app_created(self):
        """Called when the app is created"""

        if KH_ENABLE_FIRST_SETUP:
            self.app.load(
                toggle_first_setup_visibility,
                inputs=[],
                outputs=[self.setup_page_wrapper, self.tabs],
            )

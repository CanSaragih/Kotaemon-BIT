import os
import pandas as pd
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
                        "Konfigurasi AI",
                        elem_id="resources-tab",
                        id="resources-tab",
                        visible=True,  # Hidden until authenticated
                        elem_classes=["fill-main-area-height", "scrollable", "hidden-tab-ui"],
                    ) as self._tabs["resources-tab"]:
                        self.resources_page = ResourcesTab(self)

                with gr.Tab(
                    "Pengaturan",
                    elem_id="settings-tab", 
                    id="settings-tab",
                    visible=True,  # Hidden until authenticated
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
                # ✅ ENHANCED: Clear all cached data when no user + detect user switch
                print("🗑️ No user_id - triggering complete data clearing")
                self._clear_user_session_data()
                self._force_clear_all_component_states()
                
                # ✅ NEW: Clear file manager specifically
                self._clear_file_manager()
                
                # Not authenticated - show only login tab
                signin_outputs = list(self._tabs.values()) + [
                    self.tabs,
                    self.chat_page.chat_control.conversation
                ]
                
                # ✅ ENHANCED: Clear all file data dengan force update
                file_clear_updates = []
                for index in self.index_manager.indices:
                    if hasattr(index, 'file_index_page'):
                        # Force clear dengan empty states
                        file_clear_updates.extend([
                            gr.update(value=[]), 
                            gr.update(value=pd.DataFrame.from_records([{
                                "id": "-", "name": "-", "size": "-", "tokens": "-",
                                "loader": "-", "date_created": "-",
                            }])),
                            gr.update(value=[]), 
                            gr.update(value=pd.DataFrame.from_records([{
                                "id": "-", "name": "-", "files": "-", "date_created": "-",
                            }])),
                            gr.update(choices=[], value=[])
                        ])
                    else:
                        file_clear_updates.extend([gr.update(), gr.update(), gr.update(), gr.update(), gr.update()])
                
                return list(
                    (
                        gr.update(visible=True)
                        if k == "login-tab"
                        else gr.update(visible=False)
                    )
                    for k in self._tabs.keys()
                ) + [gr.update(selected="login-tab"), gr.update(choices=[], value=None)] + file_clear_updates

            # ✅ ENHANCED: Check for user switch scenario
            current_user_env = os.getenv('CURRENT_USER_ID', '')
            expected_user_env = f"sipadu_{user_id}" if user_id else ""
            
            if current_user_env != expected_user_env and current_user_env:
                print(f"🔄 USER SWITCH DETECTED in main app! Old: {current_user_env}, New: {expected_user_env}")
                print("🗑️ Force clearing all data for user switch")
                self._clear_user_session_data()
                self._force_clear_all_component_states()
                # ✅ NEW: Clear and reload file manager for new user
                self._clear_file_manager()
                # Update environment
                os.environ['CURRENT_USER_ID'] = expected_user_env

            # ✅ ENHANCED: Authenticated - load conversations immediately
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
                    ) + [gr.update(selected="login-tab"), gr.update(choices=[], value=None)]

                is_admin = getattr(user, 'admin', False)
                print(f"✅ User {user_id} authenticated, is_admin: {is_admin}")

            # ✅ ENHANCED: Force reload conversations dengan cache clearing
            try:
                if hasattr(self, 'chat_page') and hasattr(self.chat_page, 'chat_control'):
                    conv_control = self.chat_page.chat_control
                    # Clear existing conversation cache
                    conv_control.conversation.value = None
                    conv_control.conversation.choices = []
                    
                    # Force reload from database
                    chat_history = conv_control.load_chat_history(user_id)
                    print(f"🎯 FORCE RELOADED {len(chat_history)} conversations for user {user_id}")
                    
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

            # ✅ CRITICAL FIX: Immediate file reload dengan proper timing - ENHANCED
            print(f"🔄 IMMEDIATE file reload for authenticated user: {user_id}")
            file_updates = self._immediate_file_reload_for_user(user_id)

            tabs_update = []
            for k in self._tabs.keys():
                if k == "login-tab":
                    tabs_update.append(gr.update(visible=False))
                elif k == "resources-tab":
                    tabs_update.append(gr.update(visible=True))
                elif k == "settings-tab":
                    tabs_update.append(gr.update(visible=True))
                else:
                    tabs_update.append(gr.update(visible=True))

            tabs_update.append(gr.update(selected="chat-tab"))
            tabs_update.append(conversation_update)  # ✅ Add conversation update
            tabs_update.extend(file_updates)  # ✅ Add file updates
            
            print("🚀 Authentication complete - chat tab selected with conversations and files IMMEDIATELY LOADED")
            return tabs_update

        def _immediate_file_reload_for_user(self, user_id):
            """Immediate file reload untuk user - OPTIMIZED untuk login process"""
            print(f"🚀 IMMEDIATE: Reloading files for user: {user_id}")
            
            file_updates = []
            try:
                # ✅ CRITICAL: Add small delay untuk ensure database is ready
                import time
                time.sleep(0.1)  # Very small delay for DB consistency
                
                for index in self.index_manager.indices:
                    if hasattr(index, 'file_index_page'):
                        file_control = index.file_index_page
                        print(f"🔄 IMMEDIATE: Processing index {index.id}")
                        
                        # ✅ CRITICAL: Clear cached data first
                        if hasattr(file_control, '_clear_cached_file_data'):
                            file_control._clear_cached_file_data()
                        
                        # ✅ CRITICAL: Force fresh database query dengan new session
                        with Session(engine) as fresh_session:
                            print(f"🔄 IMMEDIATE: Fresh database query for user {user_id}")
                            
                            # Use fresh session untuk avoid any cache
                            Source = file_control._index._resources["Source"]
                            statement = select(Source)
                            if file_control._index.config.get("private", False):
                                statement = statement.where(Source.user == user_id)
                            
                            # Execute fresh query
                            fresh_results = fresh_session.execute(statement).all()
                            file_list_state = [
                                {
                                    "id": each[0].id,
                                    "name": each[0].name,
                                    "size": file_control.format_size_human_readable(each[0].size),
                                    "tokens": file_control.format_size_human_readable(
                                        each[0].note.get("tokens", "-"), suffix=""
                                    ),
                                    "loader": each[0].note.get("loader", "-"),
                                    "date_created": each[0].date_created.strftime("%Y-%m-%d %H:%M:%S"),
                                }
                                for each in fresh_results
                            ]
                        
                        # Create DataFrame
                        if file_list_state:
                            file_list_df = pd.DataFrame.from_records(file_list_state)
                        else:
                            file_list_df = pd.DataFrame.from_records([{
                                "id": "-", "name": "-", "size": "-", "tokens": "-",
                                "loader": "-", "date_created": "-",
                            }])
                        
                        # Load groups
                        group_list_state, group_list_df = file_control.list_group(user_id, file_list_state)
                        
                        # Update file names for dropdown
                        if file_list_state:
                            file_names = [(item["name"], item["id"]) for item in file_list_state]
                        else:
                            file_names = []
                        
                        print(f"🎯 IMMEDIATE LOADED {len(file_list_state)} files and {len(group_list_state)} groups for index {index.id}")
                        
                        # ✅ CRITICAL: Proper Gradio updates untuk immediate UI refresh
                        file_updates.extend([
                            gr.update(value=file_list_state),  # file_list_state
                            gr.update(value=file_list_df),     # file_list DataFrame
                            gr.update(value=group_list_state), # group_list_state
                            gr.update(value=group_list_df),    # group_list DataFrame
                            gr.update(choices=file_names, value=[])  # group_files dropdown
                        ])
                    else:
                        # Empty updates for indices without file page
                        file_updates.extend([
                            gr.update(value=[]), 
                            gr.update(value=None), 
                            gr.update(value=[]), 
                            gr.update(value=None), 
                            gr.update(choices=[], value=[])
                        ])
                        print(f"❌ File index page not available for index {index.id}")
                        
                print(f"✅ IMMEDIATE file reload completed: {len(file_updates)} updates prepared")
                
            except Exception as e:
                print(f"❌ Error in immediate file reload: {e}")
                import traceback
                traceback.print_exc()
                # Return empty updates on error
                for index in self.index_manager.indices:
                    file_updates.extend([
                        gr.update(value=[]), 
                        gr.update(value=None), 
                        gr.update(value=[]), 
                        gr.update(value=None), 
                        gr.update(choices=[], value=[])
                    ])
            
            return file_updates

        # Add method to main class
        self._immediate_file_reload_for_user = lambda user_id: _immediate_file_reload_for_user(self, user_id)

        # ✅ ENHANCED: Subscribe event dengan conversation dan file loading - COMPREHENSIVE
        signin_outputs = list(self._tabs.values()) + [
            self.tabs,
            self.chat_page.chat_control.conversation  # ✅ Direct conversation update
        ]
        
        # ✅ ADD: File loading outputs untuk setiap index - ENHANCED
        for index in self.index_manager.indices:
            if hasattr(index, 'file_index_page'):
                signin_outputs.extend([
                    index.file_index_page.file_list_state,
                    index.file_index_page.file_list,
                    index.file_index_page.group_list_state,
                    index.file_index_page.group_list,
                    index.file_index_page.group_files
                ])
        
        self.subscribe_event(
            name="onSignIn",
            definition={
                "fn": toggle_login_visibility,
                "inputs": [self.user_id],
                "outputs": signin_outputs,
                "show_progress": "hidden",
            },
        )

        # ✅ ENHANCED: onSignOut event dengan file clearing - COMPREHENSIVE
        signout_outputs = list(self._tabs.values()) + [
            self.tabs,
            self.chat_page.chat_control.conversation
        ]
        
        # ✅ ADD: Clear file outputs untuk setiap index
        for index in self.index_manager.indices:
            if hasattr(index, 'file_index_page'):
                signout_outputs.extend([
                    index.file_index_page.file_list_state,
                    index.file_index_page.file_list,
                    index.file_index_page.group_list_state,
                    index.file_index_page.group_list,
                    index.file_index_page.group_files
                ])
        
        def handle_signout():
            print("🚪 Handling sign out - clearing all data")
            self._clear_user_session_data()
            
            signout_updates = (
                [gr.update(visible=(k == "login-tab")) for k in self._tabs.keys()] +
                [gr.update(selected="login-tab")] +
                [gr.update(choices=[], value=None)]  # Clear conversations
            )
            
            # ✅ ADD: Clear file updates
            for index in self.index_manager.indices:
                if hasattr(index, 'file_index_page'):
                    signout_updates.extend([[], None, [], None, gr.update(choices=[])])  # Clear file lists
            
            return signout_updates
        
        self.subscribe_event(
            name="onSignOut",
            definition={
                "fn": handle_signout,
                "outputs": signout_outputs,
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

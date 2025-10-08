import hashlib

import gradio as gr
from ktem.app import BasePage
from ktem.components import reasonings
from ktem.db.models import Settings, User, engine
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings

KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)


signout_js = """
function(u, c, pw, pwc) {
    removeFromStorage('username');
    removeFromStorage('password');
    return [u, c, pw, pwc];
}
"""


gr_cls_single_value = {
    "text": gr.Textbox,
    "number": gr.Number,
    "checkbox": gr.Checkbox,
}


gr_cls_choices = {
    "dropdown": gr.Dropdown,
    "radio": gr.Radio,
    "checkboxgroup": gr.CheckboxGroup,
}


def render_setting_item(setting_item, value):
    """Render the setting component into corresponding Gradio UI component"""
    kwargs = {
        "label": setting_item.name,
        "value": value,
        "interactive": True,
    }

    if setting_item.component in gr_cls_single_value:
        return gr_cls_single_value[setting_item.component](**kwargs)

    kwargs["choices"] = setting_item.choices

    if setting_item.component in gr_cls_choices:
        return gr_cls_choices[setting_item.component](**kwargs)

    raise ValueError(
        f"Unknown component {setting_item.component}, allowed are: "
        f"{list(gr_cls_single_value.keys()) + list(gr_cls_choices.keys())}.\n"
        f"Setting item: {setting_item}"
    )


class SettingsPage(BasePage):
    """Responsible for allowing the users to customize the application

    **IMPORTANT**: the name and id of the UI setting components should match the
    name of the setting in the `app.default_settings`
    """

    public_events = ["onSignOut"]

    def __init__(self, app):
        """Initiate the page and render the UI"""
        self._app = app

        self._settings_state = app.settings_state
        self._user_id = app.user_id
        self._default_settings = app.default_settings
        self._settings_dict = self._default_settings.flatten()
        self._settings_keys = list(self._settings_dict.keys())

        self._components = {}
        self._reasoning_mode = {}

        # store llms and embeddings components
        self._llms = []
        self._embeddings = []

        # render application page if there are application settings
        self._render_app_tab = False

        if not KH_SSO_ENABLED and self._default_settings.application.settings:
            self._render_app_tab = True

        # render index page if there are index settings (general and/or specific)
        self._render_index_tab = False

        if not KH_SSO_ENABLED:
            if self._default_settings.index.settings:
                self._render_index_tab = True
            else:
                for sig in self._default_settings.index.options.values():
                    if sig.settings:
                        self._render_index_tab = True
                        break

        # render reasoning page if there are reasoning settings
        self._render_reasoning_tab = False

        if not KH_SSO_ENABLED:
            if len(self._default_settings.reasoning.settings) > 1:
                self._render_reasoning_tab = True
            else:
                for sig in self._default_settings.reasoning.options.values():
                    if sig.settings:
                        self._render_reasoning_tab = True
                        break

        self.on_building_ui()

    def on_building_ui(self):
        if not KH_SSO_ENABLED:
            self.setting_save_btn = gr.Button(
                "Save & Close",
                variant="primary",
                elem_classes=["right-button"],
                elem_id="save-setting-btn",
            )
        if self._app.f_user_management:
            with gr.Tab("User settings"):
                self.user_tab()

        self.app_tab()
        self.index_tab()
        self.reasoning_tab()

    def on_subscribe_public_events(self):
        """
        Subscribes to public events related to user management.

        This function is responsible for subscribing to the "onSignIn" event, which is
        triggered when a user signs in. It registers two event handlers for this event.

        The first event handler, "load_setting", is responsible for loading the user's
        settings when they sign in. It takes the user ID as input and returns the
        settings state and a list of component outputs. The progress indicator for this
        event is set to "hidden".

        The second event handler, "get_name", is responsible for retrieving the
        username of the current user. It takes the user ID as input and returns the
        username if it exists, otherwise it returns "___". The progress indicator for
        this event is also set to "hidden".

        Parameters:
            self (object): The instance of the class.

        Returns:
            None
        """
        if self._app.f_user_management:
            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": self.load_setting,
                    "inputs": self._user_id,
                    "outputs": [self._settings_state] + self.components(),
                    "show_progress": "hidden",
                },
            )

            def get_name(user_id):
                name = "Current user: "
                if user_id:
                    with Session(engine) as session:
                        statement = select(User).where(User.id == user_id)
                        result = session.exec(statement).all()
                        if result:
                            return name + result[0].username
                return name + "___"

            self._app.subscribe_event(
                name="onSignIn",
                definition={
                    "fn": get_name,
                    "inputs": self._user_id,
                    "outputs": [self.current_name],
                    "show_progress": "hidden",
                },
            )

    def on_register_events(self):
        if not KH_SSO_ENABLED:
            self.setting_save_btn.click(
                self.save_setting,
                inputs=[self._user_id] + self.components(),
                outputs=self._settings_state,
            ).then(
                lambda: gr.Tabs(selected="chat-tab"),
                outputs=self._app.tabs,
            )
        self._components["reasoning.use"].change(
            self.change_reasoning_mode,
            inputs=[self._components["reasoning.use"]],
            outputs=list(self._reasoning_mode.values()),
            show_progress="hidden",
        )
        if self._app.f_user_management and not KH_SSO_ENABLED:
            self.password_change_btn.click(
                self.change_password,
                inputs=[
                    self._user_id,
                    self.password_change,
                    self.password_change_confirm,
                ],
                outputs=[self.password_change, self.password_change_confirm],
                show_progress="hidden",
            )
            
            # ✅ ENHANCED: Logout dengan proper session clearing dan SIPADU redirect
            onSignOutClick = self.signout.click(
                self.enhanced_logout_handler,
                inputs=[self._user_id],
                outputs=[
                    self._user_id,
                    self.current_name,
                    self.password_change,
                    self.password_change_confirm,
                ],
                show_progress="hidden",
                js=signout_js,
            ).then(
                # Reset all settings to default after logout
                self.load_setting,
                inputs=self._user_id,
                outputs=[self._settings_state] + self.components(),
                show_progress="hidden",
            ).then(
                # Redirect to login tab dengan auto-refresh
                lambda: [
                    gr.update(selected="login-tab"),
                    gr.update(visible=True),   # Login tab visible
                    gr.update(visible=False),  # Chat tab hidden
                    gr.update(visible=False),  # Other tabs hidden
                ],
                outputs=[
                    self._app.tabs,
                    self._app._tabs["login-tab"],
                    self._app._tabs["chat-tab"],
                    self._app._tabs.get("indices-tab", gr.update()),
                ],
                show_progress="hidden"
            ).then(
                # ✅ NEW: JavaScript redirect ke SIPADU setelah logout
                fn=lambda: None,
                js="""
                function() {
                    console.log('🚪 Logout complete, redirecting to SIPADU...');
                    
                    // Get SIPADU URL from config
                    let sipaduUrl = 'http://localhost.sipadubapelitbangbogor/home';
                    if (window.SIPADU_CONFIG && window.SIPADU_CONFIG.HOME_URL) {
                        sipaduUrl = window.SIPADU_CONFIG.HOME_URL;
                    } else if (window.SIPADU_CONFIG && window.SIPADU_CONFIG.API_BASE) {
                        sipaduUrl = window.SIPADU_CONFIG.API_BASE + '/home';
                    }
                    
                    // Show notification
                    if (window.showSipaduNotification) {
                        window.showSipaduNotification('Logout berhasil. Mengarahkan ke SIPADU...', 'success');
                    }
                    
                    // Clear any localStorage
                    localStorage.removeItem('kotaemon_user_session');
                    localStorage.removeItem('current_user_id');
                    
                    // Redirect after short delay
                    setTimeout(() => {
                        console.log('🚀 Redirecting to SIPADU:', sipaduUrl);
                        window.location.href = sipaduUrl;
                    }, 1500);
                }
                """,
            )
            
            # Trigger onSignOut events untuk semua komponen
            for event in self._app.get_event("onSignOut"):
                onSignOutClick = onSignOutClick.then(**event)

    def user_tab(self):
        # user management
        self.current_name = gr.Markdown("Current user: ___")

        if KH_SSO_ENABLED:
            import gradiologin as grlogin

            self.sso_signout = grlogin.LogoutButton("Logout")
        else:
            # ✅ ENHANCED: Proper logout button dengan SIPADU integration
            self.signout = gr.Button("🚪 Logout & Kembali ke SIPADU", variant="stop", size="lg")

            self.password_change = gr.Textbox(
                label="New password", interactive=True, type="password"
            )
            self.password_change_confirm = gr.Textbox(
                label="Confirm password", interactive=True, type="password"
            )
            self.password_change_btn = gr.Button("Change password", interactive=True)

    # ✅ NEW: Enhanced logout handler dengan proper session clearing
    def enhanced_logout_handler(self, user_id):
        """Enhanced logout handler yang clear session dan redirect ke SIPADU"""
        import os
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"🚪 Enhanced logout initiated for user: {user_id}")
        
        try:
            # ✅ NEW: Clear file manager FIRST sebelum clear user data
            self._clear_file_manager_on_logout()
            
            # Clear user session dari semua komponen
            self._clear_all_user_data(user_id)
            
            # Clear environment variables
            for key in ['SIPADU_AUTH_STATUS', 'SIPADU_USER_DATA', 'CURRENT_USER_ID', 'CURRENT_SESSION_TOKEN']:
                if key in os.environ:
                    del os.environ[key]
                    
            logger.info("✅ All user data and session cleared successfully")
            
            # Return values untuk clear UI components
            return None, "Current user: ___", "", ""
            
        except Exception as e:
            logger.exception(f"❌ Error during enhanced logout: {e}")
            return None, "Current user: ___", "", ""
    
    def _clear_file_manager_on_logout(self):
        """Clear file manager khusus untuk logout"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("🗑️ Clearing file manager on logout...")
            
            # Clear file manager untuk semua indices
            if hasattr(self._app, 'index_manager') and self._app.index_manager.indices:
                for index in self._app.index_manager.indices:
                    if hasattr(index, 'file_index_page'):
                        file_page = index.file_index_page
                        
                        # Clear gradio states
                        if hasattr(file_page, 'file_list_state'):
                            file_page.file_list_state.value = []
                        if hasattr(file_page, 'group_list_state'):
                            file_page.group_list_state.value = []
                        if hasattr(file_page, 'group_files'):
                            file_page.group_files.choices = []
                        
                        # Clear cached data
                        if hasattr(file_page, '_clear_cached_file_data'):
                            file_page._clear_cached_file_data()
                            
                        logger.info(f"🗑️ Cleared file manager for index {index.id} on logout")
                        
                logger.info("✅ File manager cleared successfully on logout")
            else:
                logger.warning("❌ No index manager found during logout")
                
        except Exception as e:
            logger.exception(f"❌ Error clearing file manager on logout: {e}")
    
    def _clear_all_user_data(self, user_id):
        """Clear semua data user dari memory dan cache"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Clear file data dari semua indices (sudah di-handle di _clear_file_manager_on_logout)
            
            # Clear chat conversations
            if hasattr(self._app, 'chat_page') and hasattr(self._app.chat_page, 'chat_control'):
                chat_control = self._app.chat_page.chat_control
                if hasattr(chat_control, 'conversation'):
                    chat_control.conversation.value = None
                    chat_control.conversation.choices = []
                logger.info("🗑️ Cleared chat conversations")
                
            # Clear any cached settings
            if hasattr(self._app, 'settings_state'):
                # Reset to default settings
                default_settings = self._app.default_settings.flatten()
                self._app.settings_state.value = default_settings
                logger.info("🗑️ Reset settings to default")
                
            logger.info(f"✅ All user data cleared for user: {user_id}")
            
        except Exception as e:
            logger.exception(f"❌ Error clearing user data: {e}")

    def change_password(self, user_id, password, password_confirm):
        from ktem.pages.resources.user import validate_password

        errors = validate_password(password, password_confirm)
        if errors:
            print(errors)
            gr.Warning(errors)
            return password, password_confirm

        with Session(engine) as session:
            statement = select(User).where(User.id == user_id)
            result = session.exec(statement).all()
            if result:
                user = result[0]
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                user.password = hashed_password
                session.add(user)
                session.commit()
                gr.Info("Password diubah")
            else:
                gr.Warning("User tidak ditemukan")

        return "", ""

    def app_tab(self):
        with gr.Tab("General", visible=self._render_app_tab):
            for n, si in self._default_settings.application.settings.items():
                obj = render_setting_item(si, si.value)
                self._components[f"application.{n}"] = obj
                if si.special_type == "llm":
                    self._llms.append(obj)
                if si.special_type == "embedding":
                    self._embeddings.append(obj)

    def index_tab(self):
        # TODO: double check if we need general
        # with gr.Tab("General"):
        #     for n, si in self._default_settings.index.settings.items():
        #         obj = render_setting_item(si, si.value)
        #         self._components[f"index.{n}"] = obj

        id2name = {k: v.name for k, v in self._app.index_manager.info().items()}
        with gr.Tab("Retrieval settings", visible=self._render_index_tab):
            for pn, sig in self._default_settings.index.options.items():
                name = id2name.get(pn, f"<id {pn}>")
                with gr.Tab(name):
                    for n, si in sig.settings.items():
                        obj = render_setting_item(si, si.value)
                        self._components[f"index.options.{pn}.{n}"] = obj
                        if si.special_type == "llm":
                            self._llms.append(obj)
                        if si.special_type == "embedding":
                            self._embeddings.append(obj)

    def reasoning_tab(self):
        with gr.Tab("Reasoning settings", visible=self._render_reasoning_tab):
            with gr.Group():
                for n, si in self._default_settings.reasoning.settings.items():
                    if n == "use":
                        continue
                    obj = render_setting_item(si, si.value)
                    self._components[f"reasoning.{n}"] = obj
                    if si.special_type == "llm":
                        self._llms.append(obj)
                    if si.special_type == "embedding":
                        self._embeddings.append(obj)

            gr.Markdown("### Reasoning-specific settings")
            self._components["reasoning.use"] = render_setting_item(
                self._default_settings.reasoning.settings["use"],
                self._default_settings.reasoning.settings["use"].value,
            )

            for idx, (pn, sig) in enumerate(
                self._default_settings.reasoning.options.items()
            ):
                with gr.Group(
                    visible=idx == 0,
                    elem_id=pn,
                ) as self._reasoning_mode[pn]:
                    reasoning = reasonings.get(pn, None)
                    if reasoning is None:
                        gr.Markdown("**Name**: Description")
                    else:
                        info = reasoning.get_info()
                        gr.Markdown(f"**{info['name']}**: {info['description']}")
                    for n, si in sig.settings.items():
                        obj = render_setting_item(si, si.value)
                        self._components[f"reasoning.options.{pn}.{n}"] = obj
                        if si.special_type == "llm":
                            self._llms.append(obj)
                        if si.special_type == "embedding":
                            self._embeddings.append(obj)

    def change_reasoning_mode(self, value):
        output = []
        for each in self._reasoning_mode.values():
            if value == each.elem_id:
                output.append(gr.update(visible=True))
            else:
                output.append(gr.update(visible=False))
        return output

    def load_setting(self, user_id=None):
        settings = self._settings_dict
        with Session(engine) as session:
            statement = select(Settings).where(Settings.user == user_id)
            result = session.exec(statement).all()
            if result:
                settings = result[0].setting

        output = [settings]
        output += tuple(settings[name] for name in self.component_names())
        return output

    def save_setting(self, user_id: int, *args):
        """Save the setting to disk and persist the setting to session state

        Args:
            user_id: the user id
            args: all the values from the settings
        """
        setting = {key: value for key, value in zip(self.component_names(), args)}
        if user_id is None:
            gr.Warning("Need to login before saving settings")
            return setting

        with Session(engine) as session:
            statement = select(Settings).where(Settings.user == user_id)
            try:
                user_setting = session.exec(statement).one()
            except Exception:
                user_setting = Settings()
                user_setting.user = user_id
            user_setting.setting = setting
            session.add(user_setting)
            session.commit()

        gr.Info("Pengaturan disimpan")
        return setting

    def components(self) -> list:
        """Get the setting components"""
        output = []
        for name in self._settings_keys:
            output.append(self._components[name])
        return output

    def component_names(self):
        """Get the setting components"""
        return self._settings_keys

    def _on_app_created(self):
        if not self._app.f_user_management:
            self._app.app.load(
                self.load_setting,
                inputs=self._user_id,
                outputs=[self._settings_state] + self.components(),
                show_progress="hidden",
            )

        def update_llms():
            from ktem.llms.manager import llms

            if llms._default:
                llm_choices = [(f"{llms._default} (default)", "")]
            else:
                llm_choices = [("(random)", "")]
            llm_choices += [(_, _) for _ in llms.options().keys()]
            return gr.update(choices=llm_choices)

        def update_embeddings():
            from ktem.embeddings.manager import embedding_models_manager

            if embedding_models_manager._default:
                emb_choices = [(f"{embedding_models_manager._default} (default)", "")]
            else:
                emb_choices = [("(random)", "")]
            emb_choices += [(_, _) for _ in embedding_models_manager.options().keys()]
            return gr.update(choices=emb_choices)

        for llm in self._llms:
            self._app.app.load(
                update_llms,
                inputs=[],
                outputs=[llm],
                show_progress="hidden",
            )
        for emb in self._embeddings:
            self._app.app.load(
                update_embeddings,
                inputs=[],
                outputs=[emb],
                show_progress="hidden",
            )

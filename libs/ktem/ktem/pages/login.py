import hashlib
import os
import json
import requests
import logging
import gradio as gr
from ktem.app import BasePage
from ktem.db.models import User, engine
from ktem.pages.resources.user import create_user
from sqlmodel import Session, select
from dotenv import load_dotenv

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)

load_dotenv()
SIPADU_API_BASE = os.getenv("SIPADU_API_BASE", "http://localhost.sipadubapelitbangbogor")

class LoginPage(BasePage):

    public_events = ["onSignIn"]

    def __init__(self, app):
        self._app = app
        self._user_created = False
        self.on_building_ui()

    def validate_sipadu_token(self, token):
        """Validate token with SIPADU API"""
        if not token:
            logger.warning("Token validation failed: No token provided")
            return False, {}, "No token provided"
        
        try:
            sipadu_endpoint = f"{SIPADU_API_BASE}/api/validate-token"
            
            logger.info(f"🔐 Validating token with SIPADU: {sipadu_endpoint}")
            logger.debug(f"Token length: {len(token)}")
            
            response = requests.get(
                sipadu_endpoint,
                params={'token': token},
                headers={'Accept': 'application/json'},
                timeout=10
            )
            
            logger.info(f"📡 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == True:
                    user_info = {
                        'user_id': data.get('user_id'),
                        'username': data.get('username'),
                        'nama_lengkap': data.get('nama_lengkap'),
                        'email': data.get('email'),
                        'unit_kerja': data.get('unit_kerja'),
                        'user_id_role': data.get('user_id_role')
                    }
                    logger.info(f"Token validated successfully for user: {user_info.get('username')}")
                    return True, user_info, None
                else:
                    error_msg = data.get('message', 'Token validation failed')
                    logger.warning(f"Token validation failed: {error_msg}")
                    return False, {}, error_msg
            else:
                error_msg = f"SIPADU API error: {response.status_code}"
                logger.error(f"SIPADU API error: {response.status_code}")
                return False, {}, error_msg
                
        except Exception as e:
            error_msg = f"Connection error to SIPADU: {str(e)}"
            logger.exception("Exception occurred during token validation")
            return False, {}, error_msg

    def on_building_ui(self):
        """Build UI with modern styling and SIPADU logo"""
        
        # Checking/Loading UI
        with gr.Column(visible=True, elem_classes=["login-container"]) as self.checking_ui:
            gr.HTML('<div class="login-logo"></div>')
            gr.Markdown("# 🔄 Memeriksa Autentikasi...", elem_classes=["login-title"])
            gr.Markdown("Optimalkan data Anda dengan kecerdasan buatan SIPADU", elem_classes=["login-tagline"])
            gr.Markdown("Silakan tunggu, kami sedang memverifikasi akses Anda...", elem_classes=["login-subtitle"])
            self.status_display = gr.Markdown("Status: Memulai...", elem_classes=["login-status"])
        
        # Success UI - Login berhasil
        with gr.Column(visible=False, elem_classes=["login-container"]) as self.success_ui:
            gr.HTML('<div class="login-logo"></div>')
            gr.Markdown("# Selamat Datang di SIPADU AI Tools", elem_classes=["login-title"])
            gr.Markdown("Optimalkan data Anda dengan kecerdasan buatan SIPADU", elem_classes=["login-tagline"])
            with gr.Column(elem_classes=["login-welcome-container"]):
                self.welcome_message = gr.Markdown("", elem_classes=["login-welcome-message"])
            self.btn_login = gr.Button(
                "🚀 Mulai Gunakan AI Tools", 
                variant="primary", 
                size="lg",
                elem_classes=["login-button"]
            )
        
        # Development Mode UI
        with gr.Column(visible=False, elem_classes=["login-container"]) as self.dev_ui:
            gr.HTML('<div class="login-logo"></div>')
            gr.Markdown("# 🔧 Development Mode", elem_classes=["login-title"])
            gr.Markdown("Optimalkan data Anda dengan kecerdasan buatan SIPADU", elem_classes=["login-tagline"])
            with gr.Column(elem_classes=["dev-login-container"]):
                gr.Markdown("## Mode Pengembangan", elem_classes=["dev-login-title"])
                gr.Markdown("Sistem dalam mode pengembangan - gunakan kredensial dev:", elem_classes=["dev-login-note"])
                
                with gr.Column(elem_classes=["login-form-group"]):
                    self.usn = gr.Textbox(
                        label="Username", 
                        value="dev_user", 
                        interactive=True,
                        elem_classes=["login-form-input"]
                    )
                    self.pwd = gr.Textbox(
                        label="Password", 
                        type="password", 
                        value="dev_pass", 
                        interactive=True,
                        elem_classes=["login-form-input"]
                    )
                    
                self.btn_dev_login = gr.Button(
                    "🚀 Mulai Gunakan AI Tools", 
                    variant="primary",
                    elem_classes=["login-button"]
                )
        
        # Failed/Error UI
        with gr.Column(visible=False, elem_classes=["login-container"]) as self.failed_ui:
            gr.HTML('<div class="login-logo"></div>')
            gr.Markdown("# ⚠️ Autentikasi Gagal", elem_classes=["login-title"])
            gr.Markdown("Optimalkan data Anda dengan kecerdasan buatan SIPADU", elem_classes=["login-tagline"])
            
            with gr.Column(elem_classes=["login-error-container"]):
                gr.Markdown("## Terjadi Kesalahan", elem_classes=["login-error-title"])
                self.error_message = gr.Markdown("", elem_classes=["login-error-message"])
            
            with gr.Row(elem_classes=["login-button-group"]):
                self.retry_btn = gr.Button(
                    "🔄 Coba Lagi", 
                    variant="primary",
                    elem_classes=["login-button"]
                )
                gr.Button(
                    "Login SIPADU", 
                    link=SIPADU_API_BASE,
                    variant="secondary",
                    elem_classes=["login-secondary-button"]
                )
        
        # No Token UI - Perlu login ke SIPADU
        with gr.Column(visible=False, elem_classes=["login-container"]) as self.no_token_ui:
            gr.HTML('<div class="login-logo"></div>')
            gr.Markdown("# 🚫 Akses Ditolak", elem_classes=["login-title"])
            gr.Markdown("Optimalkan data Anda dengan kecerdasan buatan SIPADU", elem_classes=["login-tagline"])
            
            with gr.Column(elem_classes=["login-info-box"]):
                gr.Markdown("## Mohon Login Terlebih Dahulu", elem_classes=["login-info-title"])
                gr.Markdown("""
                Halo! Sepertinya Anda belum login ke SIPADU. Untuk melanjutkan, ikuti langkah-langkah berikut:
                
                **Langkah 1:** Login ke SIPADU terlebih dahulu  
                **Langkah 2:** Klik menu "AI Tools" di dashboard SIPADU  
                **Langkah 3:** Anda akan diarahkan otomatis ke halaman ini
                
                ### 🔐 Keamanan
                Kami menggunakan sistem Single Sign-On (SSO) untuk menjaga keamanan data Anda.
                """, elem_classes=["login-info-content"])
            
            gr.Button(
                "🔗 Kembali ke SIPADU", 
                link=f"{SIPADU_API_BASE}/auth/login",
                variant="primary",
                size="lg",
                elem_classes=["login-button"]
            )
        
        # Store UI components for visibility control
        self.ui_components = {
            'checking': self.checking_ui,
            'success': self.success_ui,
            'dev': self.dev_ui,
            'failed': self.failed_ui,
            'no_token': self.no_token_ui
        }
        
        # State components - FIXED: gunakan gr.State() dengan value default
        self.auth_status = gr.State(value="CHECKING")
        self.user_data = gr.State(value={})  # Pastikan ada value default
        self.auth_error = gr.State(value="")
        self.current_user_data = gr.State(value={})  # Tambahan untuk simpan data user

    def perform_auth_check(self, request: gr.Request):
        """Perform authentication check - ENHANCED dengan token change detection"""
        logger.info("🔄 Enhanced authentication check with session detection")
        
        # Extract token dari query parameters
        token = None
        if request.query_params:
            token = request.query_params.get('token')
            logger.debug(f"Query params: {dict(request.query_params)}")
            logger.debug(f"Token found: {token[:50] + '...' if token else 'None'}")
        
        # ✅ ENHANCED: Check for existing session dan compare dengan new token
        current_session_token = os.getenv('CURRENT_SESSION_TOKEN', '')
        current_user_id = os.getenv('CURRENT_USER_ID', '')
        
        # Development mode
        if os.getenv('KOTAEMON_DEV_MODE', '').lower() == 'true':
            logger.info("Development mode activated")
            user_data = {'username': 'dev_user', 'nama_lengkap': 'Development User', 'user_id': 'dev_1'}
            return 'DEV_MODE', user_data, "DEV MODE", user_data
        
        if not token:
            logger.warning("No token found")
            # ✅ ENHANCED: Clear existing session jika tidak ada token + trigger logout
            if current_session_token:
                logger.info("🗑️ Clearing existing session - no token provided")
                self._trigger_complete_logout()
            return 'NO_TOKEN', {}, "Token tidak ditemukan", {}
        
        # ✅ ENHANCED: Detect token change (user switch) dengan immediate logout
        if current_session_token and current_session_token != token:
            logger.info(f"🔄 USER SWITCH DETECTED! Previous: {current_user_id}, New token: {token[:20]}...")
            logger.info("🚪 Triggering complete logout for previous user")
            self._trigger_complete_logout()
            # Add delay untuk ensure logout is complete
            import time
            time.sleep(1.0)
        
        # Validate token
        logger.info("Validating token with SIPADU...")
        is_valid, user_data, error_msg = self.validate_sipadu_token(token)
        
        if is_valid:
            logger.info(f"Authentication SUCCESS for: {user_data.get('nama_lengkap')}")
            
            # ✅ NEW: Store session info untuk future comparison
            os.environ['CURRENT_SESSION_TOKEN'] = token
            os.environ['CURRENT_USER_ID'] = f"sipadu_{user_data.get('user_id')}"
            
            return 'SUCCESS', user_data, None, user_data
        else:
            logger.warning(f"Authentication FAILED: {error_msg}")
            self._trigger_complete_logout()
            return 'FAILED', {}, error_msg, {}

    def update_ui_based_on_auth(self, auth_status, user_data, error_msg, current_user_data):
        """Update UI berdasarkan status autentikasi - ENHANCED WELCOME VERSION"""
        logger.info(f"🔄 update_ui_based_on_auth called: {auth_status}")
        logger.debug(f"📦 User data received: {user_data}")
        
        # Default: hide all, show based on status
        visibility_updates = {
            'checking': False,
            'success': False, 
            'dev': False,
            'failed': False,
            'no_token': False
        }
        
        if auth_status == 'SUCCESS':
            visibility_updates['success'] = True
            welcome_text = f"""
            ### 🎉 Halo, **{user_data.get('nama_lengkap', 'User')}**!

            Selamat datang kembali di **SIPADU AI Tools**. Informasi akun Anda:

            **👤 Username:** `{user_data.get('username', '-')}`  
            **✉️ Email:** `{user_data.get('email', '-')}`

            Klik tombol di bawah untuk memulai!
            """
            return [
                gr.update(visible=visibility_updates['checking']),
                gr.update(visible=visibility_updates['success']),
                gr.update(visible=visibility_updates['dev']),
                gr.update(visible=visibility_updates['failed']),
                gr.update(visible=visibility_updates['no_token']),
                welcome_text,
                "Status: Autentikasi berhasil! ✅",
                user_data
            ]
            
        elif auth_status == 'DEV_MODE':
            visibility_updates['dev'] = True
            return [
                gr.update(visible=visibility_updates['checking']),
                gr.update(visible=visibility_updates['success']),
                gr.update(visible=visibility_updates['dev']),
                gr.update(visible=visibility_updates['failed']),
                gr.update(visible=visibility_updates['no_token']),
                "",
                "Status: Mode Development 🔧",
                user_data
            ]
            
        elif auth_status == 'FAILED':
            visibility_updates['failed'] = True
            error_display = f"""
            **Error:** {error_msg}

            ### 🔧 Panduan Troubleshooting:
            - Pastikan SIPADU sedang berjalan dan dapat diakses
            - Periksa koneksi jaringan Anda  
            - Coba login ulang di SIPADU terlebih dahulu
            - Hapus cache browser dan cookies
            - Jika masalah berlanjut, hubungi administrator sistem
            """
            return [
                gr.update(visible=visibility_updates['checking']),
                gr.update(visible=visibility_updates['success']),
                gr.update(visible=visibility_updates['dev']),
                gr.update(visible=visibility_updates['failed']),
                gr.update(visible=visibility_updates['no_token']),
                error_display,
                f"Status: Autentikasi gagal - {error_msg} ❌",
                {}
            ]
            
        else:  # NO_TOKEN or CHECKING
            visibility_updates['no_token'] = True
            return [
                gr.update(visible=visibility_updates['checking']),
                gr.update(visible=visibility_updates['success']),
                gr.update(visible=visibility_updates['dev']),
                gr.update(visible=visibility_updates['failed']),
                gr.update(visible=visibility_updates['no_token']),
                "",
                "Status: Token tidak ditemukan 🚫",
                {}
            ]

    def create_or_get_user(self, user_data):
        """Create user in database if not exists"""
        if not user_data or not user_data.get('user_id'):
            logger.warning("Invalid user data for creation")
            return None
            
        user_id = f"sipadu_{user_data.get('user_id')}"
        username = user_data.get('username', 'sipadu_user')
        
        logger.info(f"Checking/Creating user: {username} (ID: {user_id})")
        
        with Session(engine) as session:
            # Check if user already exists
            stmt = select(User).where(User.id == user_id)
            result = session.exec(stmt).first()

            if result:
                logger.info(f"User already exists: {username}")
                return user_id
            else:
                try:
                    # Create new user
                    create_user(
                        usn=username,
                        pwd="",  # No password for SSO users
                        user_id=user_id,
                        is_admin=False,
                    )
                    logger.info(f"Created new SIPADU user: {username}")
                    self._user_created = True
                    return user_id
                except Exception as e:
                    logger.exception("Error creating user")
                    return None

    def manual_login_handler(self, current_user_data):
        """Handler untuk manual login button - ENHANCED VERSION dengan file refresh"""
        logger.info("Manual login button clicked")
        logger.debug(f"Current user data: {current_user_data}")
        
        if current_user_data and current_user_data.get('user_id'):
            try:
                user_id = self.create_or_get_user(current_user_data)
                if user_id:
                    logger.info(f"Manual login successful for user: {current_user_data.get('nama_lengkap')}")
                    
                    # ✅ NEW: Trigger file manager refresh setelah login
                    self._trigger_file_manager_refresh(user_id)
                    
                    # Use Gradio's built-in notification system
                    gr.Info(f"🎉 Selamat datang, {current_user_data.get('nama_lengkap')}!")
                    
                    # Load chat history using existing chat_control
                    try:
                        if hasattr(self._app, 'chat_page') and hasattr(self._app.chat_page, 'chat_control'):
                            chat_control = self._app.chat_page.chat_control
                            chat_history = chat_control.load_chat_history(user_id)
                            logger.info(f"✅ Loaded {len(chat_history)} chat histories for user {user_id}")
                            return user_id, "Login berhasil!", chat_history
                        else:
                            logger.warning("Chat control not available yet")
                            return user_id, "Login berhasil!", []
                    except Exception as e:
                        logger.warning(f"Could not load chat history: {e}")
                        gr.Warning("Chat history tidak dapat dimuat, namun login berhasil")
                        return user_id, "Login berhasil!", []
                else:
                    gr.Error("Gagal membuat atau mengakses akun pengguna")
                    return None, "Gagal membuat user", []
            except Exception as e:
                logger.exception("Error during manual login")
                gr.Error(f"Terjadi kesalahan saat login: {str(e)}")
                return None, "Error saat login", []
        else:
            logger.warning("No valid user data found")
            gr.Warning("Data pengguna tidak valid. Silakan coba login ulang.")
            return None, "Data user tidak valid", []

    def _trigger_file_manager_refresh(self, user_id):
        """Trigger file manager refresh untuk user baru - CRITICAL FIX"""
        logger.info(f"🔄 Triggering file manager refresh for user: {user_id}")
        
        try:
            # ✅ 1. Clear all file manager cache first
            self._clear_all_file_manager_cache()
            
            # ✅ 2. Force refresh each index file manager
            if hasattr(self._app, 'index_manager') and self._app.index_manager.indices:
                for index in self._app.index_manager.indices:
                    if hasattr(index, 'file_index_page'):
                        file_page = index.file_index_page
                        logger.info(f"🔄 Refreshing files for index {index.id}")
                        
                        # Clear cached data
                        if hasattr(file_page, '_clear_cached_file_data'):
                            file_page._clear_cached_file_data()
                        
                        # Force reload files and groups from database
                        try:
                            file_list_state, file_list_df = file_page.list_file(user_id)
                            group_list_state, group_list_df = file_page.list_group(user_id, file_list_state)
                            file_names_update = file_page.list_file_names(file_list_state)
                            
                            # Update the actual gradio components
                            if hasattr(file_page, 'file_list_state'):
                                file_page.file_list_state.value = file_list_state
                            if hasattr(file_page, 'file_list'):
                                file_page.file_list.value = file_list_df
                            if hasattr(file_page, 'group_list_state'):
                                file_page.group_list_state.value = group_list_state
                            if hasattr(file_page, 'group_list'):
                                file_page.group_list.value = group_list_df
                            if hasattr(file_page, 'group_files'):
                                if file_list_state:
                                    file_names = [(item["name"], item["id"]) for item in file_list_state]
                                else:
                                    file_names = []
                                file_page.group_files.choices = file_names
                            
                            logger.info(f"✅ Refreshed {len(file_list_state)} files and {len(group_list_state)} groups for index {index.id}")
                        except Exception as e:
                            logger.error(f"❌ Error refreshing files for index {index.id}: {e}")
                    
                logger.info("✅ File manager refresh completed for all indices")
            else:
                logger.warning("❌ No index manager or indices found")
                
        except Exception as e:
            logger.exception(f"❌ Error in file manager refresh: {e}")

    def _clear_all_file_manager_cache(self):
        """Clear semua cache file manager"""
        logger.info("🗑️ Clearing all file manager cache...")
        
        try:
            if hasattr(self._app, 'index_manager') and self._app.index_manager.indices:
                for index in self._app.index_manager.indices:
                    if hasattr(index, 'file_index_page'):
                        file_page = index.file_index_page
                        
                        # Clear all state values
                        if hasattr(file_page, 'file_list_state'):
                            file_page.file_list_state.value = []
                        if hasattr(file_page, 'group_list_state'):
                            file_page.group_list_state.value = []
                        
                        # Clear cached attributes
                        cache_attrs = ['_cached_file_data', '_cached_group_data', '_file_cache', '_group_cache']
                        for attr in cache_attrs:
                            if hasattr(file_page, attr):
                                delattr(file_page, attr)
                        
                        logger.info(f"🗑️ Cleared cache for index {index.id}")
                        
            logger.info("✅ All file manager cache cleared")
        except Exception as e:
            logger.exception(f"❌ Error clearing file manager cache: {e}")

    def _trigger_complete_logout(self):
        """Trigger complete logout dengan event dan clearing - ENHANCED"""
        logger.info("🚪 Triggering COMPLETE logout process...")
        
        try:
            # ✅ 1. Clear file manager cache FIRST
            self._clear_all_file_manager_cache()
            
            # ✅ 2. Clear environment variables
            for key in ['CURRENT_SESSION_TOKEN', 'CURRENT_USER_ID', 'SIPADU_AUTH_STATUS', 'SIPADU_USER_DATA']:
                if key in os.environ:
                    del os.environ[key]
            
            # ✅ 3. Clear localStorage via JavaScript
            self._inject_clear_localStorage_js()
            
            # ✅ 4. Trigger onSignOut event untuk clear semua komponen
            if hasattr(self._app, 'user_id'):
                # Set user_id to None untuk trigger clearing
                old_user_id = getattr(self._app.user_id, 'value', None)
                self._app.user_id.value = None
                logger.info(f"🗑️ Set user_id from {old_user_id} to None")
                
                # ✅ 5. Manually trigger onSignOut event
                self._manual_trigger_signout_events()
            
            # ✅ 6. Clear cached data di aplikasi
            self._clear_all_application_cache()
                    
            logger.info("✅ Complete logout process finished")
            
        except Exception as e:
            logger.exception(f"❌ Error in complete logout: {e}")

    def _clear_all_cached_data(self):
        """Clear all cached data from previous user sessions"""
        logger.info("🗑️ Clearing all cached data from previous sessions")
        
        try:
            # Clear any cached file data in indices
            for index in self._app.index_manager.indices:
                if hasattr(index, 'file_index_page'):
                    # Reset internal states if they exist
                    file_page = index.file_index_page
                    if hasattr(file_page, 'file_list_state'):
                        file_page.file_list_state.value = []
                    if hasattr(file_page, 'group_list_state'):
                        file_page.group_list_state.value = []
                        
            # Clear chat history cache if exists
            if hasattr(self._app, 'chat_page') and hasattr(self._app.chat_page, 'chat_control'):
                chat_control = self._app.chat_page.chat_control
                # Reset conversation state
                if hasattr(chat_control, 'conversation'):
                    chat_control.conversation.value = None
                    
        except Exception as e:
            logger.exception(f"❌ Error clearing cached data: {e}")

    def on_register_events(self):
        """Register events - ENHANCED VERSION dengan conversation dan file loading"""
        logger.info("Registering events...")
        
        # TRIGGER AUTH CHECK ON PAGE LOAD
        self._app.app.load(
            fn=self.perform_auth_check,
            inputs=[],
            outputs=[self.auth_status, self.user_data, self.auth_error, self.current_user_data],
            show_progress="hidden",
            queue=False
        ).then(
            fn=self.update_ui_based_on_auth,
            inputs=[self.auth_status, self.user_data, self.auth_error, self.current_user_data],
            outputs=[
                self.checking_ui,
                self.success_ui, 
                self.dev_ui,
                self.failed_ui,
                self.no_token_ui,
                self.welcome_message,
                self.status_display,
                self.current_user_data
            ],
            show_progress="hidden",
            queue=False
        )
        
        # ✅ ENHANCED: Manual login dengan proper conversation dan file loading
        login_outputs = list(self._app._tabs.values()) + [
            self._app.tabs, 
            self._app.chat_page.chat_control.conversation  # ✅ DIRECT conversation update
        ]
        
        # ✅ ADD: File loading outputs untuk setiap index - ENHANCED
        for index in self._app.index_manager.indices:
            if hasattr(index, 'file_index_page'):
                login_outputs.extend([
                    index.file_index_page.file_list_state,
                    index.file_index_page.file_list,
                    index.file_index_page.group_list_state,
                    index.file_index_page.group_list,
                    index.file_index_page.group_files
                ])
        
        self.btn_login.click(
            fn=self.manual_login_handler,
            inputs=[self.current_user_data],
            outputs=[self._app.user_id, self.status_display, gr.State()],
            show_progress="hidden"
        ).then(
            fn=self.complete_login_process,
            inputs=[self._app.user_id, self.status_display, gr.State()],
            outputs=login_outputs,
            show_progress="hidden"
        ).then(
            # ✅ CRITICAL: Trigger onSignIn event AFTER everything is set up
            fn=lambda user_id: user_id,
            inputs=[self._app.user_id],
            outputs=[self._app.user_id],
            show_progress="hidden"
        ).success(
            # ✅ TRIGGER: Manual event trigger untuk memastikan conversation reload
            fn=self.trigger_conversation_reload,
            inputs=[self._app.user_id],
            outputs=[],
            show_progress="hidden"
        )
        
        # Retry button
        self.retry_btn.click(
            fn=lambda: gr.update(visible=True),
            outputs=[self.checking_ui],
            show_progress="hidden"
        ).then(
            fn=self.perform_auth_check,
            inputs=[],
            outputs=[self.auth_status, self.user_data, self.auth_error, self.current_user_data],
            show_progress="hidden"
        ).then(
            fn=self.update_ui_based_on_auth,
            inputs=[self.auth_status, self.user_data, self.auth_error, self.current_user_data],
            outputs=[
                self.checking_ui,
                self.success_ui,
                self.dev_ui,
                self.failed_ui,
                self.no_token_ui,
                self.welcome_message,
                self.status_display,
                self.current_user_data
            ],
            show_progress="hidden"
        )
        
        # Dev mode login
        self.btn_dev_login.click(
            fn=self.dev_login,
            inputs=[self.usn, self.pwd],
            outputs=[self._app.user_id],
            show_progress="hidden"
        ).then(
            fn=lambda user_id: (user_id, "Dev login successful") if user_id else (None, "Dev login failed"),
            inputs=[self._app.user_id],
            outputs=[self._app.user_id, self.status_display],
            show_progress="hidden"
        ).then(
            fn=self.complete_login_process,
            inputs=[self._app.user_id, self.status_display],
            outputs=[self._app.tabs],
            show_progress="hidden"
        )

    def dev_login(self, usn, pwd):
        """Development mode login"""
        if usn == "dev_user" and pwd == "dev_pass":
            user_id = "dev_user_1"
            
            with Session(engine) as session:
                stmt = select(User).where(User.id == user_id)
                result = session.exec(stmt).first()
                if not result:
                    create_user(
                        usn=usn,
                        pwd="",
                        user_id=user_id,
                        is_admin=True
                    )
                    logger.info("Development user created")
            logger.info("Development login successful")
            return user_id
        else:
            logger.warning("Development login failed")
            return None

    def trigger_conversation_reload(self, user_id):
        """Manually trigger conversation reload after login - FIXED VERSION"""
        if user_id and hasattr(self._app, 'chat_page'):
            logger.info(f"🔄 Manually triggering conversation reload for user: {user_id}")
            try:
                # ✅ FIXED: Use existing chat_control instance
                chat_control = self._app.chat_page.chat_control
                chat_history = chat_control.load_chat_history(user_id)
                logger.info(f"✅ Manual reload: {len(chat_history)} conversations loaded")
                
                # ✅ FIXED: Update conversation dropdown properly via gradio update
                # Don't directly modify .choices and .value as they may not work
                logger.info("🎯 Conversation history loaded and ready for display")
                
            except Exception as e:
                logger.exception(f"❌ Manual conversation reload failed: {e}")
        return user_id

    def _inject_clear_localStorage_js(self):
        """Inject JavaScript untuk clear localStorage"""
        try:
            # This will be executed on next page interaction
            clear_js = """
            console.log('🗑️ Clearing localStorage for user switch...');
            localStorage.removeItem('kotaemon_user_session');
            localStorage.removeItem('current_user_id');
            localStorage.removeItem('chat_history');
            localStorage.removeItem('file_cache');
            localStorage.removeItem('user_settings');
            localStorage.removeItem('current_session_token');
            sessionStorage.clear();
            console.log('✅ localStorage cleared');
            """
            # Store in a global variable that can be accessed by JavaScript
            if not hasattr(self, '_pending_js'):
                self._pending_js = []
            self._pending_js.append(clear_js)
            logger.info("📝 Scheduled localStorage clearing via JavaScript")
        except Exception as e:
            logger.exception(f"❌ Error injecting localStorage clear JS: {e}")

    def _manual_trigger_signout_events(self):
        """Manually trigger onSignOut events untuk semua komponen"""
        try:
            logger.info("🔄 Manually triggering onSignOut events...")
            
            # Get all onSignOut events
            signout_events = self._app.get_event("onSignOut")
            logger.info(f"📋 Found {len(signout_events)} onSignOut events to trigger")
            
            # Trigger each event
            for i, event in enumerate(signout_events):
                try:
                    if 'fn' in event:
                        event_fn = event['fn']
                        if callable(event_fn):
                            logger.info(f"🔄 Triggering onSignOut event {i+1}/{len(signout_events)}")
                            # Call the function (most signout functions don't need inputs)
                            event_fn()
                except Exception as e:
                    logger.exception(f"❌ Error triggering onSignOut event {i+1}: {e}")
                    
            logger.info("✅ Finished triggering onSignOut events")
            
        except Exception as e:
            logger.exception(f"❌ Error in manual signout trigger: {e}")

    def _clear_all_application_cache(self):
        """Clear semua cached data dari aplikasi - COMPREHENSIVE"""
        logger.info("🗑️ Clearing ALL application cache...")
        
        try:
            # ✅ 1. Clear file data dari semua indices
            if hasattr(self._app, 'index_manager'):
                for index in self._app.index_manager.indices:
                    if hasattr(index, 'file_index_page'):
                        file_page = index.file_index_page
                        if hasattr(file_page, '_clear_cached_file_data'):
                            file_page._clear_cached_file_data()
                        if hasattr(file_page, 'file_list_state'):
                            file_page.file_list_state.value = []
                        if hasattr(file_page, 'group_list_state'):
                            file_page.group_list_state.value = []
                        logger.info(f"🗑️ Cleared cache for index {index.id}")

            # ✅ 2. Clear chat data
            if hasattr(self._app, 'chat_page') and hasattr(self._app.chat_page, 'chat_control'):
                chat_control = self._app.chat_page.chat_control
                if hasattr(chat_control, 'conversation'):
                    chat_control.conversation.value = None
                    chat_control.conversation.choices = []
                logger.info("🗑️ Cleared chat conversations")
                
            # ✅ 3. Clear settings
            if hasattr(self._app, 'settings_state'):
                # Reset to default settings
                try:
                    default_settings = self._app.default_settings.flatten()
                    self._app.settings_state.value = default_settings
                    logger.info("🗑️ Reset settings to default")
                except Exception as e:
                    logger.warning(f"Could not reset settings: {e}")

            # ✅ 4. Clear any other cached states
            cached_attributes = ['_cached_data', '_user_cache', '_session_cache']
            for attr in cached_attributes:
                if hasattr(self._app, attr):
                    delattr(self._app, attr)
                    
            logger.info("✅ Application cache clearing completed")
            
        except Exception as e:
            logger.exception(f"❌ Error clearing application cache: {e}")

    def complete_login_process(self, user_id, status_msg, chat_history_list=None):
        """Complete login process dengan proper data loading"""
        logger.info(f"Complete login process called - User: {user_id}, Status: {status_msg}")
        
        if user_id:
            logger.info(f"Login successful, switching to chat tab for user: {user_id}")
            
            # ✅ CRITICAL FIX: Set user_id FIRST sebelum triggering events
            self._app.user_id.value = user_id
            
            # ✅ ENHANCED: Clear any existing cached data first
            self._clear_all_cached_data()
            
            # ✅ ENHANCED: Load chat history using existing chat_control (no new instance)
            try:
                if hasattr(self._app, 'chat_page') and hasattr(self._app.chat_page, 'chat_control'):
                    chat_control = self._app.chat_page.chat_control
                    chat_history = chat_control.load_chat_history(user_id)
                    logger.info(f"✅ Loaded {len(chat_history)} conversations for user {user_id}")
                    
                    # Auto-select latest conversation if available
                    latest_conv_id = chat_history[0][1] if chat_history else None
                    logger.info(f"🎯 Auto-selecting conversation: {latest_conv_id}")
                else:
                    logger.warning("Chat control not available during login process")
                    chat_history = []
                    latest_conv_id = None
                
            except Exception as e:
                logger.exception(f"❌ Error loading chat history: {e}")
                chat_history = []
                latest_conv_id = None
            
            # ✅ CRITICAL FIX: Force reload file list untuk setiap index yang ada dengan immediate update
            file_updates = []
            try:
                for index in self._app.index_manager.indices:
                    if hasattr(index, 'file_index_page'):
                        file_control = index.file_index_page
                        
                        # ✅ NEW: Force clear cache first
                        if hasattr(file_control, '_clear_cached_file_data'):
                            file_control._clear_cached_file_data()
                        
                        # ✅ CRITICAL: Force fresh database query untuk user ini
                        logger.info(f"🔄 Force loading files for user {user_id} in index {index.id}")
                        file_list_state, file_list_df = file_control.list_file(user_id, "")
                        logger.info(f"✅ FORCE LOADED {len(file_list_state)} files for index {index.id}")
                        
                        # ✅ CRITICAL: Force fresh group query
                        group_list_state, group_list_df = file_control.list_group(user_id, file_list_state)
                        logger.info(f"✅ FORCE LOADED {len(group_list_state)} groups for index {index.id}")
                        
                        # ✅ CRITICAL: Update file selector dropdown
                        if file_list_state:
                            file_names = [(item["name"], item["id"]) for item in file_list_state]
                        else:
                            file_names = []
                        file_names_update = gr.update(choices=file_names, value=[])
                        
                        # ✅ CRITICAL: Return proper Gradio updates untuk UI refresh
                        file_updates.extend([
                            gr.update(value=file_list_state),  # file_list_state
                            gr.update(value=file_list_df),     # file_list DataFrame
                            gr.update(value=group_list_state), # group_list_state  
                            gr.update(value=group_list_df),    # group_list DataFrame
                            file_names_update                  # group_files dropdown
                        ])
                        
                        logger.info(f"✅ Prepared UI updates for {len(file_list_state)} files and {len(group_list_state)} groups")
                    else:
                        # ✅ Empty updates for indices without file_index_page
                        file_updates.extend([
                            gr.update(value=[]), 
                            gr.update(value=None), 
                            gr.update(value=[]), 
                            gr.update(value=None), 
                            gr.update(choices=[], value=[])
                        ])
                        logger.warning(f"File index page not available for index {index.id}")
            except Exception as e:
                logger.exception(f"❌ Error loading file lists: {e}")
                # Provide empty updates for each index on error
                for index in self._app.index_manager.indices:
                    file_updates.extend([
                        gr.update(value=[]), 
                        gr.update(value=None), 
                        gr.update(value=[]), 
                        gr.update(value=None), 
                        gr.update(choices=[], value=[])
                    ])
            
            # Prepare updates for all tabs
            if hasattr(self._app, "_tabs") and hasattr(self._app, "tabs"):
                updates = []
                for k in self._app._tabs.keys():
                    if k == "login-tab":
                        updates.append(gr.update(visible=False))
                    elif k == "resources-tab":
                        updates.append(gr.update(visible=True))
                    else:
                        updates.append(gr.update(visible=True))
                
                updates.append(gr.update(selected="chat-tab"))
                
                # ✅ FIXED: Return proper conversation data
                updates.append(gr.update(
                    choices=chat_history, 
                    value=latest_conv_id
                ))
                
                # ✅ CRITICAL: Add file updates untuk immediate UI refresh
                updates.extend(file_updates)
                
                logger.info(f"🚀 Login complete - returning {len(updates)} UI updates including {len(file_updates)} file updates")
                return updates
                
        # Login failed case
        logger.warning("❌ Login failed, staying on login tab")
        if hasattr(self._app, "_tabs") and hasattr(self._app, "tabs"):
            updates = []
            for k in self._app._tabs.keys():
                if k == "login-tab":
                    updates.append(gr.update(visible=True))
                else:
                    updates.append(gr.update(visible=False))
            updates.append(gr.update(selected="login-tab"))
            updates.append(gr.update())  # Empty conversation
            
            # Add empty file updates
            for index in self._app.index_manager.indices:
                updates.extend([
                    gr.update(value=[]), 
                    gr.update(value=None), 
                    gr.update(value=[]), 
                    gr.update(value=None), 
                    gr.update(choices=[], value=[])
                ])
            
            return updates
        
        return [None, gr.update()]


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
SIPADU_API_BASE = os.getenv("SIPADU_API_BASE")

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
                "Mulai Gunakan AI Tools", 
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
                    "Mulai Gunakan AI Tools", 
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
        """Perform authentication check - FIXED user switch detection"""
        logger.info("🔄 Enhanced authentication check with session detection")
        
        # Extract token dari query parameters
        token = None
        if request.query_params:
            token = request.query_params.get('token')
            logger.debug(f"Query params: {dict(request.query_params)}")
            logger.debug(f"Token found: {token[:50] + '...' if token else 'None'}")
        
        # ✅ Get existing session info
        current_session_token = os.getenv('CURRENT_SESSION_TOKEN', '')
        current_user_id = os.getenv('CURRENT_USER_ID', '')
        
        # Development mode
        if os.getenv('KOTAEMON_DEV_MODE', '').lower() == 'true':
            logger.info("Development mode activated")
            user_data = {'username': 'dev_user', 'nama_lengkap': 'Development User', 'user_id': 'dev_1'}
            return 'DEV_MODE', user_data, "DEV MODE", user_data
        
        if not token:
            logger.warning("No token found")
            # ✅ FIXED: Only logout if there WAS a previous session
            if current_session_token:
                logger.info("🗑️ Clearing existing session - no token provided")
                self._trigger_complete_logout()
            return 'NO_TOKEN', {}, "Token tidak ditemukan", {}
        
        # ✅ CRITICAL FIX: Validate token FIRST before checking user switch
        logger.info("Validating token with SIPADU...")
        is_valid, user_data, error_msg = self.validate_sipadu_token(token)
        
        if not is_valid:
            logger.warning(f"Authentication FAILED: {error_msg}")
            self._trigger_complete_logout()
            return 'FAILED', {}, error_msg, {}
        
        # ✅ CRITICAL FIX: Construct new_user_id with sipadu_ prefix (only once!)
        new_user_id = f"sipadu_{user_data.get('user_id')}"
        
        # ✅ NEW LOGIC: Only trigger logout if user ID is DIFFERENT
        if current_user_id and current_user_id != new_user_id:
            logger.info(f"🔄 REAL USER SWITCH DETECTED! Old: {current_user_id}, New: {new_user_id}")
            logger.info("🚪 Triggering complete logout for previous user")
            self._trigger_complete_logout()
            # Add delay untuk ensure logout is complete
            import time
            time.sleep(1.0)
        elif current_session_token and current_session_token != token and current_user_id == new_user_id:
            # ✅ SAME USER with NEW TOKEN - just update token, NO logout
            logger.info(f"🔄 Same user {new_user_id} with new token - updating session")
            os.environ['CURRENT_SESSION_TOKEN'] = token
            # NO logout, NO delay
        else:
            # ✅ First login or same session - just set token
            logger.info(f"✅ Setting session for user {new_user_id}")
            os.environ['CURRENT_SESSION_TOKEN'] = token
            os.environ['CURRENT_USER_ID'] = new_user_id
        
        logger.info(f"Authentication SUCCESS for: {user_data.get('nama_lengkap')}")
        return 'SUCCESS', user_data, None, user_data

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
        """Register events - FINAL FIXED VERSION with proper event flow"""
        logger.info("="*80)
        logger.info("🔧 Registering login page events...")
        logger.info("="*80)
        
        # ✅ CRITICAL FIX: Simplified event chain dengan explicit logging
        # Step 1: Auth check saat app load
        self._app.app.load(
            fn=self.perform_auth_check,
            inputs=[],
            outputs=[self.auth_status, self.user_data, self.auth_error, self.current_user_data],
            show_progress="hidden",
            queue=False
        ).then(
            # Step 2: Update UI berdasarkan auth status
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
        ).then(
            # Step 3: Auto-login jika auth SUCCESS
            fn=self.auto_login_if_authenticated,
            inputs=[self.auth_status, self.current_user_data],
            outputs=[self._app.user_id],
            show_progress="hidden",
            queue=False
        ).then(
            # Step 4: CRITICAL - Complete login process dengan file loading
            fn=lambda user_id, auth_status: self.auto_complete_login_if_needed(user_id, auth_status),
            inputs=[self._app.user_id, self.auth_status],
            outputs=self._get_all_login_outputs(),
            show_progress="full",  # ✅ CRITICAL: Show progress untuk debugging
            queue=True  # ✅ CRITICAL: Enable queue untuk ensure proper execution
        )
        
        logger.info("✅ Registered app.load() event chain")
        
        # Manual login button (untuk Success UI case)
        login_outputs = self._get_all_login_outputs()
        
        self.btn_login.click(
            fn=self.manual_login_handler,
            inputs=[self.current_user_data],
            outputs=[self._app.user_id, self.status_display, gr.State()],
            show_progress="hidden"
        ).then(
            fn=self.complete_login_process,
            inputs=[self._app.user_id, self.status_display, gr.State()],
            outputs=login_outputs,
            show_progress="full"  # ✅ Show progress
        )
        
        logger.info("✅ Registered btn_login event")
        
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
        
        logger.info("✅ Registered retry_btn event")
        
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
            inputs=[self._app.user_id, self.status_display, gr.State()],
            outputs=self._get_all_login_outputs(),
            show_progress="hidden"
        )

    def _get_all_login_outputs(self):
        """Get all outputs needed for login process - HELPER"""
        login_outputs = list(self._app._tabs.values()) + [
            self._app.tabs, 
            self._app.chat_page.chat_control.conversation
        ]
        
        # Add file outputs
        for index in self._app.index_manager.indices:
            # ✅ CRITICAL FIX: Check both possible attribute names
            file_control = None
            if hasattr(index, 'file_index_page'):
                file_control = index.file_index_page
            elif hasattr(index, 'file_control'):
                file_control = index.file_control
            
            if file_control:
                login_outputs.extend([
                    file_control.file_list_state,
                    file_control.file_list,
                    file_control.group_list_state,
                    file_control.group_list,
                    file_control.group_files
                ])
        
        logger.info(f"📊 _get_all_login_outputs: {len(login_outputs)} total outputs")
        return login_outputs

    def auto_login_if_authenticated(self, auth_status, current_user_data):
        """Auto create/get user jika authentication SUCCESS - ENHANCED WITH LOGGING"""
        logger.info("="*80)
        logger.info(f"🔐 auto_login_if_authenticated: status={auth_status}")
        logger.info(f"📋 User data: {current_user_data}")
        logger.info("="*80)
        
        if auth_status == 'SUCCESS' and current_user_data and current_user_data.get('user_id'):
            logger.info("✅ Status is SUCCESS and user data available")
            logger.info(f"🔄 Creating/getting user for: {current_user_data.get('username')}")
            user_id = self.create_or_get_user(current_user_data)
            if user_id:
                logger.info("="*80)
                logger.info(f"✅ User ready: {user_id}")
                logger.info("="*80)
                return user_id
            else:
                logger.error("❌ Failed to create/get user!")
                return None
        
        logger.warning("❌ Not authenticated or no user data")
        logger.info(f"   - auth_status: {auth_status}")
        logger.info(f"   - has user_data: {bool(current_user_data)}")
        logger.info(f"   - has user_id in data: {current_user_data.get('user_id') if current_user_data else 'N/A'}")
        return None

    def auto_complete_login_if_needed(self, user_id, auth_status):
        """Auto complete login process jika user_id ada - FIXED VERSION"""
        logger.info(f"🔄 auto_complete_login_if_needed: user_id={user_id}, status={auth_status}")
        
        # ✅ CRITICAL FIX: Check user_id only (auth_status may not be reliable here)
        if user_id:
            logger.info(f"✅ Auto-completing login for user: {user_id} (auth_status: {auth_status})")
            # ✅ Use existing complete_login_process to load everything
            return self.complete_login_process(user_id, "Auto login successful", None)
        
        logger.info("❌ No user_id - skipping auto-login")
        # Return empty updates
        return self._get_empty_login_outputs()

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
        """Manually trigger onSignOut events untuk semua komponen - ENHANCED ERROR HANDLING"""
        try:
            logger.info("🔄 Manually triggering onSignOut events...")
            
            # Get all onSignOut events
            signout_events = self._app.get_event("onSignOut")
            logger.info(f"📋 Found {len(signout_events)} onSignOut events to trigger")
            
            # Trigger each event with proper error handling
            for i, event in enumerate(signout_events):
                try:
                    if 'fn' in event:
                        event_fn = event['fn']
                        if callable(event_fn):
                            logger.info(f"🔄 Triggering onSignOut event {i+1}/{len(signout_events)}")
                            
                            # ✅ CRITICAL FIX: Check if function needs arguments
                            import inspect
                            sig = inspect.signature(event_fn)
                            params = sig.parameters
                            
                            # If function has no parameters, call without arguments
                            if len(params) == 0:
                                event_fn()
                            else:
                                # ✅ Try to call with None/empty values for required params
                                try:
                                    args = [None] * len(params)
                                    event_fn(*args)
                                except Exception as inner_e:
                                    logger.warning(f"⚠️ Could not call event {i+1} with args: {inner_e}")
                                    # Try without arguments as fallback
                                    try:
                                        event_fn()
                                    except:
                                        pass
                                
                except Exception as e:
                    logger.warning(f"⚠️ Error triggering onSignOut event {i+1}: {e}")
                    # Don't raise, continue with next event
                    continue
                    
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
        """Complete login process dengan proper data loading - FINAL VERSION"""
        logger.info(f"🎯 complete_login_process START - User: {user_id}, Status: {status_msg}")
        
        if not user_id:
            logger.warning("❌ No user_id - aborting login process")
            return self._get_empty_login_outputs()
        
        logger.info(f"✅ Login successful for user: {user_id}")
        
        # ✅ 1. Set user_id FIRST
        self._app.user_id.value = user_id
        # ✅ CRITICAL FIX: user_id already contains 'sipadu_' prefix, don't add again!
        os.environ['CURRENT_USER_ID'] = user_id
        logger.info(f"✅ Set environment CURRENT_USER_ID: {user_id}")
        
        # ✅ 2. Clear any existing cached data
        self._clear_all_cached_data()
        logger.info("✅ Cleared cached data")
        
        # ✅ 3. Small delay for database consistency
        import time
        time.sleep(0.2)
        
        # ✅ 4. Load chat history
        try:
            if hasattr(self._app, 'chat_page') and hasattr(self._app.chat_page, 'chat_control'):
                chat_control = self._app.chat_page.chat_control
                chat_history = chat_control.load_chat_history(user_id)
                logger.info(f"✅ Loaded {len(chat_history)} conversations")
                latest_conv_id = chat_history[0][1] if chat_history else None
            else:
                logger.warning("⚠️ Chat control not available")
                chat_history = []
                latest_conv_id = None
        except Exception as e:
            logger.exception(f"❌ Error loading chat history: {e}")
            chat_history = []
            latest_conv_id = None
        
        # ✅ 5. CRITICAL: Force reload files dengan explicit logging
        logger.info("="*80)
        logger.info("🔄 STARTING FILE RELOAD...")
        logger.info(f"📊 Number of indices: {len(self._app.index_manager.indices)}")
        logger.info("="*80)
        file_updates = []
        try:
            for index in self._app.index_manager.indices:
                logger.info(f"\n🔍 Checking index: {index.id}")
                logger.info(f"   Index type: {type(index)}")
                logger.info(f"   Index attributes: {dir(index)}")
                
                # ✅ CRITICAL FIX: Check for file_control or file_index_page
                file_control = None
                if hasattr(index, 'file_index_page'):
                    file_control = index.file_index_page
                    logger.info(f"✅ Found file_index_page on index {index.id}")
                elif hasattr(index, 'file_control'):
                    file_control = index.file_control
                    logger.info(f"✅ Found file_control on index {index.id}")
                
                if file_control:
                    logger.info(f"🔄 Processing index {index.id} for user {user_id}")
                    
                    # Clear cache
                    if hasattr(file_control, '_clear_cached_file_data'):
                        file_control._clear_cached_file_data()
                        logger.info(f"✅ Cleared cache for index {index.id}")
                    else:
                        logger.warning(f"⚠️ No _clear_cached_file_data method for index {index.id}")
                    
                    # Force fresh query
                    logger.info(f"🔍 Calling list_file for user {user_id}...")
                    file_list_state, file_list_df = file_control.list_file(user_id, "")
                    logger.info(f"✅ list_file returned {len(file_list_state)} files")
                    logger.info(f"📋 Files: {[f['name'] for f in file_list_state[:3]]}...") if file_list_state else logger.info("📋 No files found")
                    
                    logger.info(f"🔍 Calling list_group for user {user_id}...")
                    group_list_state, group_list_df = file_control.list_group(user_id, file_list_state)
                    logger.info(f"✅ list_group returned {len(group_list_state)} groups")
                    
                    # Prepare dropdown
                    if file_list_state:
                        file_names = [(item["name"], item["id"]) for item in file_list_state]
                    else:
                        file_names = []
                    file_names_update = gr.update(choices=file_names, value=[])
                    
                    # Add to updates
                    file_updates.extend([
                        gr.update(value=file_list_state),
                        gr.update(value=file_list_df),
                        gr.update(value=group_list_state),
                        gr.update(value=group_list_df),
                        file_names_update
                    ])
                    
                    logger.info(f"✅ Prepared {len(file_list_state)} files and {len(group_list_state)} groups for UI update")
                else:
                    logger.error(f"❌ No file_control found for index {index.id}!")
                    logger.error(f"   This will cause file list to not load!")
                    logger.error(f"   Index attributes: {[attr for attr in dir(index) if not attr.startswith('_')]}")
                    file_updates.extend([
                        gr.update(value=[]), 
                        gr.update(value=None), 
                        gr.update(value=[]), 
                        gr.update(value=None), 
                        gr.update(choices=[], value=[])
                    ])
        except Exception as e:
            logger.exception(f"❌ Error in file reload: {e}")
            # Empty updates on error
            for index in self._app.index_manager.indices:
                file_updates.extend([
                    gr.update(value=[]), 
                    gr.update(value=None), 
                    gr.update(value=[]), 
                    gr.update(value=None), 
                    gr.update(choices=[], value=[])
                ])
        
        logger.info("="*80)
        logger.info(f"✅ FILE RELOAD COMPLETE - prepared {len(file_updates)} file updates")
        logger.info("="*80)
        
        # ✅ 6. Prepare all outputs
        logger.info("\n📦 Preparing final outputs...")
        updates = []
        for k in self._app._tabs.keys():
            if k == "login-tab":
                updates.append(gr.update(visible=False))
                logger.info(f"  - Tab '{k}': visible=False")
            else:
                updates.append(gr.update(visible=True))
                logger.info(f"  - Tab '{k}': visible=True")
        
        updates.append(gr.update(selected="chat-tab"))
        logger.info(f"  - Tab selector: selected='chat-tab'")
        
        updates.append(gr.update(choices=chat_history, value=latest_conv_id))
        logger.info(f"  - Conversation dropdown: {len(chat_history)} conversations, selected={latest_conv_id}")
        
        updates.extend(file_updates)
        logger.info(f"  - File updates: {len(file_updates)} updates added")
        
        logger.info("="*80)
        logger.info(f"🚀 complete_login_process COMPLETE - returning {len(updates)} updates")
        logger.info(f"📊 Updates breakdown: {len(self._app._tabs)} tabs + 1 tab selector + 1 conversation + {len(file_updates)} file updates")
        logger.info(f"📊 Expected outputs: {len(self._get_all_login_outputs())} vs Actual: {len(updates)}")
        logger.info("="*80)
        
        return updates

    def _get_empty_login_outputs(self):
        """Get empty outputs for failed login - HELPER"""
        updates = []
        for k in self._app._tabs.keys():
            if k == "login-tab":
                updates.append(gr.update(visible=True))
            else:
                updates.append(gr.update(visible=False))
        updates.append(gr.update(selected="login-tab"))
        updates.append(gr.update())
        
        # Empty file updates
        for index in self._app.index_manager.indices:
            updates.extend([
                gr.update(value=[]), 
                gr.update(value=None), 
                gr.update(value=[]), 
                gr.update(value=None), 
                gr.update(choices=[], value=[])
            ])
        
        return updates


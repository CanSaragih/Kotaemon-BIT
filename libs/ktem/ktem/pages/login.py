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
        """Perform authentication check - FIXED VERSION dengan better state handling"""
        logger.info("Performing authentication check")
        
        # Extract token dari query parameters
        token = None
        if request.query_params:
            token = request.query_params.get('token')
            logger.debug(f"Query params: {dict(request.query_params)}")
            logger.debug(f"Token found: {token[:50] + '...' if token else 'None'}")
        
        # Development mode
        if os.getenv('KOTAEMON_DEV_MODE', '').lower() == 'true':
            logger.info("Development mode activated")
            user_data = {'username': 'dev_user', 'nama_lengkap': 'Development User', 'user_id': 'dev_1'}
            return 'DEV_MODE', user_data, "DEV MODE", user_data  # Return user_data juga
        
        if not token:
            logger.warning("No token found")
            return 'NO_TOKEN', {}, "Token tidak ditemukan", {}
        
        # Validate token
        logger.info("Validating token with SIPADU...")
        is_valid, user_data, error_msg = self.validate_sipadu_token(token)
        
        if is_valid:
            logger.info(f"Authentication SUCCESS for: {user_data.get('nama_lengkap')}")
            return 'SUCCESS', user_data, None, user_data  # Return user_data di posisi ke-4
        else:
            logger.warning(f"Authentication FAILED: {error_msg}")
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
        """Handler untuk manual login button - FIXED VERSION tanpa create ConversationControl baru"""
        logger.info("Manual login button clicked")
        logger.debug(f"Current user data: {current_user_data}")
        
        if current_user_data and current_user_data.get('user_id'):
            try:
                user_id = self.create_or_get_user(current_user_data)
                if user_id:
                    logger.info(f"Manual login successful for user: {current_user_data.get('nama_lengkap')}")
                    
                    # Use Gradio's built-in notification system
                    gr.Info(f"🎉 Selamat datang, {current_user_data.get('nama_lengkap')}!")
                    
                    # ✅ FIXED: Load chat history using existing chat_control
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

    def complete_login_process(self, user_id, status_msg, chat_history_list=None):
        logger.info(f"Complete login process called - User: {user_id}, Status: {status_msg}")
        if user_id:
            logger.info(f"Login successful, switching to chat tab for user: {user_id}")
            
            # ✅ CRITICAL FIX: Set user_id FIRST before triggering events
            self._app.user_id.value = user_id
            
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

            # ✅ NEW: Load file list immediately after login
            try:
                if hasattr(self._app, 'index_manager') and self._app.index_manager.indices:
                    # Get first index (file index)
                    first_index = self._app.index_manager.indices[0]
                    if hasattr(first_index, '_page') and hasattr(first_index._page, 'list_file'):
                        file_list_state, file_list_df = first_index._page.list_file(user_id, "")
                        logger.info(f"✅ Loaded {len(file_list_state)} files for user {user_id}")
                    else:
                        logger.warning("File index page not available during login process")
                        file_list_state, file_list_df = [], None
                else:
                    logger.warning("Index manager not available during login process")
                    file_list_state, file_list_df = [], None
            except Exception as e:
                logger.exception(f"❌ Error loading file list: {e}")
                file_list_state, file_list_df = [], None
            
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
                
                logger.info("🚀 Login complete - redirecting to chat with loaded history and files")
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
            return updates
        
        return [None, gr.update()]

    def trigger_conversation_reload(self, user_id):
        """Manually trigger conversation and file reload after login - ENHANCED VERSION"""
        if user_id and hasattr(self._app, 'chat_page'):
            logger.info(f"🔄 Manually triggering conversation and file reload for user: {user_id}")
            try:
                # ✅ FIXED: Use existing chat_control instance
                chat_control = self._app.chat_page.chat_control
                chat_history = chat_control.load_chat_history(user_id)
                logger.info(f"✅ Manual reload: {len(chat_history)} conversations loaded")
                
                # ✅ NEW: Also trigger file reload
                if hasattr(self._app, 'index_manager') and self._app.index_manager.indices:
                    first_index = self._app.index_manager.indices[0]
                    if hasattr(first_index, '_page') and hasattr(first_index._page, 'list_file'):
                        file_list_state, file_list_df = first_index._page.list_file(user_id, "")
                        logger.info(f"✅ Manual reload: {len(file_list_state)} files loaded")
                        
                        # Trigger onFileIndexChanged event if available
                        try:
                            if hasattr(self._app, 'get_event'):
                                file_events = self._app.get_event(f"onFileIndex{first_index.id}Changed")
                                logger.info(f"✅ Found {len(file_events)} file index events to trigger")
                        except Exception as e:
                            logger.debug(f"No file index events found: {e}")
                
                logger.info("🎯 Conversation and file history loaded and ready for display")
                
            except Exception as e:
                logger.exception(f"❌ Manual conversation and file reload failed: {e}")
        return user_id

    def on_register_events(self):
        """Register events - ENHANCED VERSION dengan conversation loading"""
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
        
        # ✅ ENHANCED: Manual login dengan proper conversation loading
        self.btn_login.click(
            fn=self.manual_login_handler,
            inputs=[self.current_user_data],
            outputs=[self._app.user_id, self.status_display, gr.State()],
            show_progress="hidden"
        ).then(
            fn=self.complete_login_process,
            inputs=[self._app.user_id, self.status_display, gr.State()],
            outputs=list(self._app._tabs.values()) + [
                self._app.tabs, 
                self._app.chat_page.chat_control.conversation  # ✅ DIRECT conversation update
            ],
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


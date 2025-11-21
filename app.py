import os
import sys
import requests
import json
import gradio as gr

from theflow.settings import settings as flowsettings

KH_APP_DATA_DIR = getattr(flowsettings, "KH_APP_DATA_DIR", ".")
KH_GRADIO_SHARE = getattr(flowsettings, "KH_GRADIO_SHARE", False)
GRADIO_TEMP_DIR = os.getenv("GRADIO_TEMP_DIR", None)

# SIPADU Integration Settings - FROM ENVIRONMENT
SIPADU_API_BASE = os.getenv("SIPADU_API_BASE", "http://localhost.sipadubapelitbangor")
SIPADU_VALIDATE_ENDPOINT = f"{SIPADU_API_BASE}/api/validate-token"

# override GRADIO_TEMP_DIR if it's not set
if GRADIO_TEMP_DIR is None:
    GRADIO_TEMP_DIR = os.path.join(KH_APP_DATA_DIR, "gradio_tmp")
    os.environ["GRADIO_TEMP_DIR"] = GRADIO_TEMP_DIR

def validate_token_with_sipadu(token):
    if not token:
        return False, {}, "No token provided"
    
    try:
        
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Kotaemon-SSO/1.0',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(
            SIPADU_VALIDATE_ENDPOINT,
            params={'token': token},
            headers=headers,
            timeout=10
        )
        
        print(f"📡 Response Status: {response.status_code}")
        
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
                print(f"✅ Token valid for user: {user_info.get('nama_lengkap')}")
                return True, user_info, None
            else:
                error_msg = data.get('message', 'Token validation failed')
                print(f"❌ Token invalid: {error_msg}")
                return False, {}, error_msg
        else:
            error_msg = f"SIPADU API error: {response.status_code}"
            print(f"❌ API Error: {error_msg}")
            return False, {}, error_msg
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Connection error to SIPADU: {str(e)}"
        print(f"❌ Connection Error: {error_msg}")
        return False, {}, error_msg
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        print(f"❌ Unexpected Error: {error_msg}")
        return False, {}, error_msg

def main():
    
    # ✅ NEW: Clear any existing session data
    clear_existing_sessions()
    
    # Development mode check
    if os.getenv('KOTAEMON_DEV_MODE', '').lower() == 'true':
        auth_status = 'DEV_MODE'
        user_data = {'username': 'dev_user', 'nama_lengkap': 'Development User'}
    else:
        auth_status = 'PENDING'  # Will be handled in login.py
        user_data = {}
    
    # Set environment variables
    os.environ['SIPADU_AUTH_STATUS'] = auth_status
    os.environ['SIPADU_USER_DATA'] = json.dumps(user_data)
    
    
    # Load and launch the application
    try:
        from ktem.main import App

        app = App()
        demo = app.make()
        
        
        # Enhanced launch configuration
        launch_kwargs = {
            "server_name": "127.0.0.1",
            "server_port": 7860,
            "favicon_path": getattr(app, '_favicon', None),
            "inbrowser": True,
            "share": KH_GRADIO_SHARE,
            "allowed_paths": [
                "libs/ktem/ktem/assets",
                GRADIO_TEMP_DIR,
            ],
            "prevent_thread_lock": False,
            "show_error": True,
        }
        
        demo.launch(**launch_kwargs)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

def clear_existing_sessions():
    
    try:
        # Clear environment session variables
        for key in ['SIPADU_AUTH_STATUS', 'SIPADU_USER_DATA', 'CURRENT_USER_ID']:
            if key in os.environ:
                del os.environ[key]
        
        # Clear any temporary session files if they exist
        import tempfile
        temp_dir = tempfile.gettempdir()
        session_files = [f for f in os.listdir(temp_dir) if f.startswith('kotaemon_session_')]
        for session_file in session_files:
            try:
                os.remove(os.path.join(temp_dir, session_file))
                print(f"🗑️ Removed session file: {session_file}")
            except:
                pass
                
        print("✅ Session clearing completed")
        
    except Exception as e:
        print(f"❌ Error clearing sessions: {e}")


if __name__ == "__main__":
    main()
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from config import Config

def send_login_email(email, api_key, host_url):
    """Send an email with the magic link/API key using SendGrid"""
    if not Config.SENDGRID_API_KEY:
        print("⚠️ SendGrid API Key not configured. Cannot send email.")
        print(f"   SENDGRID_API_KEY: {'SET' if Config.SENDGRID_API_KEY else 'NOT SET'}")
        return False
    
    try:
        print(f"📧 Attempting to send login email to: {email}")
        print(f"   Using SendGrid API")
        print(f"   From: {Config.EMAIL_FROM}")
        
        base_url = host_url.rstrip('/')
        magic_link = f"{base_url}/?api_key={api_key}"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #FF6B6B;">Welcome to OtakuDescriptor</h2>
                    <p>You requested to log in. Click the button below to access your account:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{magic_link}" style="background-color: #FF6B6B; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Log In</a>
                    </div>
                    <p>Or copy your API Key directly:</p>
                    <code style="background: #f4f4f4; padding: 5px 10px; border-radius: 4px; display: block; text-align: center; margin: 10px 0;">{api_key}</code>
                    <p style="font-size: 0.9em; color: #888; margin-top: 30px;">If you didn't request this email, you can safely ignore it.</p>
                </div>
            </body>
        </html>
        """
        
        message = Mail(
            from_email=Email(Config.EMAIL_FROM),
            to_emails=To(email),
            subject="Your OtakuDescriptor Access",
            html_content=Content("text/html", html_content)
        )
        
        sg = SendGridAPIClient(Config.SENDGRID_API_KEY)
        response = sg.send(message)
        
        print(f"✅ Login email sent successfully to {email}")
        print(f"   SendGrid Response Status: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending login email: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return False

def send_verification_email(email, verification_token, host_url):
    """Send a verification email to confirm the account using SendGrid"""
    if not Config.SENDGRID_API_KEY:
        print("⚠️ SendGrid API Key not configured. Cannot send verification email.")
        print(f"   SENDGRID_API_KEY: {'SET' if Config.SENDGRID_API_KEY else 'NOT SET'}")
        return False
    
    try:
        print(f"📧 Attempting to send verification email to: {email}")
        print(f"   Using SendGrid API")
        print(f"   From: {Config.EMAIL_FROM}")
        print(f"   Host URL: {host_url}")
        
        base_url = host_url.rstrip('/')
        verification_link = f"{base_url}/api/auth/verify-email?token={verification_token}"
        
        print(f"   Verification link: {verification_link}")
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #8b5cf6;">Welcome to OtakuDescriptor! 🎉</h2>
                    <p>Thank you for registering. To activate your account, please confirm your email address.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{verification_link}" style="background-color: #8b5cf6; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">Confirm My Email</a>
                    </div>
                    <p style="color: #666; font-size: 14px;">This link is valid for 24 hours.</p>
                    <p style="font-size: 0.9em; color: #888; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                        If you didn't create an account on OtakuDescriptor, you can safely ignore this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        message = Mail(
            from_email=Email(Config.EMAIL_FROM),
            to_emails=To(email),
            subject="Confirm Your OtakuDescriptor Account",
            html_content=Content("text/html", html_content)
        )
        
        sg = SendGridAPIClient(Config.SENDGRID_API_KEY)
        response = sg.send(message)
        
        print(f"✅ Verification email sent successfully to {email}")
        print(f"   SendGrid Response Status: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending verification email: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return False

def send_reset_password_email(email, token, host_url):
    """Send password recovery email using SendGrid"""
    if not Config.SENDGRID_API_KEY:
        print("⚠️ SendGrid API Key not configured. Cannot send reset password email.")
        return False
    
    try:
        print(f"📧 Attempting to send password reset email to: {email}")
        
        reset_link = f"{host_url.rstrip('/')}/reset-password.html?token={token}"
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #FF6B6B;">Password Recovery - OtakuDescriptor</h2>
                    <p>You have requested to reset your password.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" style="background-color: #FF6B6B; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Create New Password</a>
                    </div>
                    <p style="font-size: 0.9em; color: #888; margin-top: 30px;">If this wasn't you, please ignore this message.</p>
                </div>
            </body>
        </html>
        """
        
        message = Mail(
            from_email=Email(Config.EMAIL_FROM),
            to_emails=To(email),
            subject="Password Recovery - OtakuDescriptor",
            html_content=Content("text/html", html_content)
        )
        
        sg = SendGridAPIClient(Config.SENDGRID_API_KEY)
        response = sg.send(message)
        
        print(f"✅ Password reset email sent successfully to {email}")
        print(f"   SendGrid Response Status: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending reset password email: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return False

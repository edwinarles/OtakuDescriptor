import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

def send_login_email(email, api_key, host_url):
    """Envía un correo con el magic link/API key"""
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        print("⚠️ SMTP no configurado. No se puede enviar correo.")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_FROM
        msg['To'] = email
        msg['Subject'] = "Tu acceso a OtakuDescriptor"
        
        base_url = host_url.rstrip('/')
        magic_link = f"{base_url}/?api_key={api_key}"
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #FF6B6B;">Bienvenido a OtakuDescriptor</h2>
                    <p>Has solicitado iniciar sesión. Haz clic en el siguiente botón para acceder:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{magic_link}" style="background-color: #FF6B6B; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">Iniciar Sesión</a>
                    </div>
                    <p>O copia tu API Key directamente:</p>
                    <code style="background: #f4f4f4; padding: 5px 10px; border-radius: 4px; display: block; text-align: center; margin: 10px 0;">{api_key}</code>
                    <p style="font-size: 0.9em; color: #888; margin-top: 30px;">Si no solicitaste este correo, puedes ignorarlo.</p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Correo enviado a {email}")
        return True
    except Exception as e:
        print(f"❌ Error enviando correo: {e}")
        return False

def send_verification_email(email, verification_token, host_url):
    """Envía un correo de verificación para confirmar la cuenta"""
    if not Config.SMTP_USERNAME or not Config.SMTP_PASSWORD:
        print("⚠️ SMTP no configurado. No se puede enviar correo.")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_FROM
        msg['To'] = email
        msg['Subject'] = "Confirma tu cuenta en OtakuDescriptor"
        
        base_url = host_url.rstrip('/')
        # CORRECCIÓN: Agregar /api/auth al path
        verification_link = f"{base_url}/api/auth/verify-email?token={verification_token}"
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                    <h2 style="color: #8b5cf6;">¡Bienvenido a OtakuDescriptor! 🎉</h2>
                    <p>Gracias por registrarte. Para activar tu cuenta, por favor confirma tu correo electrónico.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{verification_link}" style="background-color: #8b5cf6; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">Confirmar mi Email</a>
                    </div>
                    <p style="color: #666; font-size: 14px;">Este enlace es válido por 24 horas.</p>
                    <p style="font-size: 0.9em; color: #888; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                        Si no creaste una cuenta en OtakuDescriptor, puedes ignorar este correo de manera segura.
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email de verificación enviado a {email}")
        return True
    except Exception as e:
        print(f"❌ Error enviando email de verificación: {e}")
        return False

def send_reset_password_email(email, token, host_url):
    """Envía correo de recuperación de contraseña"""
    if not Config.SMTP_USERNAME: return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = Config.EMAIL_FROM
        msg['To'] = email
        msg['Subject'] = "Recuperar Contraseña - OtakuDescriptor"
        
        # NOTA: En frontend deberás implementar una página que capture este token
        # Por ahora asumimos una url teórica /reset-password.html?token=...
        reset_link = f"{host_url.rstrip('/')}/reset-password.html?token={token}"
        
        html = f"""
        <p>Has solicitado restablecer tu contraseña.</p>
        <p><a href="{reset_link}">Haz clic aquí para crear una nueva contraseña</a></p>
        <p>Si no fuiste tú, ignora este mensaje.</p>
        """
        
        msg.attach(MIMEText(html, 'html'))
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Error reset password email: {e}")
        return False

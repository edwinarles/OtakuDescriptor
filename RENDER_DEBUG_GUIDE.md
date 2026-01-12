# Render 500 Error Fix - Registration Endpoint

## Problem Summary

You were experiencing a **500 Internal Server Error** on Render when attempting to register a new account. The key issue was:

```
SyntaxError: Unexpected token '<', "<html>  <"... is not valid JSON
```

This error occurs when:
1. The server encounters an **unhandled exception**
2. Flask returns an **HTML error page** (default 500 error page)
3. The frontend tries to parse this HTML as JSON and fails

## Root Cause

The registration endpoint (`/api/auth/register-password`) was throwing unhandled exceptions that weren't being caught properly. The most likely causes on Render are:

1. **SMTP Configuration Issues** - Missing or incorrect email credentials
2. **Database Connection Problems** - MongoDB connection errors
3. **Missing Environment Variables** - Required config not set on Render

When any of these fail, Flask was returning an HTML error page instead of a JSON error response.

## Changes Made

### 1. Enhanced Error Handling in `routes/auth.py`

**Changes:**
- ✅ Added database connection verification at the start
- ✅ Wrapped JSON parsing in try-catch
- ✅ Wrapped every database operation in separate try-catch blocks
- ✅ Added specific error handling for email service
- ✅ Ensured ALL errors return JSON responses, never HTML

**Key improvements:**
```python
# Database connection check
try:
    db.db.command('ping')
    print("✅ Database connection verified")
except Exception as db_err:
    return jsonify({
        'error': 'Database connection error',
        'details': 'Cannot connect to database...'
    }), 500
```

### 2. Global Error Handlers in `app.py`

**Changes:**
- ✅ Added `@app.errorhandler(500)` to catch all 500 errors
- ✅ Added `@app.errorhandler(Exception)` as a catch-all
- ✅ Both handlers return JSON instead of HTML

**Benefits:**
- Even if an exception escapes the route's try-catch, Flask will still return JSON
- Provides detailed error information in the response
- Logs stack traces to Render logs for debugging

## Next Steps to Deploy on Render

### Step 1: Verify Environment Variables

Make sure these are set in your Render dashboard:

**Required:**
- `MONGO_URI` - Your MongoDB Atlas connection string
- `SMTP_USERNAME` - Your Gmail address (e.g., `yourapp@gmail.com`)
- `SMTP_PASSWORD` - Your Gmail App Password (NOT your regular password!)
- `EMAIL_FROM` - Email address to send from (usually same as SMTP_USERNAME)

**Optional but Recommended:**
- `SMTP_SERVER` - Default: `smtp.gmail.com`
- `SMTP_PORT` - Default: `587`

### Step 2: Get Gmail App Password

If using Gmail for SMTP:

1. Go to Google Account settings
2. Enable 2-Factor Authentication
3. Go to **Security > 2-Step Verification > App passwords**
4. Create an app password named "OtakuDescriptor"
5. Copy the 16-character password
6. Use this in `SMTP_PASSWORD` environment variable

### Step 3: Deploy and Test

1. **Commit and push** these changes:
   ```bash
   git add .
   git commit -m "Add comprehensive error handling for registration endpoint"
   git push
   ```

2. **Check Render logs** after deployment:
   - Go to Render dashboard → Your service → Logs
   - Try to register an account
   - Look for the detailed logging:
     - `🔐 PASSWORD REGISTRATION ATTEMPT`
     - `✅ Database connection verified`
     - `📧 Attempting to send verification email...`

3. **Identify the specific issue**:
   - If you see `❌ DATABASE CONNECTION FAILED` → Check `MONGO_URI`
   - If you see `❌ SMTP Authentication failed` → Check SMTP credentials
   - If you see `❌ Email service error` → Check all SMTP environment variables

## Common Issues and Solutions

### Issue 1: SMTP Authentication Failed
**Error:** `❌ SMTP Authentication failed`

**Solution:**
- Use Gmail App Password, not your regular password
- Ensure 2FA is enabled on your Gmail account
- Double-check the `SMTP_USERNAME` and `SMTP_PASSWORD` in Render

### Issue 2: Database Connection Error
**Error:** `❌ DATABASE CONNECTION FAILED`

**Solution:**
- Verify `MONGO_URI` is correct in Render environment variables
- Ensure MongoDB Atlas allows connections from anywhere (0.0.0.0/0)
- Check that your MongoDB Atlas cluster is running

### Issue 3: Missing Environment Variables
**Error:** `❌ SMTP not configured`

**Solution:**
- Set all required environment variables in Render dashboard
- Restart the service after adding variables

## Testing Locally

To test these changes locally:

1. Ensure your `.env` file has all required variables:
```env
MONGO_URI=mongodb+srv://...
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com
```

2. Run the server:
```bash
python app.py
```

3. Try registering from your frontend
4. Check the terminal for detailed logs

## What to Look For in Render Logs

When you try to register on Render, you should see:

✅ **Success:**
```
🔐 PASSWORD REGISTRATION ATTEMPT
✅ Database connection verified
1️⃣ Checking for existing account...
   ✅ No existing account found
2️⃣ Checking for pending registrations...
   ✅ No pending registration found
3️⃣ Creating new pending registration...
   Generated token: xxxxx...
   ✅ Pending registration saved to database
4️⃣ Sending verification email...
📧 Attempting to send verification email...
   Connecting to SMTP server...
   Authenticating...
   Sending message...
✅ Verification email sent successfully
```

❌ **Failure (with specific error):**
```
🔐 PASSWORD REGISTRATION ATTEMPT
❌ DATABASE CONNECTION FAILED: [error details]
```

Now you'll know EXACTLY what's failing!

## Frontend Changes (Already Handled)

The frontend in `funcionamiento.js` already handles JSON error responses properly:
- Catches network errors
- Displays error messages to users
- Includes retry logic

No frontend changes needed! 🎉

## Summary

✅ **Before:** Server returned HTML 500 errors → Frontend couldn't parse → Generic "Connection error"

✅ **After:** Server returns structured JSON errors → Frontend displays specific error → You can debug from logs

The key improvement is **granular error handling** at every step with **detailed logging**, making it easy to identify exactly what's failing on Render.

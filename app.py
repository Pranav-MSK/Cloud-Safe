from flask import Flask, redirect, request, session, url_for, render_template, flash, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from google.cloud import storage
from datetime import datetime, timedelta
import os
import uuid
from jinja2 import TemplateNotFound
from dotenv import load_dotenv
load_dotenv()

# Allow transport for local development and production
if os.environ.get("GAE_ENV", "").startswith("standard"):
    # On Google App Engine
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "0"
else:
    # On local dev server
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

print("Current working directory:", os.getcwd())
print("Files in this directory:", os.listdir())

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-default-insecure")

CLIENT_SECRETS_FILE = os.environ.get("CLIENT_SECRETS_FILE")
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
if os.environ.get("GAE_ENV", "").startswith("standard"):
    REDIRECT_URI = os.environ.get("PROD_REDIRECT_URI")
else:
    REDIRECT_URI = os.environ.get("REDIRECT_URI")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE")

# File upload configurations
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'mp4', 'mp3'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def get_gcs_client():
    """Initialize and return GCS client"""
    return storage.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_safe_filename(filename, user_email):
    """Generate a safe filename to prevent conflicts"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{user_email}/{timestamp}_{filename}"
    return safe_name

def get_user_files(user_email):
    """Get all files for a specific user"""
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        
        # List all blobs with user's email prefix
        blobs = bucket.list_blobs(prefix=f"{user_email}/")
        
        files = []
        for blob in blobs:
            # Skip if it's just the folder
            if blob.name.endswith('/'):
                continue
                
            # Extract original filename
            original_filename = blob.name.split('/')[-1]
            if '_' in original_filename:
                original_filename = '_'.join(original_filename.split('_')[1:])
            
            file_info = {
                'name': original_filename,
                'blob_name': blob.name,
                'size': blob.size,
                'created': blob.time_created,
                'updated': blob.updated,
                'content_type': blob.content_type or 'application/octet-stream'
            }
            files.append(file_info)
        
        # Sort by upload date (newest first)
        files.sort(key=lambda x: x['updated'], reverse=True)
        return files
    except Exception as e:
        print(f"Error getting user files: {e}")
        return []

def get_file_versions(user_email, original_filename):
    """Get all versions of a specific file"""
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        
        # This ensures you're fetching all historical versions of that exact file.
        blobs = bucket.list_blobs(prefix=f"{user_email}/{original_filename}", versions=True)
        
        versions = []
        for blob in blobs:
            if blob.name.endswith(original_filename):
                version_info = {
                    'blob_name': blob.name,
                    'size': blob.size,
                    'created': blob.time_created,
                    'updated': blob.updated,
                    'version': blob.name.split('/')[-1].split('_')[0]  # Extract timestamp as version
                }
                versions.append(version_info)
        
        # Sort by creation date (newest first)
        versions.sort(key=lambda x: x['created'], reverse=True)
        return versions
    except Exception as e:
        print(f"Error getting file versions: {e}")
        return []

@app.route("/")
def index():
    if "email" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "email" not in session:
        return redirect(url_for("index"))
    
    files = get_user_files(session["email"])
    return render_template("dashboard.html", 
                         email=session["email"],
                         name=session.get("name", session["email"]),
                         picture=session.get("picture", ""),
                         files=files)

@app.route("/login")
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(prompt="consent")
    session["state"] = state
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    state = session.get("state")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    idinfo = id_token.verify_oauth2_token(
        credentials._id_token,
        grequests.Request(),
        credentials.client_id,
    )
    
    session["email"] = idinfo["email"]
    session["name"] = idinfo.get("name", idinfo["email"])
    session["picture"] = idinfo.get("picture", "")
    
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("index"))

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "email" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("upload.html", email=session["email"], name=session.get("name", session["email"]))

    # Handle file upload
    if "file" not in request.files:
        flash("No file selected", "error")
        return redirect(request.url)
    
    file = request.files["file"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(request.url)

    # Validate file
    if not allowed_file(file.filename):
        flash(f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}", "error")
        return redirect(request.url)

    # Check file size (this is a basic check, GCS will also enforce limits)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        flash(f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB", "error")
        return redirect(request.url)

    try:
        # Generate filename for enabled versioning
        blob_name = f"{session['email']}/{file.filename}"
        
        # Upload to GCS
        storage_client = get_gcs_client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        # Add metadata
        blob.metadata = {
            'uploaded_by': session["email"],
            'upload_time': datetime.now().isoformat(),
            'original_filename': file.filename,
            'file_size': str(file_size)
        }
        
        blob.upload_from_file(file, content_type=file.content_type)
        
        flash(f"File '{file.filename}' uploaded successfully!", "success")
        return redirect(url_for("dashboard"))
        
    except Exception as e:
        flash(f"Upload failed: {str(e)}", "error")
        return redirect(request.url)

@app.route("/preview/<path:blob_name>")
def preview_file(blob_name):
    if "email" not in session or not blob_name.startswith(session["email"] + "/"):
        flash("Access denied", "error")
        return redirect(url_for("dashboard"))

    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            flash("File not found", "error")
            return redirect(url_for("dashboard"))

        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=10),
            method="GET"
        )
        return redirect(url)
    except Exception as e:
        flash(f"Preview failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))

@app.route("/download/<path:blob_name>")
def download_file(blob_name):
    if "email" not in session:
        return redirect(url_for("login"))
    
    # Security check: ensure user can only download their own files
    if not blob_name.startswith(session["email"] + "/"):
        flash("Access denied", "error")
        return redirect(url_for("dashboard"))
    
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        if not blob.exists():
            flash("File not found", "error")
            return redirect(url_for("dashboard"))
        
        # Generate signed URL for download (valid for 1 hour)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET"
        )
        
        return redirect(url)
        
    except Exception as e:
        flash(f"Download failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))

@app.route("/download_version/<path:blob_name>/<generation>")
def download_version(blob_name, generation):
    if "email" not in session or not blob_name.startswith(session["email"] + "/"):
        flash("Access denied", "error")
        return redirect(url_for("dashboard"))

    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name, generation=int(generation))

        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=10),
            method="GET"
        )
        return redirect(url)
    except Exception as e:
        flash(f"Download failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))


@app.route("/delete/<path:blob_name>", methods=["POST"])
def delete_file(blob_name):
    if "email" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Security check: ensure user can only delete their own files
    if not blob_name.startswith(session["email"] + "/"):
        return jsonify({"error": "Access denied"}), 403
    
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        if blob.exists():
            # Get original filename for the flash message
            original_filename = blob_name.split('/')[-1]
            if '_' in original_filename:
                original_filename = '_'.join(original_filename.split('_')[1:])
            
            blob.delete()
            flash(f"File '{original_filename}' deleted successfully", "success")
        else:
            flash("File not found", "error")
            
        return redirect(url_for("dashboard"))
        
    except Exception as e:
        flash(f"Delete failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))

# Simulated in-memory store
shared_links = {}

@app.route('/share/<path:blob_name>', methods=['POST'])
def share(blob_name):
    # Generate a unique token for sharing
    token = str(uuid.uuid4())
    expiry = datetime.utcnow() + timedelta(days=7)

    # Store mapping
    shared_links[token] = {
        'blob_name': blob_name,
        'expires': expiry
    }

    share_url = url_for('access_shared_file', token=token, _external=True)
    return jsonify({'url': share_url})

@app.route('/shared/<token>')
def access_shared_file(token):
    shared = shared_links.get(token)
    if not shared:
        flash('Invalid or expired link.', 'error')
        return redirect('/dashboard')

    if shared['expires'] < datetime.utcnow():
        flash('This link has expired.', 'error')
        return redirect('/dashboard')

    blob_name = shared['blob_name']
    # Logic to serve the file or redirect to preview/download
    return redirect(url_for('previewShare_file', blob_name=blob_name))  # Or use download_file

# Dummy endpoints for preview
@app.route('/preview/<path:blob_name>')
def previewShare_file(blob_name):
    return f"Previewing {blob_name}"

@app.route("/file/<path:original_filename>/versions")
def file_versions(original_filename):
    if "email" not in session:
        return redirect(url_for("login"))
    
    versions = get_file_versions(session["email"], original_filename)
    return render_template("versions.html", 
                         filename=original_filename,
                         versions=versions,
                         name=session.get("name", session["email"]))

@app.route("/restore/<path:blob_name>/<generation>", methods=["POST"])
def restore_version(blob_name, generation):
    if "email" not in session or not blob_name.startswith(session["email"] + "/"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)

        # Source: old version
        source_blob = bucket.blob(blob_name, generation=int(generation))

        # Destination: same blob name, no generation = "latest"
        destination_blob = bucket.blob(blob_name)

        # Copy old version to become latest
        bucket.copy_blob(source_blob, bucket, new_name=blob_name)

        flash(f"Restored version {generation} of {blob_name.split('/')[-1]}", "success")
        return redirect(url_for("file_versions", original_filename=blob_name.split("/")[-1]))

    except Exception as e:
        flash(f"Restore failed: {str(e)}", "error")
        return redirect(url_for("dashboard"))

# Error handlers
@app.errorhandler(404)
def not_found(e):
    try:
        return render_template("error.html"), 404
    except TemplateNotFound:
        return "404 Not Found", 404

@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html", error_code=500, error_message="Internal server error"), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)
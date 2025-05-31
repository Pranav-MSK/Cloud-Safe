# ☁️ Cloud Safe - Secure File Storage System

Cloud Safe is a secure cloud-based file storage system built with Python (Flask), Google Cloud Storage, and OAuth 2.0. Users can log in with their Google accounts, upload, preview, share, and manage files — including restoring previous versions.

---

## 🔗 Live Demo

🌐 [Visit the Live App](https://cloud-storage-system-460210.uc.r.appspot.com)

---

## 📸 Features

- ✅ Google OAuth 2.0 login
- ✅ File upload (with type & size restrictions)
- ✅ File preview & download
- ✅ Shareable link generation (with expiry)
- ✅ File versioning & restore
- ✅ Secure per-user file access
- ✅ Google Cloud Storage integration
- ✅ User-friendly interface (HTML, Jinja templates)

---

## 🛠 Tech Stack

- **Backend**: Python, Flask
- **Frontend**: HTML, CSS, Jinja
- **Cloud Platform**: Google Cloud Platform (GCP)
- **Storage**: Google Cloud Storage (GCS)
- **Auth**: Google OAuth 2.0
- **Deployment**: Google App Engine

---

## 🚀 Getting Started (Local Setup)

### 1. Clone the repo
```bash
git clone https://github.com/Pranav-MSK/Cloud-Safe.git
cd cloud-safe
```

---

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate  <!--For Windows-->
```

---

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

---

### 4. Add secrets (not included in repo)
- client_secret.json – Google OAuth client credentials 
- service_account.json – GCP service account key
<!--Both json files can be downloaded from your Google Cloud Console of your Project-->

- .env – environment variables (example below)
#### Sample .env file
```yaml
FLASK_SECRET_KEY=your-secret-key
REDIRECT_URI=http://localhost:5000/oauth2callback 
```

---

### 5. Run the app locally
```bash
python app.py 
```

---

## 📁 Project Structure
```graphql
Cloud-Safe/
│
├── app.py                  # Main Flask app
├── app.yaml                # GCP deployment config 
├── requirements.txt        # Python dependencies (modules, libraries used)
├── templates/              # HTML templates
├── static/                 # Static assets (logo, favicon)
├── .gitignore              # Git ignored files
├── .gcloudignore           # Files excluded during GCP deploy
└── README.md               # Project readme
```

---

## ☁️ Deploying to Google App Engine
Download Google Cloud SDK. Run these in the shell

### Authenticate & set project:
```bash
gcloud auth login
gcloud config set project [your-gcp-project-id]
```

### Deploy:
```bash
gcloud app deploy
```

### Visit your app
```bash
gcloud app browse
```

---

## 🔒 Note on Security
For safety, this repo does not include:
- client_secret.json
- service_account.json
- .env
*These should be created manually during local testing and must not be shared publicly.*

---

## 📧 Author
- Name: Pranav M S Krishnan
- Username: Pranav-MSK
- Profile :- https://github.com/Pranav-MSK
- Repository :- https://github.com/Pranav-MSK/Cloud-Safe
- App Deployed at:- https://cloud-storage-system-460210.uc.r.appspot.com

-----------

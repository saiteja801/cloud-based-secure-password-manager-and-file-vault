import customtkinter as ctk
from tkinter import messagebox, filedialog
from cryptography.fernet import Fernet
import hashlib
import base64
import json
import os
import time
import cv2
import threading
import shutil
import datetime
import smtplib
import random
import string
from email.message import EmailMessage

# ================= UI SETTINGS =================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ================= CONFIG =================
USERS_FILE = "users.json"
CLOUD_STORAGE = "cloud_vault_storage" 
INTRUDER_FOLDER = "intruders"
FACE_ABSENCE_LIMIT = 10
ADMIN_EMAIL = "admin@vault.com"
MAX_ATTEMPTS = 3

# --- EMAIL CONFIG (IMPORTANT: Use App Password here) ---
SENDER_EMAIL = "saitejarayarao@gmail.com"
SENDER_PASSWORD = "jsci ejda ipqr mljd" 

# ================= STATE =================
current_user = None
fernet = None
camera = None
monitoring = False
face_last_seen = time.time()
failed_attempts = {}
attack_alerts = {}
generated_otp = None

# ================= SETUP =================
for folder in [CLOUD_STORAGE, INTRUDER_FOLDER]:
    if not os.path.exists(folder): os.makedirs(folder)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({ADMIN_EMAIL: hashlib.sha256("admin123".encode()).hexdigest()}, f)

# ================= SECURITY & UTILS =================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_key(password):
    key = hashlib.sha256(password.encode()).digest()
    return base64.urlsafe_b64encode(key)

def capture_and_email_intruder(recipient_email, attempts):
    """FIXED: Captures photo and ATTACHES it to the alert email."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened(): return
    
    time.sleep(2.5) # Wait for camera to adjust to light
    ret, frame = cap.read()
    if ret:
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(INTRUDER_FOLDER, f"intruder_{ts}.jpg")
        cv2.imwrite(filename, frame)
        
        try:
            msg = EmailMessage()
            msg['Subject'] = "🚨 SECURE VAULT: INTRUDER ALERT"
            msg['From'] = SENDER_EMAIL
            msg['To'] = recipient_email
            msg.set_content(f"Security Alert! Someone tried to access your vault.\nAttempts: {attempts}\nTime: {ts}\nSee attached photo.")
            
            with open(filename, 'rb') as f:
                msg.add_attachment(f.read(), maintype='image', subtype='jpeg', filename=f"intruder_{ts}.jpg")
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
                smtp.send_message(msg)
        except Exception as e: print(f"Mail failed: {e}")
    cap.release()

def send_otp_email(recipient, otp):
    """Sends a password reset code."""
    try:
        msg = EmailMessage()
        msg['Subject'] = "🔐 Vault Password Reset OTP"
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient
        msg.set_content(f"Your 6-digit security code is: {otp}")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        return True
    except: return False

# ================= AI FACE MONITOR =================
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def face_monitor():
    global camera, monitoring, face_last_seen
    camera = cv2.VideoCapture(0)
    face_last_seen = time.time()
    while monitoring:
        ret, frame = camera.read()
        if not ret: continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        if len(faces) > 0:
            face_last_seen = time.time()
        else:
            if time.time() - face_last_seen > FACE_ABSENCE_LIMIT:
                monitoring = False
                app.after(0, logout)
                break
        time.sleep(2)

def start_face_monitor():
    global monitoring
    monitoring = True
    threading.Thread(target=face_monitor, daemon=True).start()

def stop_face_monitor():
    global monitoring, camera
    monitoring = False
    if camera:
        camera.release()
        camera = None

# ================= MAIN UI =================
app = ctk.CTk()
app.geometry("1000x750")
app.title("🔐 Cloud Secure Vault Pro")

main_frame = ctk.CTkFrame(app)
main_frame.pack(expand=True, fill="both")

def clear_main():
    for widget in main_frame.winfo_children(): widget.destroy()

# ================= LOGIN LOGIC =================
def login():
    global current_user, fernet
    email = login_email.get()
    password = login_password.get()

    if not os.path.exists(USERS_FILE): return
    with open(USERS_FILE, "r") as f: users = json.load(f)

    if email not in users:
        messagebox.showerror("Error", "User not found")
        return

    if email not in failed_attempts: failed_attempts[email] = 0

    if users[email] == hash_password(password):
        if email in attack_alerts and attack_alerts[email] >= MAX_ATTEMPTS:
            messagebox.showwarning("SECURITY WARNING", f"⚠️ Someone tried to access your vault {attack_alerts[email]} times while you were away!")
        
        failed_attempts[email] = 0
        attack_alerts[email] = 0
        current_user = email
        
        if email == ADMIN_EMAIL:
            load_admin_dashboard()
        else:
            fernet = Fernet(generate_key(password))
            load_dashboard()
            start_face_monitor()
    else:
        failed_attempts[email] += 1
        attack_alerts[email] = failed_attempts[email]
        
        if failed_attempts[email] >= MAX_ATTEMPTS:
            # FIXED: Captures photo and sends it to email in background
            threading.Thread(target=capture_and_email_intruder, args=(email, failed_attempts[email])).start()
            messagebox.showerror("Security Triggered", "Invalid Credentials! Intruder photo captured and security email sent.")
        else:
            messagebox.showerror("Error", f"Invalid Credentials ({failed_attempts[email]}/{MAX_ATTEMPTS})")

# ================= FORGOT PASSWORD =================
def open_forgot_password():
    clear_main()
    ctk.CTkLabel(main_frame, text="🔑 Reset Password", font=("Arial", 24)).pack(pady=20)
    e_entry = ctk.CTkEntry(main_frame, placeholder_text="Enter Registered Email", width=300); e_entry.pack(pady=10)
    
    def handle_reset():
        global generated_otp
        email = e_entry.get()
        with open(USERS_FILE, "r") as f: users = json.load(f)
        if email in users:
            generated_otp = "".join(random.choices(string.digits, k=6))
            if send_otp_email(email, generated_otp):
                messagebox.showinfo("Sent", f"OTP code sent to {email}")
                load_verify_otp_screen(email)
            else: messagebox.showerror("Error", "Failed to send email. Check settings.")
        else: messagebox.showerror("Error", "Email not found.")

    ctk.CTkButton(main_frame, text="Send Reset Code", command=handle_reset).pack(pady=10)
    ctk.CTkButton(main_frame, text="Back", command=load_login_screen).pack()

def load_verify_otp_screen(email):
    clear_main()
    ctk.CTkLabel(main_frame, text="Verify Code", font=("Arial", 20)).pack(pady=10)
    otp_e = ctk.CTkEntry(main_frame, placeholder_text="6-digit OTP", width=200); otp_e.pack(pady=10)
    new_p = ctk.CTkEntry(main_frame, placeholder_text="New Password", show="*", width=300); new_p.pack(pady=10)
    
    def update():
        if otp_e.get() == generated_otp:
            with open(USERS_FILE, "r") as f: users = json.load(f)
            users[email] = hash_password(new_p.get())
            with open(USERS_FILE, "w") as f: json.dump(users, f)
            messagebox.showinfo("Success", "Password Updated!")
            load_login_screen()
        else: messagebox.showerror("Error", "Invalid OTP Code.")

    ctk.CTkButton(main_frame, text="Update Password", command=update).pack(pady=20)

# ================= DASHBOARD =================
def load_dashboard():
    clear_main()
    header = ctk.CTkFrame(main_frame, height=80, fg_color="#1F2937")
    header.pack(fill="x", side="top")
    ctk.CTkLabel(header, text="🔐 Cloud Secure Vault", font=("Arial", 22, "bold")).pack(side="left", padx=30)
    ctk.CTkButton(header, text="Logout", fg_color="#EF4444", width=100, command=logout).pack(side="right", padx=30)

    grid = ctk.CTkFrame(main_frame)
    grid.pack(expand=True, fill="both", padx=40, pady=40)
    
    def create_card(r, c, title, color, cmd):
        f = ctk.CTkFrame(grid, corner_radius=15, border_width=1)
        f.grid(row=r, column=c, padx=15, pady=15, sticky="nsew")
        ctk.CTkLabel(f, text=title, font=("Arial", 18, "bold")).pack(pady=20)
        ctk.CTkButton(f, text="Access", fg_color=color, command=cmd).pack(pady=10)

    grid.grid_columnconfigure((0,1), weight=1)
    create_card(0, 0, "☁️ Cloud File Vault", "#10B981", open_cloud_vault)
    create_card(0, 1, "🔑 Password Manager", "#3B82F6", open_password_manager)
    create_card(1, 0, "🍯 Honey Vault (Decoy)", "#F59E0B", open_honey_vault)
    create_card(1, 1, "🗑️ Clear Cloud Data", "#6B7280", reset_account)

def open_cloud_vault():
    clear_main()
    user_cloud_path = os.path.join(CLOUD_STORAGE, current_user)
    if not os.path.exists(user_cloud_path): os.makedirs(user_cloud_path)
    ctk.CTkLabel(main_frame, text="☁️ Cloud Sync Storage", font=("Arial", 24)).pack(pady=20)
    files_box = ctk.CTkScrollableFrame(main_frame, width=600, height=300)
    files_box.pack(pady=10)

    def refresh_list():
        for w in files_box.winfo_children(): w.destroy()
        for f_name in os.listdir(user_cloud_path):
            f_row = ctk.CTkFrame(files_box); f_row.pack(fill="x", pady=2)
            ctk.CTkLabel(f_row, text=f_name).pack(side="left", padx=10)
            ctk.CTkButton(f_row, text="Download", width=80, command=lambda fn=f_name: download_file(fn)).pack(side="right", padx=5)

    def upload_file():
        path = filedialog.askopenfilename()
        if path:
            with open(path, "rb") as f: data = f.read()
            with open(os.path.join(user_cloud_path, os.path.basename(path)+".vault"), "wb") as f:
                f.write(fernet.encrypt(data))
            refresh_list()

    def download_file(filename):
        save_to = filedialog.asksaveasfilename(initialfile=filename.replace(".vault", ""))
        if save_to:
            with open(os.path.join(user_cloud_path, filename), "rb") as f: enc_data = f.read()
            with open(save_to, "wb") as f: f.write(fernet.decrypt(enc_data))
            messagebox.showinfo("Success", "File Downloaded.")

    ctk.CTkButton(main_frame, text="📤 Upload New File", fg_color="#10B981", command=upload_file).pack(pady=10)
    ctk.CTkButton(main_frame, text="Back", command=load_dashboard).pack()
    refresh_list()

def open_password_manager():
    clear_main()
    user_path = os.path.join(CLOUD_STORAGE, current_user)
    pass_file = os.path.join(user_path, "passwords.json.enc")
    ctk.CTkLabel(main_frame, text="🔑 Secure Passwords", font=("Arial", 24)).pack(pady=20)
    site_e = ctk.CTkEntry(main_frame, placeholder_text="Website Name", width=300); site_e.pack(pady=5)
    pass_e = ctk.CTkEntry(main_frame, placeholder_text="Password", width=300, show="*"); pass_e.pack(pady=5)

    def save_pass():
        data = {}
        if os.path.exists(pass_file):
            with open(pass_file, "rb") as f: data = json.loads(fernet.decrypt(f.read()).decode())
        data[site_e.get()] = pass_e.get()
        with open(pass_file, "wb") as f: f.write(fernet.encrypt(json.dumps(data).encode()))
        messagebox.showinfo("Cloud", "Saved to Cloud.")

    def view_pass():
        if not os.path.exists(pass_file): return
        with open(pass_file, "rb") as f: data = json.loads(fernet.decrypt(f.read()).decode())
        msg = "\n".join([f"{k}: {v}" for k, v in data.items()])
        messagebox.showinfo("Vault", msg)

    ctk.CTkButton(main_frame, text="Add", command=save_pass).pack(pady=10)
    ctk.CTkButton(main_frame, text="View All", command=view_pass).pack()
    ctk.CTkButton(main_frame, text="Back", command=load_dashboard).pack(pady=20)

def open_honey_vault():
    clear_main()
    ctk.CTkLabel(main_frame, text="🍯 Decoy Vault Data", font=("Arial", 20)).pack(pady=20)
    ctk.CTkLabel(main_frame, text="Bank: **** 9921\nCrypto: 0x71C...34f", fg_color="gray20", padx=20, pady=20).pack()
    ctk.CTkButton(main_frame, text="Exit Decoy", command=load_dashboard).pack(pady=20)

# ================= ADMIN =================
def load_admin_dashboard():
    clear_main()
    ctk.CTkLabel(main_frame, text="🛡️ ADMIN SYSTEM LOGS", font=("Arial", 26, "bold")).pack(pady=20)
    scroll_frame = ctk.CTkScrollableFrame(main_frame, width=800, height=450); scroll_frame.pack(pady=10)
    
    for user, count in attack_alerts.items():
        if count > 0:
            u_frame = ctk.CTkFrame(scroll_frame); u_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(u_frame, text=f"Target: {user} | Failed Attempts: {count}", text_color="orange").pack(side="left", padx=10)
    
    ctk.CTkButton(main_frame, text="Logout Admin", fg_color="#EF4444", command=logout).pack(pady=20)

# ================= SYSTEM =================
def reset_account():
    if messagebox.askyesno("Confirm", "Wipe all data?"):
        shutil.rmtree(os.path.join(CLOUD_STORAGE, current_user))
        os.makedirs(os.path.join(CLOUD_STORAGE, current_user))
        messagebox.showinfo("Reset", "Data cleared.")

def logout():
    global current_user
    current_user = None
    stop_face_monitor()
    load_login_screen()

def register():
    clear_main()
    ctk.CTkLabel(main_frame, text="Register Account", font=("Arial", 22)).pack(pady=20)
    e_entry = ctk.CTkEntry(main_frame, placeholder_text="Email", width=250); e_entry.pack(pady=10)
    p_entry = ctk.CTkEntry(main_frame, placeholder_text="Password", show="*", width=250); p_entry.pack(pady=10)

    def save():
        with open(USERS_FILE, "r") as f: users = json.load(f)
        users[e_entry.get()] = hash_password(p_entry.get())
        with open(USERS_FILE, "w") as f: json.dump(users, f)
        os.makedirs(os.path.join(CLOUD_STORAGE, e_entry.get()), exist_ok=True)
        messagebox.showinfo("Success", "Account Created!")
        load_login_screen()

    ctk.CTkButton(main_frame, text="Sign Up", command=save).pack(pady=15)
    ctk.CTkButton(main_frame, text="Back", command=load_login_screen).pack()

def load_login_screen():
    clear_main()
    f = ctk.CTkFrame(main_frame, corner_radius=20)
    f.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(f, text="🔐 SECURE VAULT PRO", font=("Arial", 24, "bold")).pack(pady=25, padx=40)
    global login_email, login_password
    login_email = ctk.CTkEntry(f, placeholder_text="Email", width=280); login_email.pack(pady=10)
    login_password = ctk.CTkEntry(f, placeholder_text="Password", show="*", width=280); login_password.pack(pady=10)
    ctk.CTkButton(f, text="Login", width=280, command=login).pack(pady=10)
    ctk.CTkButton(f, text="Forgot Password?", fg_color="transparent", text_color="gray", command=open_forgot_password).pack()
    ctk.CTkButton(f, text="Create Account", width=280, fg_color="transparent", border_width=1, command=register).pack(pady=5)

load_login_screen()
app.mainloop()
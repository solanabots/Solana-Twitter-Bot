import tkinter as tk
from tkinter import messagebox, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import subprocess
import sys
import os
import json
import platform

class TwitterBotGUI:
    def __init__(self, master):
        self.master = master
        master.title("Twitter Sniper for Solana Tokens")
        master.geometry("600x550")

        style = ttk.Style("darkly")
        style.configure("TButton", font=("Helvetica", 12))
        style.configure("TLabel", font=("Helvetica", 12))
        style.configure("TEntry", font=("Helvetica", 12))

        self.process = None
        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        main_frame = ttk.Frame(self.master, padding="20")
        main_frame.pack(fill=BOTH, expand=YES)

        ttk.Label(main_frame, text="Twitter Sniper for Solana Tokens", font=("Helvetica", 18, "bold"), 
                  bootstyle="warning").pack(pady=10)

        fields = [
            ("Private Keys (comma-separated):", "private_keys"),
            ("Accounts (username:email:password):", "accounts"),
            ("User ID to Monitor:", "user_id"),
            ("Amount to Swap (per wallet):", "amount_to_swap"),
            ("Discord Webhook (optional):", "discord"),
            ("Proxy URL (optional):", "proxy_url"),
            ("Capsolver API Key (optional):", "capsolver_api_key")
        ]

        self.entries = {}
        for label, key in fields:
            frame = ttk.Frame(main_frame)
            frame.pack(fill=X, pady=5)
            ttk.Label(frame, text=label, width=30).pack(side=LEFT)
            entry = ttk.Entry(frame, bootstyle="warning")
            entry.pack(side=LEFT, expand=YES, fill=X)
            self.entries[key] = entry

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=10)
        ttk.Button(button_frame, text="Run Bot", command=self.run_bot, 
                   bootstyle="success").pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Save Config", command=self.save_config, 
                   bootstyle="info").pack(side=RIGHT, padx=5)
        ttk.Button(button_frame, text="Load Config", command=self.load_config, 
                   bootstyle="info").pack(side=RIGHT, padx=5)

    def run_bot(self):
        if self.process and self.process.poll() is None:
            messagebox.showinfo("Info", "Bot is already running.")
            return

        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twitter.py")
        if not os.path.exists(script_path):
            messagebox.showerror("Error", "twitter.py not found in the same directory.")
            return

        command = [sys.executable, script_path]
        for key, entry in self.entries.items():
            value = entry.get().strip()
            if value:
                command.extend([f"--{key}", value])

        system = platform.system()
        if system == "Windows":
            self.process = subprocess.Popen(["start", "cmd", "/k"] + command, shell=True)
        elif system == "Darwin":  # macOS
            self.process = subprocess.Popen(["osascript", "-e", 
                f'tell application "Terminal" to do script "{" ".join(command)}"'])
        else:  # Linux and other Unix-like systems
            self.process = subprocess.Popen(["x-terminal-emulator", "-e"] + command)

        messagebox.showinfo("Info", "Bot started in a new terminal window.")

    def save_config(self):
        config = {key: entry.get() for key, entry in self.entries.items()}
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(config, f, indent=4)
            messagebox.showinfo("Info", "Configuration saved successfully.")

    def load_config(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    config = json.load(f)
                for key, value in config.items():
                    if key in self.entries:
                        self.entries[key].delete(0, END)
                        self.entries[key].insert(0, value)
                messagebox.showinfo("Info", "Configuration loaded successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")

if __name__ == "__main__":
    root = ttk.Window(themename="darkly")
    app = TwitterBotGUI(root)
    root.mainloop()
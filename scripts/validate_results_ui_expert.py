from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import pandas as pd
from PIL import Image, ImageTk


# ============================================================
# GLOBAL VARIABLES
# ============================================================

current_index = 0
df = pd.DataFrame()

image_paths = []
valid_crop_values = []  # "valid" or "dismissed"
expert_id_free_values = []  # Free text
expert_id_checklist_values = []  # Selected from checklist

output_path = Path()
image_dir = Path()
metadata_path = Path()

# Species list (loaded from CSV)
species_list = []


# ============================================================
# MAIN GUI CLASS
# ============================================================

class ImageValidatorGUI:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Crop Validator")
        self.root.configure(bg="black")
        self.root.resizable(True, True)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        win_w = int(screen_w * 0.8)
        win_h = int(screen_h * 0.8)

        self.root.geometry(f"{win_w}x{win_h}")

        # ========================================================
        # INIT WINDOW: SELECT DATA & VALIDATION CRITERIA
        # ========================================================

        self.init_frame = tk.Frame(root, bg="black")
        self.init_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title (centered)
        title = tk.Label(
            self.init_frame,
            text="Setup Validation Run",
            font=("Arial", 16, "bold"),
            bg="black",
            fg="#00aeff"
        )
        title.pack(pady=10)

        # Directory Selection (centered)
        self.dir_frame = tk.Frame(self.init_frame, bg="black")
        self.dir_frame.pack(fill=tk.X, pady=10, padx=20, anchor="center")

        tk.Label(
            self.dir_frame,
            text="📁 Processed Data Directory:",
            font=("Arial", 12),
            bg="black",
            fg="white"
        ).pack(anchor="center")

        self.dir_path_label = tk.Label(
            self.dir_frame,
            text="Not selected",
            font=("Arial", 12),
            bg="black",
            fg="#888888",
            wraplength=win_w - 100,
            justify=tk.LEFT
        )
        self.dir_path_label.pack(anchor="center", pady=(2, 5))

        self.dir_button = tk.Button(
            self.dir_frame,
            text="Browse...",
            font=("Arial", 12),
            bg="#2d2d2d",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.select_image_dir
        )
        self.dir_button.pack(anchor="center")

        # Metadata CSV Selection (centered)
        self.csv_frame = tk.Frame(self.init_frame, bg="black")
        self.csv_frame.pack(fill=tk.X, pady=10, padx=20, anchor="center")

        tk.Label(
            self.csv_frame,
            text="📁 Subsampled Metadata CSV:",
            font=("Arial", 12),
            bg="black",
            fg="white"
        ).pack(anchor="center")

        self.csv_path_label = tk.Label(
            self.csv_frame,
            text="Not selected",
            font=("Arial", 12),
            bg="black",
            fg="#888888",
            wraplength=win_w - 100,
            justify=tk.LEFT
        )
        self.csv_path_label.pack(anchor="center", pady=(2, 5))

        self.csv_button = tk.Button(
            self.csv_frame,
            text="Browse...",
            font=("Arial", 12),
            bg="#2d2d2d",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.select_metadata_csv
        )
        self.csv_button.pack(anchor="center")

        # Species Checklist (auto-loaded)
        self.species_file_label = tk.Label(
            self.init_frame,
            text="📁 Species Checklist (auto-loaded):",
            font=("Arial", 12),
            bg="black",
            fg="white"
        )
        self.species_file_label.pack(anchor="center", pady=(10, 0))

        self.species_path_label = tk.Label(
            self.init_frame,
            text="checklist_syrphids_simple.csv",
            font=("Arial", 12),
            bg="black",
            fg="#888888",
            wraplength=win_w - 100,
            justify=tk.LEFT
        )
        self.species_path_label.pack(anchor="center", pady=(2, 5))

        # ✅ Create feedback_label here (after init_frame)
        self.feedback_label = tk.Label(
            self.init_frame,
            text="",
            font=("Arial", 12),
            bg="black",
            fg="#d69111"
        )
        self.feedback_label.pack(pady=5)

        # Row Count Display (NEW: shows number of rows after CSV selected)
        self.row_count_label = tk.Label(
            self.init_frame,
            text="",
            font=("Arial", 12),
            bg="black",
            fg="#00ff88"
        )
        self.row_count_label.pack(pady=5)

        # Start Button (centered)
        self.start_button = tk.Button(
            self.init_frame,
            text="▶️ Start Validation",
            font=("Arial", 12, "bold"),
            bg="#0d5b9b",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.start_validation_flow
        )
        self.start_button.pack(pady=20)

        # Reset state
        self.reset()

    # ============================================================
    # LOAD SPECIES LIST FROM CSV (now safe to use feedback_label)
    # ============================================================

    def load_species_list(self):
        global species_list
        script_dir = Path(__file__).parent  # Same folder as script
        checklist_path = script_dir / "checklist_syrphids_simple.csv"

        if not checklist_path.exists():
            self.feedback_label.config(text="⚠️ Checklist file not found: checklist_syrphids_simple.csv")
            return

        try:
            species_df = pd.read_csv(checklist_path)
            if "species" not in species_df.columns:
                self.feedback_label.config(text="⚠️ Checklist must have a 'species' column")
                return
            species_list = species_df["species"].dropna().astype(str).tolist()
            self.feedback_label.config(text=f"✅ Loaded {len(species_list)} species")
        except Exception as e:
            self.feedback_label.config(text=f"⚠️ Error loading checklist: {e}")

    # ============================================================
    # RESET
    # ============================================================

    def reset(self):
        global current_index, df, image_paths, valid_crop_values, expert_id_free_values, expert_id_checklist_values
        global output_path, image_dir, metadata_path, species_list

        current_index = 0
        df = pd.DataFrame()
        image_paths = []
        valid_crop_values = []
        expert_id_free_values = []
        expert_id_checklist_values = []
        output_path = Path()
        image_dir = Path()
        metadata_path = Path()
        species_list = []

        self.dir_path_label.config(text="Not selected")
        self.csv_path_label.config(text="Not selected")
        self.row_count_label.config(text="")
        self.feedback_label.config(text="")

    # ============================================================
    # SELECT IMAGE DIRECTORY
    # ============================================================

    def select_image_dir(self):
        dir_path = filedialog.askdirectory(title="Select Image Directory")
        if not dir_path:
            return
        global image_dir
        image_dir = Path(dir_path)
        self.dir_path_label.config(text=str(image_dir))
        self.feedback_label.config(text="✅ Directory selected")

    # ============================================================
    # SELECT METADATA CSV
    # ============================================================

    def select_metadata_csv(self):
        file_path = filedialog.askopenfilename(
            title="Select Metadata CSV",
            filetypes=[("CSV files", "*.csv")]
        )
        if not file_path:
            return
        global metadata_path
        metadata_path = Path(file_path)
        self.csv_path_label.config(text=str(metadata_path))

        try:
            # Load CSV to count rows
            df_temp = pd.read_csv(metadata_path)
            row_count = len(df_temp)
            self.row_count_label.config(text=f"📊 {row_count} rows in file")
            self.feedback_label.config(text="✅ CSV loaded successfully")
        except Exception as e:
            self.row_count_label.config(text="❌ Failed to read file")
            self.feedback_label.config(text=f"⚠️ Error: {e}")

    # ============================================================
    # START VALIDATION FLOW
    # ============================================================

    def start_validation_flow(self):
        global image_dir, metadata_path

        # Validate inputs
        if not image_dir or not image_dir.exists():
            messagebox.showwarning("Missing Directory", "Please select a valid image directory.")
            return

        if not metadata_path or not metadata_path.exists():
            messagebox.showwarning("Missing CSV", "Please select a valid metadata CSV.")
            return

        # ✅ Load species list AFTER GUI is fully initialized
        self.load_species_list()

        if not species_list:
            messagebox.showwarning("No Species List", "Species checklist not loaded.")
            return

        # Load CSV
        try:
            global df
            df = pd.read_csv(metadata_path)

            required_cols = [
                "crop_path",
                "duration_s",
                "top1_prob_weighted",
                "det_conf_mean"
            ]

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                messagebox.showerror("Missing Columns", f"Missing required columns:\n{missing}")
                return

            # Reinitialize validation values
            global valid_crop_values, expert_id_free_values, expert_id_checklist_values
            valid_crop_values = ["valid"] * len(df)  # Default: "valid"
            expert_id_free_values = [None] * len(df)
            expert_id_checklist_values = [None] * len(df)

            # Build filename index
            filename_to_path = {}
            for root, _, files in os.walk(image_dir):
                for file in files:
                    filename_to_path[file.lower()] = Path(root) / file

            # Update image paths
            global image_paths
            image_paths = []
            for _, row in df.iterrows():
                filename = Path(row["crop_path"]).name.lower()
                image_paths.append(filename_to_path.get(filename))

            # Set output path: same dir as input CSV, with _identified.csv
            global output_path
            output_path = metadata_path.parent / f"{metadata_path.stem}_identified.csv"

            # Hide init frame
            self.init_frame.pack_forget()

            # Create validation window
            self.create_validation_window()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV:\n{e}")

    # ============================================================
    # CREATE VALIDATION WINDOW (IMAGE + TWO FIELDS + RADIO BUTTONS + SUBMIT + BACK)
    # ============================================================

    def create_validation_window(self):
        global df, image_paths, valid_crop_values, expert_id_free_values, expert_id_checklist_values, output_path

        df = df.copy()

        # Main container (centered)
        self.main_container = tk.Frame(self.root, bg="black")
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Centering frame
        self.center_frame = tk.Frame(self.main_container, bg="black")
        self.center_frame.pack(expand=True)

        # Image Frame (centered)
        self.image_frame = tk.Frame(self.center_frame, bg="black")
        self.image_frame.pack(pady=10)

        self.image_label = tk.Label(
            self.image_frame,
            text="No image loaded",
            bg="black",
            fg="white",
            font=("Arial", 12),
            relief=tk.RAISED,
            bd=2
        )
        self.image_label.pack(expand=True, fill=tk.BOTH)

        # Free Text Field (top)
        self.free_frame = tk.Frame(self.center_frame, bg="black")
        self.free_frame.pack(pady=10)

        self.free_label = tk.Label(
            self.free_frame,
            text="📝 Free Text Entry",
            font=("Arial", 12, "bold"),
            bg="black",
            fg="#00ff88"
        )
        self.free_label.pack(anchor="center", pady=(0, 5))

        self.free_text = tk.Text(
            self.free_frame,
            height=3,
            font=("Arial", 12),
            wrap=tk.WORD,
            bg="#2d2d2d",
            fg="white",
            relief=tk.SUNKEN,
            bd=2,
            padx=8,
            pady=8
        )
        self.free_text.pack(fill=tk.X, pady=2)

        # Checklist Dropdown (below free text)
        self.checklist_frame = tk.Frame(self.center_frame, bg="black")
        self.checklist_frame.pack(pady=10)

        self.checklist_label = tk.Label(
            self.checklist_frame,
            text="🔍 Species Checklist",
            font=("Arial", 12, "bold"),
            bg="black",
            fg="#00ff88"
        )
        self.checklist_label.pack(anchor="center", pady=(0, 5))

        # Autocomplete Combobox (readonly)
        self.checklist_var = tk.StringVar()
        self.checklist_combo = ttk.Combobox(
            self.checklist_frame,
            textvariable=self.checklist_var,
            values=species_list,
            state="readonly",  # ✅ No free text allowed
            font=("Arial", 12),
            width=30
        )
        self.checklist_combo.pack(fill=tk.X, pady=2)

        # ✅ BINDING: Open dropdown on click
        self.checklist_combo.bind("<Button-1>", self.on_checklist_click)

        # ✅ BINDING: Filter on key release
        self.checklist_combo.bind("<KeyRelease>", self.on_checklist_key_release)
        self.checklist_combo.bind("<<ComboboxSelected>>", self.on_checklist_selected)

        # Radio Buttons Frame (same line, side-by-side)
        self.radio_frame = tk.Frame(self.center_frame, bg="black")
        self.radio_frame.pack(pady=10)

        # Radio button variable
        self.valid_crop_var = tk.StringVar(value="valid")

        # Keep Crop Button (smaller, green when active)
        self.keep_radio = tk.Radiobutton(
            self.radio_frame,
            text="✅ Keep crop",
            variable=self.valid_crop_var,
            value="valid",
            bg="black",
            fg="white",
            font=("Arial", 10),
            selectcolor="green",
            indicatoron=0,
            width=14,
            height=1,
            relief=tk.RAISED,
            bd=2,
            command=lambda: self.set_valid_crop(self.valid_crop_var.get())
        )
        self.keep_radio.pack(side=tk.LEFT, padx=2)

        # Dismiss Crop Button (smaller, red when active)
        self.dismiss_radio = tk.Radiobutton(
            self.radio_frame,
            text="❌ Dismiss crop",
            variable=self.valid_crop_var,
            value="dismissed",
            bg="black",
            fg="white",
            font=("Arial", 10),
            selectcolor="red",
            indicatoron=0,
            width=14,
            height=1,
            relief=tk.RAISED,
            bd=2,
            command=lambda: self.set_valid_crop(self.valid_crop_var.get())
        )
        self.dismiss_radio.pack(side=tk.LEFT, padx=2)

        # Buttons Frame (centered)
        self.button_frame = tk.Frame(self.center_frame, bg="black")
        self.button_frame.pack(pady=10)

        # Submit Button (centered)
        self.submit_button = tk.Button(
            self.button_frame,
            text="✅ Submit",
            font=("Arial", 12, "bold"),
            bg="#00aa00",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.submit_label
        )
        self.submit_button.pack(side=tk.LEFT, padx=10)

        # Go Back Button
        self.back_button = tk.Button(
            self.center_frame,
            text="↩️ Go Back",
            font=("Arial", 12),
            bg="#2d2d2d",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.go_back
        )
        self.back_button.pack(pady=5)

        # Status
        self.status_label = tk.Label(
            self.center_frame,
            text="Status: Ready",
            font=("Arial", 12),
            bg="black",
            fg="#00ff88"
        )
        self.status_label.pack(pady=5)

        # Save & Exit (with warning)
        self.save_button = tk.Button(
            self.center_frame,
            text="💾 Save & Return to Setup",
            font=("Arial", 12, "bold"),
            bg="#007acc",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.save_and_return_with_warning
        )
        self.save_button.pack(pady=15)

        # Show first image
        self.show_next_image()

    # ============================================================
    # AUTOCOMPLETE: FILTER LIST ON KEY RELEASE (FIXED)
    # ============================================================

    def on_checklist_key_release(self, event):
        # Get typed text
        typed = self.checklist_var.get().lower()

        # Clear values if empty
        if not typed:
            self.checklist_combo['values'] = species_list
            return

        # Filter list
        filtered = [s for s in species_list if typed in s.lower()]
        self.checklist_combo['values'] = filtered

        # If matches found, show dropdown
        if filtered:
            # Force dropdown to open
            self.checklist_combo.event_generate('<Down>')
            # Ensure focus stays
            self.checklist_combo.focus_force()
        else:
            # No matches → clear
            self.checklist_combo['values'] = []

    # ============================================================
    # ON CLICK: FORCE DROPDOWN TO OPEN
    # ============================================================

    def on_checklist_click(self, event):
        """Force the dropdown to open when clicking on the empty combobox."""
        self.checklist_combo.event_generate('<Down>')
        self.checklist_combo.focus_force()

    # ============================================================
    # ON SELECTED: Save selected species
    # ============================================================

    def on_checklist_selected(self, event):
        # When user selects from dropdown
        selected = self.checklist_var.get()
        if selected:
            self.checklist_var.set(selected)

    # ============================================================
    # SET VALID CROP (called by radio button)
    # ============================================================

    def set_valid_crop(self, value: str):
        global current_index
        valid_crop_values[current_index] = value

        # Update button appearance
        if value == "valid":
            self.keep_radio.config(bg="#00aa00", fg="white", relief=tk.SUNKEN, bd=4)
            self.dismiss_radio.config(bg="black", fg="white", relief=tk.RAISED, bd=2)
        else:
            self.dismiss_radio.config(bg="#aa0000", fg="white", relief=tk.SUNKEN, bd=4)
            self.keep_radio.config(bg="black", fg="white", relief=tk.RAISED, bd=2)

    # ============================================================
    # SHOW NEXT IMAGE
    # ============================================================

    def show_next_image(self):
        global current_index, df, image_paths

        if current_index >= len(df):
            # All images validated
            self.status_label.config(text="✅ All images validated!")
            self.submit_button.config(state=tk.DISABLED)
            self.back_button.config(state=tk.DISABLED)
            self.save_button.config(state=tk.NORMAL)
            return

        image_path = image_paths[current_index]
        if not image_path or not image_path.exists():
            self.image_label.config(image="", text="Image not found")
            return

        try:
            self.root.update_idletasks()
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()

            max_width = int(window_width * 0.7)
            max_height = int(window_height * 0.4)

            img = Image.open(image_path)
            orig_width, orig_height = img.size

            scale_x = max_width / orig_width
            scale_y = max_height / orig_height
            scale = min(scale_x, scale_y)

            new_width = int(orig_width * scale)
            new_height = int(orig_height * scale)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            self.photo = photo
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo

            self.status_label.config(text=f"Status: {current_index + 1}/{len(df)}")

            # Load saved values
            free_comment = expert_id_free_values[current_index] or ""
            checklist_comment = expert_id_checklist_values[current_index] or ""
            self.free_text.delete(1.0, tk.END)
            self.free_text.insert(tk.END, free_comment)
            self.checklist_var.set(checklist_comment)

            # Update radio button state
            if valid_crop_values[current_index] == "valid":
                self.valid_crop_var.set("valid")
                self.set_valid_crop("valid")
            else:
                self.valid_crop_var.set("dismissed")
                self.set_valid_crop("dismissed")

        except Exception as e:
            self.image_label.config(image="", text=f"Error: {e}")

    # ============================================================
    # SUBMIT LABEL (WITH WARNING ON EMPTY FIELDS)
    # ============================================================

    def submit_label(self):
        global current_index, valid_crop_values, expert_id_free_values, expert_id_checklist_values

        # Get current values
        free_text = self.free_text.get(1.0, tk.END).strip()
        checklist_text = self.checklist_var.get().strip()

        # Check if valid_crop is "valid" AND both fields are empty
        if valid_crop_values[current_index] == "valid" and not free_text and not checklist_text:
            # Show warning
            result = messagebox.askyesno(
                title="⚠️ Warning",
                message=(
                    "⚠️ Warning: You did not enter an identification result yet.\n"
                    "Do you want to continue to the next image?"
                ),
                icon="warning"
            )

            if not result:
                # User said "No" → stay on current image
                return  # Do not advance

        # Save both values
        expert_id_free_values[current_index] = free_text or None
        expert_id_checklist_values[current_index] = checklist_text or None

        # Move to next image
        current_index += 1
        self.show_next_image()

    # ============================================================
    # GO BACK BUTTON
    # ============================================================

    def go_back(self):
        global current_index

        if current_index <= 0:
            messagebox.showwarning("Cannot Go Back", "Already at the first image.")
            return

        current_index -= 1
        self.show_next_image()

    # ============================================================
    # SAVE & RETURN TO INIT (WITH WARNING)
    # ============================================================

    def save_and_return_with_warning(self):
        # Show warning popup
        result = messagebox.askyesno(
            title="⚠️ Warning",
            message=(
                "⚠️ Warning: Going back to setup will save your current results,\n"
                "but you will not be able to jump back to where you left off.\n"
                "You’ll need to start from the beginning.\n\n"
                "Are you sure you want to proceed?"
            ),
            icon="warning"
        )

        if result:
            # Proceed with save and return
            self.save_and_return()
        else:
            # Cancel
            messagebox.showinfo("Cancelled", "Return to setup was cancelled.")

    # ============================================================
    # SAVE & RETURN TO INIT (INTERNAL)
    # ============================================================

    def save_and_return(self):
        global df, valid_crop_values, expert_id_free_values, expert_id_checklist_values, output_path

        if len(df) == 0:
            messagebox.showwarning("No Data", "No data to save.")
            return

        out_df = df.copy()
        out_df["valid_crop"] = valid_crop_values
        out_df["expert_id_free"] = expert_id_free_values
        out_df["expert_id_checklist"] = expert_id_checklist_values

        try:
            out_df.to_csv(output_path, index=False)
            messagebox.showinfo("Saved", f"Saved to:\n{output_path}")

            # Return to init window
            self.main_container.pack_forget()
            self.init_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # Reset validation state
            self.reset()

        except Exception as e:
            messagebox.showerror("Save Error", str(e))


# ============================================================
# MAIN
# ============================================================

def main():
    root = tk.Tk()
    app = ImageValidatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
    
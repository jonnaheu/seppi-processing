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
validation_labels = []
comments = []

output_path = Path()
image_dir = Path()
metadata_path = Path()

# Store user choices
selected_validation_criteria = None  # "pollinator", "bioclip"
selected_taxonomic_level = None  # "species", "genus", "family", "order"
strata_number = None  # 1 to 8


# ============================================================
# MAIN GUI CLASS
# ============================================================

class ImageValidatorGUI:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Validator - Multi-Strata Setup")
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
            text="Image Validation Setup (Multi-Strata)",
            font=("Arial", 16, "bold"),
            bg="black",
            fg="#00ff88"
        )
        title.pack(pady=10)

        # Directory Selection
        self.dir_frame = tk.Frame(self.init_frame, bg="black")
        self.dir_frame.pack(fill=tk.X, pady=10)

        tk.Label(
            self.dir_frame,
            text="📁 Processed Image Directory:",
            font=("Arial", 12),
            bg="black",
            fg="white"
        ).pack(anchor="w")

        self.dir_path_label = tk.Label(
            self.dir_frame,
            text="Not selected",
            font=("Arial", 12),
            bg="black",
            fg="#888888",
            wraplength=win_w - 100,
            justify=tk.LEFT
        )
        self.dir_path_label.pack(anchor="w", pady=(2, 5))

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
        self.dir_button.pack(anchor="w")

        # Metadata CSV Selection
        self.csv_frame = tk.Frame(self.init_frame, bg="black")
        self.csv_frame.pack(fill=tk.X, pady=10)

        tk.Label(
            self.csv_frame,
            text="📁 Subsampled Metadata CSV:",
            font=("Arial", 12),
            bg="black",
            fg="white"
        ).pack(anchor="w")

        self.csv_path_label = tk.Label(
            self.csv_frame,
            text="Not selected",
            font=("Arial", 12),
            bg="black",
            fg="#888888",
            wraplength=win_w - 100,
            justify=tk.LEFT
        )
        self.csv_path_label.pack(anchor="w", pady=(2, 5))

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
        self.csv_button.pack(anchor="w")

        # Validation Criteria (centered)
        self.criteria_frame = tk.Frame(self.init_frame, bg="black")
        self.criteria_frame.pack(fill=tk.X, pady=10)

        tk.Label(
            self.criteria_frame,
            text="🎯 Validation Criteria:",
            font=("Arial", 12),
            bg="black",
            fg="white"
        ).pack(anchor="center", pady=(0, 10))

        self.criteria_var = tk.StringVar(value="")

        criteria_options = [
            ("Assess if a pollinator is present", "pollinator"),
            ("Validate Bioclip classification result", "bioclip"),
        ]

        # Create a frame to group the second option
        self.bioclip_frame = tk.Frame(self.init_frame, bg="black")
        self.bioclip_frame.pack(fill=tk.X, pady=10)

        # Create radio buttons with checkmarks
        self.radio_buttons = {}
        for text, value in criteria_options:
            label_text = f"✓ {text}"
            rb = tk.Radiobutton(
                self.criteria_frame,
                text=label_text,
                variable=self.criteria_var,
                value=value,
                bg="black",
                fg="white",
                font=("Arial", 12),
                selectcolor="gray",
                anchor="w",
                indicatoron=0,
                width=40,
                height=2,
                relief=tk.RAISED,
                bd=2,
                command=lambda v=value: self.on_criteria_change(v)
            )
            rb.pack(anchor="w", padx=20, pady=5)
            self.radio_buttons[value] = rb

        # Taxonomic Level (only for "bioclip")
        self.tax_frame = tk.Frame(self.bioclip_frame, bg="black")
        self.tax_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            self.tax_frame,
            text="🔍 Taxonomic Level:",
            font=("Arial", 12),
            bg="black",
            fg="white"
        ).pack(anchor="w")

        self.tax_var = tk.StringVar(value="")

        self.tax_combo = ttk.Combobox(
            self.tax_frame,
            textvariable=self.tax_var,
            values=["Genus", "Family", "Species", "Order"],
            state="readonly",
            font=("Arial", 12),
            width=15
        )
        self.tax_combo.pack(anchor="w", pady=(2, 5))

        # Feedback labels
        self.feedback_label = tk.Label(
            self.init_frame,
            text="",
            font=("Arial", 12),
            bg="black",
            fg="#00ff88"
        )
        self.feedback_label.pack(pady=5)

        # Start Button
        self.start_button = tk.Button(
            self.init_frame,
            text="▶️ Start Validation",
            font=("Arial", 12, "bold"),
            bg="#007acc",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.start_validation_flow
        )
        self.start_button.pack(pady=20)

        # Reset state
        self.reset()

    # ============================================================
    # RESET
    # ============================================================

    def reset(self):
        global current_index, df, image_paths, validation_labels, comments
        global output_path, image_dir, metadata_path, selected_validation_criteria, selected_taxonomic_level, strata_number

        current_index = 0
        df = pd.DataFrame()
        image_paths = []
        validation_labels = []
        comments = []
        output_path = Path()
        image_dir = Path()
        metadata_path = Path()
        selected_validation_criteria = None
        selected_taxonomic_level = None
        strata_number = None

        self.dir_path_label.config(text="Not selected")
        self.csv_path_label.config(text="Not selected")
        self.criteria_var.set("")
        self.tax_var.set("")
        self.feedback_label.config(text="")

        self.bioclip_frame.pack_forget()

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

        # Extract strata number from filename
        stem = metadata_path.stem
        if stem.startswith("strata"):
            try:
                import re
                match = re.match(r"strata(\d+)", stem)
                if match:
                    strata_num = int(match.group(1))
                    if 1 <= strata_num <= 8:
                        global strata_number
                        strata_number = strata_num
                        self.feedback_label.config(text=f"✅ Strata {strata_num} detected")
                    else:
                        self.feedback_label.config(text="⚠️ Strata number must be 1–8")
                else:
                    self.feedback_label.config(text="⚠️ Invalid filename format: must start with 'strataX_'")
            except Exception as e:
                self.feedback_label.config(text=f"⚠️ Error parsing strata number: {e}")
        else:
            self.feedback_label.config(text="⚠️ Filename must start with 'strataX_'")
    # ============================================================
    # ON CRITERIA CHANGE
    # ============================================================

    def on_criteria_change(self, value):
        if value == "bioclip":
            self.bioclip_frame.pack(fill=tk.X, pady=10)
        else:
            self.bioclip_frame.pack_forget()

    # ============================================================
    # START VALIDATION FLOW
    # ============================================================

    def start_validation_flow(self):
        global image_dir, metadata_path, selected_validation_criteria, selected_taxonomic_level, strata_number

        # Validate inputs
        if not image_dir or not image_dir.exists():
            messagebox.showwarning("Missing Directory", "Please select a valid image directory.")
            return

        if not metadata_path or not metadata_path.exists():
            messagebox.showwarning("Missing CSV", "Please select a valid metadata CSV.")
            return

        selected_validation_criteria = self.criteria_var.get()
        if not selected_validation_criteria:
            messagebox.showwarning("No Criteria Selected", "Please select a validation criterion.")
            return

        if selected_validation_criteria == "bioclip":
            selected_taxonomic_level = self.tax_var.get()
            if not selected_taxonomic_level:
                messagebox.showwarning("No Taxonomic Level", "Please select a taxonomic level for Bioclip validation.")
                return
        else:
            selected_taxonomic_level = None

        # Load CSV
        try:
            global df
            df = pd.read_csv(metadata_path)

            required_cols = [
                "crop_path",
                "bioclip_species",
                "bioclip_genus",
                "bioclip_family",
                "bioclip_order",
                "duration_s",
                "top1_prob_weighted",
                "det_conf_mean"
            ]

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                messagebox.showerror("Missing Columns", f"Missing required columns:\n{missing}")
                return

            # ✅ Reinitialize validation_labels and comments
            global validation_labels, comments
            validation_labels = [None] * len(df)
            comments = [None] * len(df)

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

            # Set output path
            global output_path
            output_path = metadata_path.parent / f"{metadata_path.stem}_validated.csv"

            # Hide init frame
            self.init_frame.pack_forget()

            # Create validation window
            self.create_validation_window()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV:\n{e}")

    # ============================================================
    # CREATE VALIDATION WINDOW (SINGLE PANEL, CENTERED)
    # ============================================================

    def create_validation_window(self):
        global df, image_paths, validation_labels, comments, output_path, selected_validation_criteria, selected_taxonomic_level, strata_number

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

        # Info Frame (centered)
        self.info_frame = tk.Frame(self.center_frame, bg="black")
        self.info_frame.pack(pady=10)

        # Smaller, white title
        self.info_title = tk.Label(
            self.info_frame,
            text="Bioclip Classification",
            font=("Arial", 10),
            bg="black",
            fg="white"
        )
        self.info_title.pack(anchor="center", pady=(0, 5))

        self.labels = {}

        # Dynamic label based on strata and criteria
        if strata_number in [1, 2]:
            # Pollinator: show species as fallback
            self.labels["Species"] = tk.Label(
                self.info_frame,
                text="N/A",
                font=("Arial", 14, "bold"),
                bg="black",
                fg="white",
                width=30,
                anchor="center",
                relief=tk.SUNKEN,
                bd=1
            )
            self.labels["Species"].pack(pady=2)
        else:
            # Taxonomic level: show selected level
            level = selected_taxonomic_level.lower()
            label_text = f"{level.title()}"
            self.labels[label_text] = tk.Label(
                self.info_frame,
                text="N/A",
                font=("Arial", 14, "bold"),
                bg="black",
                fg="white",
                width=30,
                anchor="center",
                relief=tk.SUNKEN,
                bd=1
            )
            self.labels[label_text].pack(pady=2)

        # Buttons Frame (centered)
        self.button_frame = tk.Frame(self.center_frame, bg="black")
        self.button_frame.pack(pady=10)

        # Dynamic button labels based on criteria
        if strata_number in [1, 2]:
            self.correct_btn = tk.Button(
                self.button_frame,
                text="✅ Pollinator",
                font=("Arial", 12),
                bg="#00aa00",
                fg="white",
                relief=tk.RAISED,
                bd=2,
                command=lambda: self.submit_label("pollinator")
            )
            self.incorrect_btn = tk.Button(
                self.button_frame,
                text="❌ Not a Pollinator",
                font=("Arial", 12),
                bg="#aa0000",
                fg="white",
                relief=tk.RAISED,
                bd=2,
                command=lambda: self.submit_label("non-pollinator")
            )
            self.unclear_btn = tk.Button(
                self.button_frame,
                text="❓ Unclear",
                font=("Arial", 12),
                bg="#ff8800",
                fg="white",
                relief=tk.RAISED,
                bd=2,
                command=lambda: self.submit_label("unclear")
            )
        else:
            self.correct_btn = tk.Button(
                self.button_frame,
                text="✅ Correct",
                font=("Arial", 12),
                bg="#00aa00",
                fg="white",
                relief=tk.RAISED,
                bd=2,
                command=lambda: self.submit_label("correct")
            )
            self.incorrect_btn = tk.Button(
                self.button_frame,
                text="❌ Incorrect",
                font=("Arial", 12),
                bg="#aa0000",
                fg="white",
                relief=tk.RAISED,
                bd=2,
                command=lambda: self.submit_label("incorrect")
            )
            self.unclear_btn = tk.Button(
                self.button_frame,
                text="❓ Unclear",
                font=("Arial", 12),
                bg="#ff8800",
                fg="white",
                relief=tk.RAISED,
                bd=2,
                command=lambda: self.submit_label("unclear")
            )

        self.correct_btn.pack(side=tk.LEFT, padx=10)
        self.incorrect_btn.pack(side=tk.LEFT, padx=10)
        self.unclear_btn.pack(side=tk.LEFT, padx=10)

        # Go Back Button (NEW)
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

        # Comment Frame (centered)
        self.comment_frame = tk.Frame(self.center_frame, bg="black")
        self.comment_frame.pack(pady=10)

        self.comment_title = tk.Label(
            self.comment_frame,
            text="📝 Comment (e.g., corrected name)",
            font=("Arial", 12, "bold"),
            bg="black",
            fg="#00ff88"
        )
        self.comment_title.pack(anchor="center", pady=(0, 5))

        self.comment_text = tk.Text(
            self.comment_frame,
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
        self.comment_text.pack(fill=tk.X, pady=2)

        # Status
        self.status_label = tk.Label(
            self.center_frame,
            text="Status: Ready",
            font=("Arial", 12),
            bg="black",
            fg="#00ff88"
        )
        self.status_label.pack(pady=5)

        # Save & Exit
        self.save_button = tk.Button(
            self.center_frame,
            text="💾 Save & Return to Setup",
            font=("Arial", 12, "bold"),
            bg="#007acc",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.save_and_return
        )
        self.save_button.pack(pady=15)

        # Show first image
        self.show_next_image()

    # ============================================================
    # SHOW NEXT IMAGE
    # ============================================================

    def show_next_image(self):
        global current_index, df, image_paths

        if current_index >= len(df):
            messagebox.showinfo("Done", "All images validated!")
            self.save_and_return()
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

            self.update_info_text()

        except Exception as e:
            self.image_label.config(image="", text=f"Error: {e}")

    # ============================================================
    # UPDATE INFO
    # ============================================================

    def update_info_text(self):
        if current_index >= len(df):
            return

        row = df.iloc[current_index]

        if strata_number in [1, 2]:
            # Show species for pollinator
            self.labels["Species"].config(text=row.get("bioclip_species", "N/A"))
        else:
            # Show selected taxonomic level
            level = selected_taxonomic_level.lower()
            if level == "order":
                value = row.get("bioclip_order", "N/A")
                self.labels["Order"].config(text=str(value))
            else:
                value = row.get(f"bioclip_{level}", "N/A")
                self.labels[level.title()].config(text=str(value))

    # ============================================================
    # SUBMIT LABEL
    # ============================================================

    def submit_label(self, label: str):
        global current_index, validation_labels, comments

        validation_labels[current_index] = label
        comments[current_index] = self.comment_text.get(1.0, tk.END).strip()

        self.comment_text.delete(1.0, tk.END)

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
    # SAVE & RETURN TO INIT
    # ============================================================

    def save_and_return(self):
        global df, validation_labels, comments, output_path, selected_validation_criteria, selected_taxonomic_level, strata_number

        if len(df) == 0:
            messagebox.showwarning("No Data", "No data to save.")
            return

        out_df = df.copy()

        # Dynamic column name: valX_level
        if strata_number in [1, 2]:
            col_name = f"val{strata_number}"
        else:
            level = selected_taxonomic_level.lower()
            col_name = f"val{strata_number}_{level}"

        out_df[col_name] = validation_labels
        out_df["comment"] = comments

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
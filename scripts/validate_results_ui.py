from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import pandas as pd
from PIL import Image, ImageTk

# === Configuration ===
DEFAULT_OUTPUT_DIR = Path("validation_results")
DEFAULT_OUTPUT_FILE = "validated_metadata.csv"
DEFAULT_IMAGE_SIZE = (600, 400)  # Max display size

# === Global Variables ===
current_index = 0
df = pd.DataFrame()
image_paths = []
validation_labels = []
output_path = Path()
image_dir = Path()  # Directory where image crops are stored
filename_to_path = {}  # Cache: filename → full path (one per file)
comments = []  # Store user comments


# === Main GUI Class ===
class ImageValidatorGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Validator")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        self.root.configure(bg="black")

        # === Widgets ===
        # Image display
        self.image_label = tk.Label(
            root,
            text="No image loaded",
            bg="black",
            fg="white",
            font=("Arial", 12),
            relief=tk.RAISED,
            bd=2
        )
        self.image_label.pack(pady=10, fill=tk.BOTH, expand=True)

        # === Controls Frame (Top Row) ===
        self.controls_frame = tk.Frame(root, bg="black")
        self.controls_frame.pack(pady=5, fill=tk.X, padx=20)

        # Image Dir Button
        self.image_dir_button = tk.Button(
            self.controls_frame,
            text="📁 Select Image Crops Directory",
            font=("Arial", 11),
            bg="#2d2d2d",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.select_image_dir
        )
        self.image_dir_button.grid(row=0, column=0, padx=5)

        # CSV Button
        self.csv_button = tk.Button(
            self.controls_frame,
            text="📁 Load Metadata CSV",
            font=("Arial", 11),
            bg="#2d2d2d",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.load_csv
        )
        self.csv_button.grid(row=0, column=1, padx=5)

        # Start Button
        self.start_button = tk.Button(
            self.controls_frame,
            text="▶️ Start Validation",
            font=("Arial", 11, "bold"),
            bg="#007acc",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.start_validation
        )
        self.start_button.grid(row=0, column=2, padx=5)

        # === Bioclip Info Frame (Table Style) ===
        self.info_frame = tk.Frame(root, bg="black")
        self.info_frame.pack(pady=5, fill=tk.X, padx=20)

        self.info_title = tk.Label(
            self.info_frame,
            text="Bioclip Classification Results",
            font=("Arial", 14, "bold"),
            bg="black",
            fg="#00ff88"
        )
        self.info_title.pack(anchor="w", pady=(0, 5))

        # Table-style labels
        self.labels = {}
        rows = ["Species", "Genus", "Family", "Order"]
        for i, label in enumerate(rows):
            frame = tk.Frame(self.info_frame, bg="black")
            frame.pack(fill=tk.X, pady=2)

            tk.Label(
                frame,
                text=label + ":",
                font=("Arial", 12, "bold"),
                bg="black",
                fg="#00ff88",
                width=10,
                anchor="w"
            ).pack(side=tk.LEFT, padx=(0, 10))

            self.labels[label] = tk.Label(
                frame,
                text="N/A",
                font=("Arial", 12),
                bg="black",
                fg="white",
                width=30,
                anchor="w",
                relief=tk.SUNKEN,
                bd=1
            )
            self.labels[label].pack(side=tk.LEFT, fill=tk.X, expand=True)

        # === Statistics Frame (New) ===
        self.stats_frame = tk.Frame(root, bg="black")
        self.stats_frame.pack(pady=5, fill=tk.X, padx=20)

        self.stats_title = tk.Label(
            self.stats_frame,
            text="📊 Statistics",
            font=("Arial", 14, "bold"),
            bg="black",
            fg="#00ff88"
        )
        self.stats_title.pack(anchor="w", pady=(0, 5))

        # Statistics labels
        self.stats_labels = {}
        stats_rows = [
            ("Duration of tracking event", "duration_s"),
            ("Top1 weighted prob.", "top1_prob_weighted"),
            ("Mean detection confidence", "det_conf_mean")
        ]
        for i, (label_text, col_name) in enumerate(stats_rows):
            frame = tk.Frame(self.stats_frame, bg="black")
            frame.pack(fill=tk.X, pady=2)

            tk.Label(
                frame,
                text=label_text + ":",
                font=("Arial", 12, "bold"),
                bg="black",
                fg="#00ff88",
                width=20,
                anchor="w"
            ).pack(side=tk.LEFT, padx=(0, 10))

            self.stats_labels[col_name] = tk.Label(
                frame,
                text="N/A",
                font=("Arial", 12),
                bg="black",
                fg="white",
                width=20,
                anchor="w",
                relief=tk.SUNKEN,
                bd=1
            )
            self.stats_labels[col_name].pack(side=tk.LEFT, fill=tk.X, expand=True)

        # === Comment Frame ===
        self.comment_frame = tk.Frame(root, bg="black")
        self.comment_frame.pack(pady=5, fill=tk.X, padx=20)

        self.comment_title = tk.Label(
            self.comment_frame,
            text="📝 Comment (e.g., corrected species name)",
            font=("Arial", 12, "bold"),
            bg="black",
            fg="#00ff88"
        )
        self.comment_title.pack(anchor="w", pady=(0, 5))

        self.comment_text = tk.Text(
            self.comment_frame,
            height=3,
            font=("Arial", 11),
            wrap=tk.WORD,
            bg="#2d2d2d",
            fg="white",
            relief=tk.SUNKEN,
            bd=2,
            padx=8,
            pady=8
        )
        self.comment_text.pack(fill=tk.X, pady=2)

        # Status label
        self.status_label = tk.Label(
            root,
            text="Status: Ready",
            font=("Arial", 10),
            bg="black",
            fg="#00ff88"
        )
        self.status_label.pack(pady=5)

        # === Button Frame (Bottom) ===
        self.button_frame = tk.Frame(root, bg="black")
        self.button_frame.pack(pady=10)

        # Buttons
        self.correct_btn = tk.Button(
            self.button_frame,
            text="✅ Correct",
            font=("Arial", 12),
            bg="#00aa00",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=lambda: self.submit_label("y")
        )
        self.correct_btn.grid(row=0, column=0, padx=10)

        self.incorrect_btn = tk.Button(
            self.button_frame,
            text="❌ Incorrect",
            font=("Arial", 12),
            bg="#aa0000",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=lambda: self.submit_label("n")
        )
        self.incorrect_btn.grid(row=0, column=1, padx=10)

        self.unclear_btn = tk.Button(
            self.button_frame,
            text="❓ Unclear",
            font=("Arial", 12),
            bg="#ff8800",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=lambda: self.submit_label("l")
        )
        self.unclear_btn.grid(row=0, column=2, padx=10)

        # Save button
        self.save_button = tk.Button(
            root,
            text="💾 Save & Exit",
            font=("Arial", 12),
            bg="#007acc",
            fg="white",
            relief=tk.RAISED,
            bd=2,
            command=self.save_and_exit
        )
        self.save_button.pack(pady=10)

        # === Initialize ===
        self.reset()

    def reset(self):
        global current_index, df, image_paths, validation_labels, output_path, image_dir, filename_to_path, comments
        current_index = 0
        df = pd.DataFrame()
        image_paths = []
        validation_labels = [None] * len(df)
        comments = [None] * len(df)
        output_path = DEFAULT_OUTPUT_DIR / DEFAULT_OUTPUT_FILE
        image_dir = Path()
        filename_to_path = {}
        self.photo = None
        self.start_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: Ready")
        self.image_label.config(image="", text="No image loaded")
        self.update_info_text()
        self.update_stats_text()
        self.comment_text.delete(1.0, tk.END)

    def load_csv(self):
        global df, image_paths, output_path
        file_path = filedialog.askopenfilename(
            title="Select metadata CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            df = pd.read_csv(file_path)
            # Ensure required columns exist
            required_cols = ["crop_path", "bioclip_species", "bioclip_genus", "bioclip_family", "bioclip_order",
                            "duration_s", "top1_prob_weighted", "det_conf_mean"]
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                messagebox.showerror("Error", f"Missing required columns: {missing}")
                return

            # Ensure all paths are strings
            df["crop_path"] = df["crop_path"].astype(str)

            # Set output path
            output_path = Path(file_path).parent / "validated_metadata.csv"
            self.status_label.config(text=f"Status: Loaded {len(df)} rows from CSV")

            # ✅ Initialize validation_labels and comments
            global validation_labels, comments
            validation_labels = [None] * len(df)
            comments = [None] * len(df)

            # If image_dir is already set, update paths
            if image_dir:
                self.update_image_paths()
            else:
                self.status_label.config(text="⚠️ Image directory not set. Please select it.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {e}")

    def select_image_dir(self):
        global image_dir
        dir_path = filedialog.askdirectory(title="Select Image Crops Directory")
        if not dir_path:
            return

        image_dir = Path(dir_path)
        if not image_dir.exists():
            messagebox.showerror("Error", f"Directory not found: {dir_path}")
            return

        self.status_label.config(text=f"Image directory set: {image_dir}")

        # Build filename index
        self.build_filename_index()

    def build_filename_index(self):
        global filename_to_path
        filename_to_path = {}
        found_count = 0
        duplicate_count = 0

        print(f"🔍 Scanning directory: {image_dir}")
        for root, _, files in os.walk(image_dir):
            for file in files:
                filename = Path(file).name.lower()  # ✅ Case-insensitive
                if filename in filename_to_path:
                    duplicate_count += 1
                    continue
                full_path = Path(root) / file
                filename_to_path[filename] = full_path
                found_count += 1

        print(f"✅ Indexed {found_count} files. {duplicate_count} duplicates skipped.")
        print(f"🔍 First 5 filenames: {list(filename_to_path.keys())[:5]}")

    def update_image_paths(self):
        global df, image_paths
        if not image_dir or df.empty:
            return

        image_paths = []
        found_count = 0
        not_found_count = 0

        for idx, row in df.iterrows():
            rel_path = Path(row["crop_path"])
            filename = rel_path.name.lower()  # ✅ Case-insensitive
            print(f"🔍 Looking for: {filename}")

            full_path = filename_to_path.get(filename)
            if full_path and full_path.exists():
                image_paths.append(full_path)
                found_count += 1
            else:
                image_paths.append(None)
                not_found_count += 1
                print(f"❌ Not found: {filename}")

        self.status_label.config(
            text=f"Status: {found_count}/{len(df)} found, {not_found_count} missing"
        )

    def start_validation(self):
        global current_index
        if df.empty:
            messagebox.showwarning("No Data", "Please load a CSV first.")
            return
        if not image_dir:
            messagebox.showwarning("No Directory", "Please select an image directory.")
            return

        self.start_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Validation started")
        current_index = 0
        self.show_next_image()
        self.update_info_text()
        self.update_stats_text()
        self.comment_text.delete(1.0, tk.END)

    def show_next_image(self):
        global current_index, df, image_paths
        if current_index >= len(df):
            messagebox.showinfo("Done", "All images have been validated!")
            self.save_and_exit()
            return

        row = df.iloc[current_index]
        image_path = image_paths[current_index]

        if not image_path or not image_path.exists():
            self.status_label.config(text=f"⚠️ Image missing: {image_path}")
            self.image_label.config(image="", text="Image not found")
            self.root.after(1000, self.show_next_image)
            return

        try:
            # Open image
            img = Image.open(image_path)

            # Get original size
            orig_width, orig_height = img.size

            # Define max display size
            max_width = 600
            max_height = 400

            # Calculate scaling factor to fit within bounds
            scale_x = max_width / orig_width
            scale_y = max_height / orig_height
            scale = min(scale_x, scale_y)

            # New size
            new_width = int(orig_width * scale)
            new_height = int(orig_height * scale)

            # Resize
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            # ✅ Store as instance attribute to prevent garbage collection
            self.photo = photo

            # Update label
            self.image_label.config(image=photo)
            self.image_label.image = photo
            self.status_label.config(text=f"Status: {current_index + 1}/{len(df)}")
            self.update_info_text()
            self.update_stats_text()

        except Exception as e:
            self.status_label.config(text=f"❌ Failed to load image: {e}")
            self.image_label.config(image="", text="Error loading image")
            self.root.after(1000, self.show_next_image)

    def update_info_text(self):
        if current_index >= len(df):
            return

        row = df.iloc[current_index]
        species = row.get("bioclip_species", "N/A")
        genus = row.get("bioclip_genus", "N/A")
        family = row.get("bioclip_family", "N/A")
        order = row.get("bioclip_order", "N/A")

        self.labels["Species"].config(text=species)
        self.labels["Genus"].config(text=genus)
        self.labels["Family"].config(text=family)
        self.labels["Order"].config(text=order)

    def update_stats_text(self):
        if current_index >= len(df):
            return

        row = df.iloc[current_index]
        duration = row.get("duration_s", "N/A")
        prob = row.get("top1_prob_weighted", "N/A")
        conf = row.get("det_conf_mean", "N/A")

        self.stats_labels["duration_s"].config(text=str(duration))
        self.stats_labels["top1_prob_weighted"].config(text=f"{prob:.2f}")
        self.stats_labels["det_conf_mean"].config(text=f"{conf:.2f}")

    def submit_label(self, label: str):
        global current_index, validation_labels, comments
        if current_index >= len(df):
            return

        if current_index >= len(validation_labels):
            print(f"⚠️ current_index ({current_index}) >= len(validation_labels) ({len(validation_labels)})")
            return

        validation_labels[current_index] = label
        comments[current_index] = self.comment_text.get(1.0, tk.END).strip()
        current_index += 1
        self.show_next_image()
        self.comment_text.delete(1.0, tk.END)  # Clear comment

    def save_and_exit(self):
        global df, validation_labels, comments, output_path
        if len(df) == 0:
            messagebox.showwarning("No Data", "No data to save.")
            return

        # ✅ Ensure validation_labels and comments have correct length
        if len(validation_labels) != len(df):
            print(f"⚠️ validation_labels length ({len(validation_labels)}) != df length ({len(df)})")
            validation_labels = [None] * len(df)
        if len(comments) != len(df):
            print(f"⚠️ comments length ({len(comments)}) != df length ({len(df)})")
            comments = [None] * len(df)

        # Add validation and comment columns
        df_with_validation = df.copy()
        df_with_validation["validation"] = validation_labels
        df_with_validation["comment"] = comments

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save
        try:
            df_with_validation.to_csv(output_path, index=False)
            messagebox.showinfo(
                "Saved",
                f"Validation complete!\nSaved to:\n{output_path}"
            )
            self.root.quit()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")


# === Main Entry Point ===
def main():
    root = tk.Tk()
    app = ImageValidatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
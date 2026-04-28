import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import PIL
import pandas as pd
import os

class ImageValidator:
    def __init__(self, root, csv_path, image_dir):
        self.root = root
        self.root.title("Image Classification Validator")
        self.root.geometry("800x600")

        # Load data
        self.df = pd.read_csv(csv_path)
        self.image_dir = image_dir
        self.current_idx = 0
        self.validated_data = []

        # UI Elements
        self.setup_ui()

    def setup_ui(self):
        # Frame for image
        self.image_frame = ttk.Frame(self.root)
        self.image_frame.pack(pady=10, fill=tk.BOTH, expand=True)

        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack()

        # Frame for controls
        self.control_frame = ttk.Frame(self.root)
        self.control_frame.pack(pady=10)

        # Buttons
        self.prev_btn = ttk.Button(self.control_frame, text="Previous", command=self.prev_image)
        self.prev_btn.grid(row=0, column=0, padx=5)

        self.accept_btn = ttk.Button(self.control_frame, text="Accept", command=self.accept)
        self.accept_btn.grid(row=0, column=1, padx=5)

        self.reject_btn = ttk.Button(self.control_frame, text="Reject", command=self.reject)
        self.reject_btn.grid(row=0, column=2, padx=5)

        self.next_btn = ttk.Button(self.control_frame, text="Next", command=self.next_image)
        self.next_btn.grid(row=0, column=3, padx=5)

        # Status label
        self.status_label = ttk.Label(self.root, text="", foreground="blue")
        self.status_label.pack(pady=5)

        # Load first image
        self.load_image()

    def load_image(self):
        if self.current_idx >= len(self.df):
            messagebox.showinfo("Done", "All images validated!")
            return

        row = self.df.iloc[self.current_idx]
        img_path = os.path.join(self.image_dir, row['image_id'])

        if not os.path.exists(img_path):
            self.status_label.config(text=f"Image not found: {img_path}")
            self.next_image()
            return

        # Open and resize image
        pil_img = PIL.Image.open(img_path)
        pil_img.thumbnail((600, 400))  # Resize for display
        self.tk_img = PIL.ImageTk.PhotoImage(pil_img)

        self.image_label.config(image=self.tk_img)
        self.image_label.image = self.tk_img  # Keep reference

        # Update status
        pred_class = row['predicted_class']
        confidence = row['confidence']
        self.status_label.config(text=f"Image {self.current_idx + 1}/{len(self.df)} | "
                                      f"Predicted: {pred_class} (Conf: {confidence:.2f})")

    def next_image(self):
        self.current_idx += 1
        self.load_image()

    def prev_image(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_image()

    def accept(self):
        row = self.df.iloc[self.current_idx]
        self.validated_data.append({
            'image_id': row['image_id'],
            'predicted_class': row['predicted_class'],
            'confidence': row['confidence'],
            'validated_class': row['predicted_class'],  # Accept as correct
            'validated': True
        })
        self.next_image()

    def reject(self):
        row = self.df.iloc[self.current_idx]
        # Optionally, let user enter correct class later
        # For now, just mark as invalid
        self.validated_data.append({
            'image_id': row['image_id'],
            'predicted_class': row['predicted_class'],
            'confidence': row['confidence'],
            'validated_class': None,
            'validated': False
        })
        self.next_image()

    def save_results(self):
        # Save validated results
        output_df = pd.DataFrame(self.validated_data)
        output_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if output_path:
            output_df.to_csv(output_path, index=False)
            messagebox.showinfo("Saved", f"Validation results saved to {output_path}")

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to save results before quitting?"):
            self.save_results()
        self.root.destroy()


# Run the app
if __name__ == "__main__":
    root = tk.Tk()

    # Set paths (adjust these!)
    CSV_PATH = "data/predictions.csv"
    IMAGE_DIR = "data/images"

    app = ImageValidator(root, CSV_PATH, IMAGE_DIR)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    root.mainloop()
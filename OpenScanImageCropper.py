import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import cv2
import numpy as np
import os
import glob
import json
import threading
from PIL import Image, ImageTk

SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(e)
            return {}
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

class OpenScanImageCropper(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OpenScan Image Cropper")
        # Increase window size to show all controls comfortably.
        self.geometry("800x1200")
        self.settings = load_settings()
        self.settings.setdefault("input_folder", "")
        self.settings.setdefault("output_folder", "")
        self.settings.setdefault("threshold", 200)
        self.settings.setdefault("margin", 30)
        self.settings.setdefault("custom_prefix", "")
        self.settings.setdefault("output_format", "Original")
        self.last_input_folder = self.settings.get("input_folder", "")
        self.last_output_folder = self.settings.get("output_folder", "")
        
        self.image_list = []      # List of image file paths.
        self.current_index = 0
        self.sample_image = None  # Loaded image (NumPy array).
        self.current_preview_pil = None  # PIL image for preview.
        self.preview_photo = None  # PhotoImage for canvas.
        self.zoom_factor = 1.0
        # Pan offsets.
        self.pan_x = 0
        self.pan_y = 0

        # For panning.
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_start_offset_x = 0
        self.pan_start_offset_y = 0

        # For selection mode.
        self.select_mode = False
        self.sel_start_x = 0
        self.sel_start_y = 0
        self.sel_rect_id = None

        # Canvas dimensions.
        self.canvas_width = 600
        self.canvas_height = 400

        # Build GUI.
        tk.Label(self, text="Input Folder:").pack(pady=(10, 0))
        self.input_folder_entry = tk.Entry(self, width=60)
        self.input_folder_entry.pack(pady=(0, 5))
        self.input_folder_entry.insert(0, self.settings["input_folder"])
        tk.Button(self, text="Browse Input Folder", command=self.browse_input_folder).pack()

        tk.Label(self, text="Output Folder:").pack(pady=(10, 0))
        self.output_folder_entry = tk.Entry(self, width=60)
        self.output_folder_entry.pack(pady=(0, 5))
        self.output_folder_entry.insert(0, self.settings["output_folder"])
        tk.Button(self, text="Browse Output Folder", command=self.browse_output_folder).pack()

        tk.Label(self, text="Custom Output Prefix:").pack(pady=(10, 0))
        self.prefix_entry = tk.Entry(self, width=30)
        self.prefix_entry.pack(pady=(0, 5))
        self.prefix_entry.insert(0, self.settings["custom_prefix"])

        tk.Label(self, text="Output Format:").pack(pady=(10, 0))
        self.output_format_var = tk.StringVar(self)
        self.output_format_var.set(self.settings["output_format"])  # Options: Original, TIFF, PNG, JPG.
        formats = ["Original", "TIFF", "PNG", "JPG"]
        tk.OptionMenu(self, self.output_format_var, *formats).pack(pady=(0, 5))

        tk.Label(self, text="Brightness Threshold (0-255):").pack(pady=(10, 0))
        self.threshold_scale = tk.Scale(self, from_=0, to=255, orient="horizontal", command=self.update_preview)
        self.threshold_scale.set(self.settings["threshold"])
        self.threshold_scale.pack()

        tk.Label(self, text="Margin (px):").pack(pady=(10, 0))
        self.margin_scale = tk.Scale(self, from_=0, to=100, orient="horizontal", command=self.update_preview)
        self.margin_scale.set(self.settings["margin"])
        self.margin_scale.pack()

        nav_frame = tk.Frame(self)
        nav_frame.pack(pady=10)
        tk.Button(nav_frame, text="<< Prev 10", command=self.prev_10).grid(row=0, column=0, padx=5)
        tk.Button(nav_frame, text="< Prev", command=self.prev_image).grid(row=0, column=1, padx=5)
        tk.Button(nav_frame, text="Next >", command=self.next_image).grid(row=0, column=2, padx=5)
        tk.Button(nav_frame, text="Next 10 >>", command=self.next_10).grid(row=0, column=3, padx=5)

        self.preview_canvas = tk.Canvas(self, width=self.canvas_width, height=self.canvas_height, bg="grey")
        self.preview_canvas.pack(pady=10)
        # Bind unified left mouse events.
        self.preview_canvas.bind("<ButtonPress-1>", self.on_left_button_press)
        self.preview_canvas.bind("<B1-Motion>", self.on_left_button_motion)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_left_button_release)
        self.preview_canvas.bind("<MouseWheel>", self.do_zoom)  # Windows.
        self.preview_canvas.bind("<Button-4>", self.do_zoom)    # Linux scroll up.
        self.preview_canvas.bind("<Button-5>", self.do_zoom)    # Linux scroll down.

        self.filename_label = tk.Label(self, text="Filename: None", font=("Helvetica", 10))
        self.filename_label.pack(pady=(0, 10))

        # Frame for processing buttons.
        proc_frame = tk.Frame(self)
        proc_frame.pack(pady=20)
        tk.Button(proc_frame, text="Process All Images", command=self.start_process_all).grid(row=0, column=0, padx=10)
        tk.Button(proc_frame, text="Process Current Image", command=self.process_current_image).grid(row=0, column=1, padx=10)
        tk.Button(proc_frame, text="Select Region for Threshold", command=self.activate_selection_mode).grid(row=0, column=2, padx=10)
        tk.Button(proc_frame, text="Load Darkest Image for Threshold", command=self.load_darkest_image_for_threshold).grid(row=0, column=3, padx=10)

        # Progress bar.
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=750, mode="determinate")
        self.progress_bar.pack(pady=10)

        # Instructions.
        instructions = ("Instructions:\n"
                        "• Pan: Click and drag the image.\n"
                        "• Zoom: Use the mouse wheel; zoom is centered at the mouse pointer.\n"
                        "• To set threshold from a region: Click 'Select Region for Threshold' then click & drag on the image.\n"
                        "• To determine threshold on the darkest image: Click 'Load Darkest Image for Threshold'.")
        tk.Label(self, text=instructions, font=("Helvetica", 9), wraplength=750, justify="center").pack(pady=10)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.settings["input_folder"]:
            self.load_input_folder(self.settings["input_folder"])

    # --- Folder Browsing ---
    def browse_input_folder(self):
        folder = filedialog.askdirectory(initialdir=self.last_input_folder or None)
        if folder:
            self.input_folder_entry.delete(0, tk.END)
            self.input_folder_entry.insert(0, folder)
            self.last_input_folder = folder
            self.settings["input_folder"] = folder
            self.load_input_folder(folder)

    def load_input_folder(self, folder):
        # Updated to include TIFF, JPG, JPEG, PNG.
        extensions = ["*.tif", "*.tiff", "*.jpg", "*.jpeg", "*.png"]
        image_paths = []
        for ext in extensions:
            image_paths.extend(glob.glob(os.path.join(folder, ext)))
        image_paths = sorted(image_paths)
        if not image_paths:
            messagebox.showinfo("No Images Found", "No image files found in the selected input folder.")
            self.image_list = []
            self.sample_image = None
            self.preview_canvas.delete("all")
            self.filename_label.config(text="Filename: None")
        else:
            self.image_list = image_paths
            self.current_index = 0
            self.load_current_image(reset_zoom=True)

    def browse_output_folder(self):
        folder = filedialog.askdirectory(initialdir=self.last_output_folder or None)
        if folder:
            self.output_folder_entry.delete(0, tk.END)
            self.output_folder_entry.insert(0, folder)
            self.last_output_folder = folder
            self.settings["output_folder"] = folder

    # --- Image Loading & Display ---
    def load_current_image(self, reset_zoom=True):
        if not self.image_list:
            return
        if self.current_index < 0 or self.current_index >= len(self.image_list):
            return
        image_path = self.image_list[self.current_index]
        self.sample_image = cv2.imread(image_path)
        if self.sample_image is None:
            messagebox.showerror("Error", f"Could not load image: {image_path}")
            return
        if reset_zoom:
            img_height, img_width = self.sample_image.shape[:2]
            scale = min(1.0, self.canvas_width / img_width, self.canvas_height / img_height)
            self.zoom_factor = scale
            self.pan_x = 0
            self.pan_y = 0
        self.filename_label.config(text=f"Filename: {os.path.basename(image_path)}")
        self.update_preview()

    def update_preview(self, event=None):
        if self.sample_image is None:
            return
        brightness_threshold = self.threshold_scale.get()
        margin = self.margin_scale.get()
        image = self.sample_image.copy()
        if len(image.shape) == 2:
            gray = image
            image_color = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            image_color = image
        _, thresh = cv2.threshold(gray, brightness_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest_contour)
            x = max(x - margin, 0)
            y = max(y - margin, 0)
            x2 = min(x + w + 2 * margin, image_color.shape[1])
            y2 = min(y + h + 2 * margin, image_color.shape[0])
            cv2.rectangle(image_color, (x, y), (x2, y2), (0, 255, 0), 2)
        if len(image_color.shape) == 2:
            image_rgb = cv2.cvtColor(image_color, cv2.COLOR_GRAY2RGB)
        else:
            image_rgb = cv2.cvtColor(image_color, cv2.COLOR_BGR2RGB)
        im_pil = Image.fromarray(image_rgb)
        self.current_preview_pil = im_pil
        self.update_canvas_image()

    def update_canvas_image(self):
        if self.current_preview_pil is None:
            return
        w, h = self.current_preview_pil.size
        new_size = (int(w * self.zoom_factor), int(h * self.zoom_factor))
        try:
            resample_method = Image.Resampling.LANCZOS
        except AttributeError:
            resample_method = Image.LANCZOS
        resized = self.current_preview_pil.resize(new_size, resample_method)
        self.preview_photo = ImageTk.PhotoImage(resized)
        self.preview_canvas.delete("all")
        center_x = self.canvas_width / 2 + self.pan_x
        center_y = self.canvas_height / 2 + self.pan_y
        self.preview_canvas.create_image(center_x, center_y, anchor="center", image=self.preview_photo)
        if self.select_mode and self.sel_rect_id is not None:
            self.preview_canvas.lift(self.sel_rect_id)

    # --- Unified Left Mouse Handlers ---
    def on_left_button_press(self, event):
        if self.select_mode:
            self.start_selection(event)
        else:
            self.start_pan(event)

    def on_left_button_motion(self, event):
        if self.select_mode:
            self.do_selection(event)
        else:
            self.do_pan(event)

    def on_left_button_release(self, event):
        if self.select_mode:
            self.end_selection(event)

    # --- Pan Handlers ---
    def start_pan(self, event):
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_start_offset_x = self.pan_x
        self.pan_start_offset_y = self.pan_y

    def do_pan(self, event):
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.pan_x = self.pan_start_offset_x + dx
        self.pan_y = self.pan_start_offset_y + dy
        self.update_canvas_image()

    # --- Zoom Handler ---
    def do_zoom(self, event):
        if event.delta:
            scale_factor = 1.1 if event.delta > 0 else 1/1.1
        elif event.num == 4:
            scale_factor = 1.1
        elif event.num == 5:
            scale_factor = 1/1.1
        else:
            scale_factor = 1.0
        old_zoom = self.zoom_factor
        new_zoom = old_zoom * scale_factor
        center_x = self.canvas_width / 2 + self.pan_x
        center_y = self.canvas_height / 2 + self.pan_y
        dx = event.x - center_x
        dy = event.y - center_y
        rel_x = dx / old_zoom
        rel_y = dy / old_zoom
        self.zoom_factor = new_zoom
        self.pan_x = event.x - self.canvas_width/2 - rel_x * new_zoom
        self.pan_y = event.y - self.canvas_height/2 - rel_y * new_zoom
        self.update_canvas_image()

    # --- Selection Mode Handlers ---
    def activate_selection_mode(self):
        self.select_mode = True
        messagebox.showinfo("Selection Mode", "Selection mode activated.\nClick and drag on the image to select a region for threshold.")

    def start_selection(self, event):
        self.sel_start_x = event.x
        self.sel_start_y = event.y
        if self.sel_rect_id:
            self.preview_canvas.delete(self.sel_rect_id)
        self.sel_rect_id = self.preview_canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="red", width=2)

    def do_selection(self, event):
        if self.sel_rect_id:
            self.preview_canvas.coords(self.sel_rect_id, self.sel_start_x, self.sel_start_y, event.x, event.y)

    def end_selection(self, event):
        if self.sel_rect_id is None:
            return
        x1, y1, x2, y2 = self.preview_canvas.coords(self.sel_rect_id)
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        cx = self.canvas_width / 2 + self.pan_x
        cy = self.canvas_height / 2 + self.pan_y
        if self.current_preview_pil is None:
            return
        img_w, img_h = self.current_preview_pil.size
        disp_w, disp_h = img_w * self.zoom_factor, img_h * self.zoom_factor
        img_x0 = cx - disp_w/2
        img_y0 = cy - disp_h/2
        sel_img_x1 = (x1 - img_x0) / self.zoom_factor
        sel_img_y1 = (y1 - img_y0) / self.zoom_factor
        sel_img_x2 = (x2 - img_x0) / self.zoom_factor
        sel_img_y2 = (y2 - img_y0) / self.zoom_factor
        sel_img_x1 = max(0, min(img_w, sel_img_x1))
        sel_img_y1 = max(0, min(img_h, sel_img_y1))
        sel_img_x2 = max(0, min(img_w, sel_img_x2))
        sel_img_y2 = max(0, min(img_h, sel_img_y2))
        if sel_img_x2 - sel_img_x1 < 1 or sel_img_y2 - sel_img_y1 < 1:
            messagebox.showwarning("Selection Too Small", "Selected area is too small.")
        else:
            cropped = self.current_preview_pil.crop((sel_img_x1, sel_img_y1, sel_img_x2, sel_img_y2))
            cropped_gray = cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2GRAY)
            new_threshold = int(np.mean(cropped_gray))
            self.threshold_scale.set(new_threshold)
            messagebox.showinfo("Threshold Set", f"Threshold set to {new_threshold} from selected region.")
        self.preview_canvas.delete(self.sel_rect_id)
        self.sel_rect_id = None
        self.select_mode = False
        self.update_preview()

    # --- Darkest Image Feature ---
    def load_darkest_image_for_threshold(self):
        if not self.image_list:
            messagebox.showinfo("No Images", "No images in the folder.")
            return
        extensions = ["*.tif", "*.tiff", "*.jpg", "*.jpeg", "*.png"]
        all_paths = []
        for ext in extensions:
            all_paths.extend(glob.glob(os.path.join(self.input_folder_entry.get(), ext)))
        all_paths = sorted(all_paths)
        total = len(all_paths)
        self.progress_bar["maximum"] = total
        darkest_index = None
        darkest_brightness = float("inf")
        for idx, path in enumerate(all_paths):
            img = cv2.imread(path)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            avg = np.mean(gray)
            if avg < darkest_brightness:
                darkest_brightness = avg
                darkest_index = idx
            self.progress_bar["value"] = idx + 1
            self.progress_bar.update_idletasks()
        self.progress_bar["value"] = 0
        if darkest_index is not None:
            self.current_index = darkest_index
            self.load_current_image(reset_zoom=True)
            messagebox.showinfo("Darkest Image Loaded", f"Darkest image loaded (avg brightness: {int(darkest_brightness)}).\nNow use 'Select Region for Threshold' if desired.")
        else:
            messagebox.showinfo("No Valid Images", "No valid images found for analysis.")

    # --- Navigation ---
    def next_image(self):
        if not self.image_list:
            return
        self.current_index = min(self.current_index + 1, len(self.image_list) - 1)
        self.load_current_image(reset_zoom=False)

    def prev_image(self):
        if not self.image_list:
            return
        self.current_index = max(self.current_index - 1, 0)
        self.load_current_image(reset_zoom=False)

    def next_10(self):
        if not self.image_list:
            return
        self.current_index = min(self.current_index + 10, len(self.image_list) - 1)
        self.load_current_image(reset_zoom=False)

    def prev_10(self):
        if not self.image_list:
            return
        self.current_index = max(self.current_index - 10, 0)
        self.load_current_image(reset_zoom=False)

    # --- Processing ---
    def process_image(self, image_path, output_folder, brightness_threshold, margin, prefix, output_format):
        image = cv2.imread(image_path)
        if image is None:
            print(f"Could not read {image_path}")
            return
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, brightness_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            print(f"No bright object found in {image_path}. Skipping.")
            return
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        x = max(x - margin, 0)
        y = max(y - margin, 0)
        x2 = min(x + w + 2 * margin, image.shape[1])
        y2 = min(y + h + 2 * margin, image.shape[0])
        cropped = image[y:y2, x:x2]
        base_name = os.path.basename(image_path)
        name, ext = os.path.splitext(base_name)
        if prefix:
            name = f"{prefix}_{name}"
        if output_format == "Original":
            ext = ext
        elif output_format == "TIFF":
            ext = ".tif"
        elif output_format == "PNG":
            ext = ".png"
        elif output_format == "JPG":
            ext = ".jpg"
        new_filename = name + ext
        output_path = os.path.join(output_folder, new_filename)
        cv2.imwrite(output_path, cropped)
        print(f"Saved cropped image to {output_path}")

    def process_images_thread(self):
        input_folder = self.input_folder_entry.get()
        output_folder = self.output_folder_entry.get()
        brightness_threshold = self.threshold_scale.get()
        margin = self.margin_scale.get()
        prefix = self.prefix_entry.get().strip()
        output_format = self.output_format_var.get()
        extensions = ["*.tif", "*.tiff", "*.jpg", "*.jpeg", "*.png"]
        image_paths = []
        for ext in extensions:
            image_paths.extend(glob.glob(os.path.join(input_folder, ext)))
        total = len(image_paths)
        self.progress_bar["maximum"] = total
        for i, image_path in enumerate(image_paths):
            self.process_image(image_path, output_folder, brightness_threshold, margin, prefix, output_format)
            self.progress_bar["value"] = i + 1
            self.progress_bar.update_idletasks()
        messagebox.showinfo("Processing Complete", f"Processed {total} images.")
        self.progress_bar["value"] = 0

    def start_process_all(self):
        if not self.input_folder_entry.get() or not self.output_folder_entry.get():
            messagebox.showerror("Missing Folder", "Please select both input and output folders.")
            return
        if not self.image_list:
            messagebox.showinfo("No Images", "No images to process.")
            return
        thread = threading.Thread(target=self.process_images_thread)
        thread.start()

    def process_current_image(self):
        input_folder = self.input_folder_entry.get()
        output_folder = self.output_folder_entry.get()
        brightness_threshold = self.threshold_scale.get()
        margin = self.margin_scale.get()
        prefix = self.prefix_entry.get().strip()
        output_format = self.output_format_var.get()
        if not input_folder or not output_folder:
            messagebox.showerror("Missing Folder", "Please select both input and output folders.")
            return
        if not self.image_list:
            messagebox.showinfo("No Image", "No image is loaded.")
            return
        current_path = self.image_list[self.current_index]
        self.process_image(current_path, output_folder, brightness_threshold, margin, prefix, output_format)
        messagebox.showinfo("Processing Complete", f"Processed current image: {os.path.basename(current_path)}")

    # --- On Close ---
    def on_close(self):
        self.settings["input_folder"] = self.input_folder_entry.get()
        self.settings["output_folder"] = self.output_folder_entry.get()
        self.settings["threshold"] = self.threshold_scale.get()
        self.settings["margin"] = self.margin_scale.get()
        self.settings["custom_prefix"] = self.prefix_entry.get().strip()
        self.settings["output_format"] = self.output_format_var.get()
        save_settings(self.settings)
        self.destroy()

if __name__ == "__main__":
    app = OpenScanImageCropper()
    app.mainloop()

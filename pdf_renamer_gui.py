import os
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from threading import Thread
from PIL import Image, ImageTk
import openai

# === CONFIGURATION ===
openai.api_key = "YOUR_OPENAI_API_KEY"
MAX_TEXT_LENGTH = 1000
GPT_MODEL = "gpt-4"

# === GLOBALS ===
preview_image = None
selected_pdf_path = None

def extract_text_by_area(pdf_path, rect):
    doc = fitz.open(pdf_path)
    page = doc[0]
    text = page.get_text("text", clip=fitz.Rect(*rect))
    return text.strip()

def generate_filename(text):
    prompt = (
        f"Based on this text, suggest a clean, short, descriptive filename in 4–6 words. "
        f"Do not include file extension or special characters.\n\n{text}"
    )
    try:
        response = openai.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates clean filenames."},
                {"role": "user", "content": prompt}
            ]
        )
        name = response.choices[0].message.content.strip()
        name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        return name
    except Exception as e:
        return None, str(e)

def rename_pdfs(folder_path, output_box, prefix, suffix, preview_only, use_area, rect):
    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".pdf"):
            old_path = os.path.join(folder_path, filename)
            output_box.insert(tk.END, f"🔍 Reading: {filename}\n")
            try:
                if use_area:
                    region_text = extract_text_by_area(old_path, rect)
                    if not region_text:
                        output_box.insert(tk.END, f"❌ No text found in area.\n")
                        continue
                    name = generate_filename(region_text)
                else:
                    doc = fitz.open(old_path)
                    full_text = ""
                    for page in doc:
                        full_text += page.get_text()
                        if len(full_text) >= MAX_TEXT_LENGTH:
                            break
                    name = generate_filename(full_text.strip()[:MAX_TEXT_LENGTH])
                if isinstance(name, tuple):
                    output_box.insert(tk.END, f"❌ GPT Error: {name[1]}\n")
                    continue
                final_name = f"{prefix}{name}{suffix}.pdf"
                new_path = os.path.join(folder_path, final_name)
                if preview_only:
                    output_box.insert(tk.END, f"📝 Will rename to: {final_name}\n")
                else:
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        output_box.insert(tk.END, f"✅ Renamed to: {final_name}\n")
                    else:
                        output_box.insert(tk.END, f"⚠️ Skipped (file exists): {final_name}\n")
            except Exception as e:
                output_box.insert(tk.END, f"❌ Error: {str(e)}\n")
    output_box.insert(tk.END, "✅ Done.\n")

class PDFRenamerApp:
    def __init__(self, master):
        self.master = master
        master.title("AI PDF Renamer with Area Selector")
        master.geometry("720x600")

        self.folder_path = None
        self.rect = [0, 0, 0, 0]
        self.rect_id = None

        self.top_frame = tk.Frame(master)
        self.top_frame.pack(pady=5)

        self.select_btn = tk.Button(self.top_frame, text="📁 Select Folder", command=self.select_folder)
        self.select_btn.grid(row=0, column=0, padx=5)

        self.sample_btn = tk.Button(self.top_frame, text="📄 Choose Sample PDF", command=self.select_sample_pdf)
        self.sample_btn.grid(row=0, column=1, padx=5)

        self.prefix_entry = tk.Entry(self.top_frame, width=15)
        self.prefix_entry.grid(row=0, column=2)
        tk.Label(self.top_frame, text="Prefix").grid(row=1, column=2)

        self.suffix_entry = tk.Entry(self.top_frame, width=15)
        self.suffix_entry.grid(row=0, column=3)
        tk.Label(self.top_frame, text="Suffix").grid(row=1, column=3)

        self.preview_var = tk.BooleanVar()
        self.preview_check = tk.Checkbutton(self.top_frame, text="Preview Only", variable=self.preview_var)
        self.preview_check.grid(row=0, column=4, padx=5)

        self.use_area_var = tk.BooleanVar()
        self.use_area_check = tk.Checkbutton(self.top_frame, text="Use Area", variable=self.use_area_var)
        self.use_area_check.grid(row=1, column=4, padx=5)

        self.start_btn = tk.Button(master, text="🚀 Start Renaming", command=self.start_renaming, state="disabled")
        self.start_btn.pack(pady=5)

        self.canvas = tk.Canvas(master, bg="white", height=300)
        self.canvas.pack(padx=10, pady=5, fill=tk.X)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)

        self.output_box = scrolledtext.ScrolledText(master, height=10)
        self.output_box.pack(fill=tk.BOTH, padx=10, pady=10)

    def select_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_path = path
            self.output_box.insert(tk.END, f"📂 Folder Selected: {path}\n")
            self.start_btn.config(state="normal")

    def select_sample_pdf(self):
        global preview_image, selected_pdf_path
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not path:
            return
        selected_pdf_path = path
        doc = fitz.open(path)
        pix = doc[0].get_pixmap(dpi=100)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img = img.resize((600, int(img.height * 600 / pix.width)))
        preview_image = ImageTk.PhotoImage(img)
        self.canvas.config(width=600, height=img.height)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=preview_image)
        self.output_box.insert(tk.END, f"🖼 Loaded sample PDF for area selection.\n")

    def on_canvas_click(self, event):
        self.rect[0] = event.x
        self.rect[1] = event.y

    def on_canvas_drag(self, event):
        self.rect[2] = event.x
        self.rect[3] = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(*self.rect, outline="red", width=2)

    def start_renaming(self):
        if not self.folder_path:
            messagebox.showerror("No folder", "Please select a folder with PDFs.")
            return
        prefix = self.prefix_entry.get().strip()
        suffix = self.suffix_entry.get().strip()
        preview = self.preview_var.get()
        use_area = self.use_area_var.get()
        if use_area and not any(self.rect):
            messagebox.showerror("Area not selected", "Please select an area on the sample PDF.")
            return

        doc = fitz.open(selected_pdf_path)
        page = doc[0]
        scale_x = page.rect.width / 600
        scale_y = page.rect.height / self.canvas.winfo_height()
        scaled_rect = [int(x * scale_x) if i % 2 == 0 else int(x * scale_y) for i, x in enumerate(self.rect)]

        Thread(target=rename_pdfs, args=(
            self.folder_path,
            self.output_box,
            prefix,
            suffix,
            preview,
            use_area,
            scaled_rect
        )).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFRenamerApp(root)
    root.mainloop()


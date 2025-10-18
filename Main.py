#!/usr/bin/env python3
"""
signer_gui.py

A Tkinter GUI for:
 - P7M (sign_file_p7m)
 - PAdES (sign_pdf_pades) with visible signature placement via click-and-drag.

Dependencies:
  pip install pymupdf pillow
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import fitz  # PyMuPDF


# ----------------------------------------------------------------------
# IMPORTANT: Provide your real signing functions here (or import them).
#
# Example:
# from my_signer_module import sign_file_p7m, sign_pdf_pades
#
# If you leave them undefined, the GUI will show an error when you try to sign.
# ----------------------------------------------------------------------

try:
    # Try to import if user put functions in a module called `signer`
    from p7m import sign_file_p7m
    from pades import sign_pdf_pades  # optional
except Exception:
    # If not importable, try to see if functions exist in globals (user may paste them above).
    if 'sign_file_p7m' in globals() and 'sign_pdf_pades' in globals():
        pass
    else:
        # Define stub functions that raise helpful errors if used.
        def sign_file_p7m(*args, **kwargs):
            raise RuntimeError(
                "sign_file_p7m() not found. Please put your function in this file or import it as `from signer import sign_file_p7m`."
            )

        def sign_pdf_pades(*args, **kwargs):
            raise RuntimeError(
                "sign_pdf_pades() not found. Please put your function in this file or import it as `from signer import sign_pdf_pades`."
            )

# ----------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------
def ask_file(filetypes=(("All files", "*.*"),)):
    return filedialog.askopenfilename(title="Select file", filetypes=filetypes)

def ask_save_file(defaultextension="", filetypes=(("All files", "*.*"),)):
    return filedialog.asksaveasfilename(title="Save as", defaultextension=defaultextension, filetypes=filetypes)

# ----------------------------------------------------------------------
# PDF Preview widget with click-and-drag box selection
# ----------------------------------------------------------------------
class PDFPreview(tk.Frame):
    def __init__(self, master, on_box_changed=None, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, bg="gray", width=600, height=800)
        self.canvas.pack(fill="both", expand=True)
        self.imtk = None  # PhotoImage
        self._doc = None
        self.page_index = 0
        self.scale = 1.0
        self.image_size = (0, 0)
        self.box = None  # (x0, y0, x1, y1) in PDF coordinates
        self._rect_id = None
        self.on_box_changed = on_box_changed

        # mouse events for drawing/selecting a rectangle
        self._drag_start = None
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

    def load_pdf(self, path, page_index=0, max_width=900):
        if not os.path.exists(path):
            messagebox.showerror("File not found", f"PDF not found: {path}")
            return
        self._doc = fitz.open(path)
        self.page_index = min(max(0, page_index), len(self._doc)-1)
        self._render_page(max_width=max_width)

    def num_pages(self):
        return len(self._doc) if self._doc else 0

    def _render_page(self, max_width=900):
        page = self._doc.load_page(self.page_index)
        zoom = 2  # render quality
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        mode = "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        # scale down if too wide for the canvas
        w, h = img.size
        if w > max_width:
            ratio = max_width / w
            img = img.resize((int(w*ratio), int(h*ratio)), Image.LANCZOS)
            self.scale = (w / img.width)  # pdf pts per displayed pixel scale
        else:
            self.scale = 1.0 * (1/zoom)  # approximate scale (pdf pts to canvas px)
        self.image_size = img.size
        self.imtk = ImageTk.PhotoImage(img)
        self.canvas.config(width=self.image_size[0], height=self.image_size[1])
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.imtk)
        # draw existing box if present
        if self.box:
            self._draw_rect_on_canvas(self.box)

    def _pdf_to_screen(self, bbox_pdf):
        # bbox_pdf = (x0, y0, x1, y1) in PDF points (origin top-left)
        # When we rendered we used a zoom and possibly resized; we stored `scale` as pdf_pts / screen_px approx
        x0, y0, x1, y1 = bbox_pdf
        sx0 = x0 / self.scale
        sy0 = y0 / self.scale
        sx1 = x1 / self.scale
        sy1 = y1 / self.scale
        return (sx0, sy0, sx1, sy1)

    def _screen_to_pdf(self, bbox_screen):
        sx0, sy0, sx1, sy1 = bbox_screen
        return (sx0 * self.scale, sy0 * self.scale, sx1 * self.scale, sy1 * self.scale)

    def _on_mouse_down(self, event):
        # start point in screen coords
        self._drag_start = (event.x, event.y)
        # remove existing temporary rectangle
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_mouse_move(self, event):
        if not self._drag_start:
            return
        x0, y0 = self._drag_start
        x1, y1 = event.x, event.y
        # draw/update rectangle on canvas
        if self._rect_id:
            self.canvas.coords(self._rect_id, x0, y0, x1, y1)
        else:
            self._rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline="red", width=2)

    def _on_mouse_up(self, event):
        if not self._drag_start:
            return
        x0, y0 = self._drag_start
        x1, y1 = event.x, event.y
        # normalize
        sx0, sy0 = min(x0, x1), min(y0, y1)
        sx1, sy1 = max(x0, x1), max(y0, y1)
        # screen -> pdf
        pdf_box = self._screen_to_pdf((sx0, sy0, sx1, sy1))
        self.box = pdf_box
        # keep rectangle visible
        # delete old overlays then draw permanent rectangle
        for tag in ("permanent_rect",):
            self.canvas.delete(tag)
        self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline="green", width=2, tags=("permanent_rect",))
        self._drag_start = None
        if callable(self.on_box_changed):
            self.on_box_changed(self.box)

    def clear_box(self):
        self.box = None
        self.canvas.delete("permanent_rect")

    def _draw_rect_on_canvas(self, pdf_box):
        sx0, sy0, sx1, sy1 = self._pdf_to_screen(pdf_box)
        self.canvas.create_rectangle(sx0, sy0, sx1, sy1, outline="green", width=2, tags=("permanent_rect",))

# ----------------------------------------------------------------------
# Main Application
# ----------------------------------------------------------------------
class SignerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Document Signer - PAdES / P7M")
        self.geometry("1100x800")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._create_pades_tab()
        self._create_p7m_tab()

    # -------------------------
    # PAdES Tab (PDF)
    # -------------------------
    def _create_pades_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Sign PDF (PAdES)")

        left = ttk.Frame(frame, width=420)
        left.pack(side="left", fill="y", padx=8, pady=8)
        right = ttk.Frame(frame)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        # Left controls
        # Input PDF
        ttk.Label(left, text="Input PDF:").pack(anchor="w", pady=(4,0))
        self.pdf_input_var = tk.StringVar()
        in_frame = ttk.Frame(left)
        in_frame.pack(fill="x")
        ttk.Entry(in_frame, textvariable=self.pdf_input_var, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(in_frame, text="Browse", command=self._browse_pdf).pack(side="left", padx=4)

        # Output
        ttk.Label(left, text="Output PDF:").pack(anchor="w", pady=(8,0))
        self.pdf_output_var = tk.StringVar()
        out_frame = ttk.Frame(left)
        out_frame.pack(fill="x")
        ttk.Entry(out_frame, textvariable=self.pdf_output_var, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(out_frame, text="Save as...", command=self._save_pdf_as).pack(side="left", padx=4)

        # PKCS#11 and token/cert/pin
        ttk.Label(left, text="PKCS#11 library:").pack(anchor="w", pady=(8,0))
        self.pkcs11_var = tk.StringVar()
        self.pkcs11_var.set("./libbit4xpki.so")
        lib_frame = ttk.Frame(left)
        lib_frame.pack(fill="x")
        ttk.Entry(lib_frame, textvariable=self.pkcs11_var, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(lib_frame, text="Browse", command=self._browse_pkcs11).pack(side="left", padx=4)

        ttk.Label(left, text="Token / Slot label:").pack(anchor="w", pady=(8,0))
        self.token_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.token_var).pack(fill="x")

        #ttk.Label(left, text="Cert label:").pack(anchor="w", pady=(8,0))
        self.cert_var = tk.StringVar()
        #ttk.Entry(left, textvariable=self.cert_var).pack(fill="x")

        ttk.Label(left, text="PIN:").pack(anchor="w", pady=(8,0))
        self.pin_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.pin_var, show="*").pack(fill="x")

        # Visible signature options
        ttk.Separator(left).pack(fill="x", pady=8)
        self.visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left, text="Visible signature (click-and-drag to place)", variable=self.visible_var).pack(anchor="w")
        ttk.Label(left, text="Visible text prefix:").pack(anchor="w", pady=(8,0))
        self.visible_text_var = tk.StringVar(value="Firmato digitalmente da ")
        ttk.Entry(left, textvariable=self.visible_text_var).pack(fill="x")

        ttk.Label(left, text="Signature page index (0-based):").pack(anchor="w", pady=(8,0))
        self.page_var = tk.IntVar(value=0)
        ttk.Spinbox(left, from_=0, to=99, textvariable=self.page_var).pack(fill="x")

        # Sign button
        ttk.Button(left, text="Sign PDF (PAdES)", command=self._do_sign_pdf).pack(fill="x", pady=12)

        # Right: PDF preview
        self.preview = PDFPreview(right, on_box_changed=self._on_pdf_box_changed)
        self.preview.pack(fill="both", expand=True)
        # small status
        self.box_label_var = tk.StringVar(value="No box selected")
        ttk.Label(right, textvariable=self.box_label_var).pack(anchor="w", pady=4)

    def _browse_pdf(self):
        path = ask_file(filetypes=[("PDF files","*.pdf"),("All files","*.*")])
        if path:
            self.pdf_input_var.set(path)
            # set a default output filename
            base, ext = os.path.splitext(path)
            self.pdf_output_var.set(base + "_signed.pdf")
            # load preview
            try:
                page_idx = int(self.page_var.get())
            except Exception:
                page_idx = 0
            try:
                self.preview.load_pdf(path, page_index=page_idx)
            except Exception as e:
                messagebox.showerror("Preview error", f"Could not render PDF: {e}")

    def _save_pdf_as(self):
        path = ask_save_file(defaultextension=".pdf", filetypes=[("PDF files","*.pdf")])
        if path:
            self.pdf_output_var.set(path)

    def _browse_pkcs11(self):
        path = ask_file(filetypes=[("Shared libs","*.so;*.dll;*.dylib"),("All files","*.*")])
        if path:
            self.pkcs11_var.set(path)

    def _on_pdf_box_changed(self, box_pdf):
        # box_pdf is in PDF points; update label
        if box_pdf:
            x0,y0,x1,y1 = box_pdf
            self.box_label_var.set(f"Box (PDF pts): {int(x0)} {int(y0)} {int(x1)} {int(y1)}")
        else:
            self.box_label_var.set("No box selected")

    def _do_sign_pdf(self):
        input_pdf = self.pdf_input_var.get().strip()
        output_pdf = self.pdf_output_var.get().strip()
        pkcs11 = self.pkcs11_var.get().strip()
        token_label = self.token_var.get().strip()
        cert_label = self.cert_var.get().strip()
        user_pin = self.pin_var.get().strip()
        visible = bool(self.visible_var.get())
        visible_text = self.visible_text_var.get()
        try:
            page = int(self.page_var.get())
        except Exception:
            page = 0

        if not input_pdf or not os.path.exists(input_pdf):
            messagebox.showerror("Missing input", "Please select an existing input PDF.")
            return
        if not output_pdf:
            messagebox.showerror("Missing output", "Please choose an output filename.")
            return
        if not pkcs11:
            messagebox.showerror("Missing PKCS#11 library", "Please specify the PKCS#11 library path.")
            return
        if not user_pin:
            if not messagebox.askyesno("No PIN", "No PIN supplied. Continue without PIN?"):
                return

        # If visible and box not set, warn
        box = None
        if visible:
            box = self.preview.box
            if not box:
                if not messagebox.askyesno("No box selected", "No visible signature box selected. Sign anyway (invisible)?"):
                    return

        # Convert box to the format expected by sign_pdf_pades: (left, bottom, right, top) or (x0,y0,x1,y1)?
        # The GUI stores bbox in PDF points with origin top-left: (x0, y0, x1, y1).
        # Many signers expect (left, bottom, right, top) with origin bottom-left. We will attempt to convert
        # using page height from the PDF so user doesn't need to worry.
        if visible and box:
            try:
                doc = fitz.open(input_pdf)
                page_obj = doc.load_page(page)
                page_h = page_obj.rect.height  # PDF coordinate height
                x0, y0, x1, y1 = box
                # convert from top-left origin to bottom-left origin for PDF: new_y0 = page_h - y1, new_y1 = page_h - y0
                left = int(x0)
                right = int(x1)
                top = int(y0)
                bottom = int(y1)
                # Convert to common (left, bottom, right, top)
                box_for_signer = (left, int(page_h - bottom), right, int(page_h - top))
            except Exception as e:
                messagebox.showwarning("Box conversion failed", f"Couldn't convert box coordinates: {e}\nProceeding with raw box.")
                box_for_signer = tuple(map(int, box))
        else:
            box_for_signer = None

        # Confirm and call the signer function
        try:
            # sign_pdf_pades(input_pdf, output_pdf, pkcs11_lib, token_label, cert_label, user_pin, visible=False/True, visible_text="...", page=0, box=(l,b,r,t))
            # We pass box only if visible True and box set; otherwise None.
            #messagebox.showinfo("Signing", f"Calling sign_pdf_pades...\n\nInput: {input_pdf}\nOutput: {output_pdf}")
            sign_pdf_pades(
                input_pdf,
                output_pdf,
                pkcs11,
                token_label,
                cert_label,
                user_pin,
                visible=bool(visible and box_for_signer is not None),
                visible_text=visible_text,
                page=page,
                box=box_for_signer if box_for_signer is not None else (50, 50, 250, 100)
            )
            messagebox.showinfo("Done", f"PDF signed successfully and saved to:\n{output_pdf}")
        except Exception as e:
            messagebox.showerror("Signing failed", f"An error occurred while signing the PDF:\n\n{e}")

    # -------------------------
    # P7M Tab
    # -------------------------
    def _create_p7m_tab(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Sign File (P7M / CAdES)")

        container = ttk.Frame(frame, padding=12)
        container.pack(fill="both", expand=True)

        # Input file
        ttk.Label(container, text="Input file:").grid(row=0, column=0, sticky="w")
        self.file_input_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.file_input_var, width=60).grid(row=0, column=1, sticky="we")
        ttk.Button(container, text="Browse", command=self._browse_file).grid(row=0, column=2, padx=4)

        # Output file
        ttk.Label(container, text="Output (p7m):").grid(row=1, column=0, sticky="w", pady=(6,0))
        self.file_output_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.file_output_var, width=60).grid(row=1, column=1, sticky="we", pady=(6,0))
        ttk.Button(container, text="Save as...", command=self._save_file_as).grid(row=1, column=2, padx=4, pady=(6,0))

        # PKCS#11 lib
        ttk.Label(container, text="PKCS#11 library:").grid(row=2, column=0, sticky="w", pady=(8,0))
        self.p7m_pkcs11_var = tk.StringVar()
        self.p7m_pkcs11_var.set("./libbit4xpki.so")
        ttk.Entry(container, textvariable=self.p7m_pkcs11_var, width=60).grid(row=2, column=1, sticky="we", pady=(8,0))
        ttk.Button(container, text="Browse", command=self._browse_p7m_pkcs11).grid(row=2, column=2, padx=4, pady=(8,0))

        # Slot index or token label (we'll show both)
        ttk.Label(container, text="Slot index (int):").grid(row=3, column=0, sticky="w", pady=(8,0))
        self.slot_index_var = tk.IntVar(value=0)
        ttk.Entry(container, textvariable=self.slot_index_var, width=12).grid(row=3, column=1, sticky="w", pady=(8,0))

        ttk.Label(container, text="Key label:").grid(row=4, column=0, sticky="w", pady=(8,0))
        self.key_label_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.key_label_var, width=60).grid(row=4, column=1, sticky="we", pady=(8,0))

        ttk.Label(container, text="Cert DER path (optional):").grid(row=5, column=0, sticky="w", pady=(8,0))
        self.cert_der_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.cert_der_var, width=60).grid(row=5, column=1, sticky="we", pady=(8,0))
        ttk.Button(container, text="Browse", command=self._browse_cert_der).grid(row=5, column=2, padx=4, pady=(8,0))

        ttk.Label(container, text="PIN:").grid(row=6, column=0, sticky="w", pady=(8,0))
        self.p7m_pin_var = tk.StringVar()
        ttk.Entry(container, textvariable=self.p7m_pin_var, show="*").grid(row=6, column=1, sticky="w", pady=(8,0))

        # Sign button
        ttk.Button(container, text="Sign File (P7M)", command=self._do_sign_p7m).grid(row=7, column=0, columnspan=3, pady=16)

        # Make grid expand
        container.columnconfigure(1, weight=1)

    def _browse_file(self):
        path = ask_file()
        if path:
            self.file_input_var.set(path)
            base, ext = os.path.splitext(path)
            self.file_output_var.set(base + ".p7m")

    def _save_file_as(self):
        path = ask_save_file(defaultextension=".p7m", filetypes=[("P7M files","*.p7m"),("All files","*.*")])
        if path:
            self.file_output_var.set(path)

    def _browse_p7m_pkcs11(self):
        path = ask_file(filetypes=[("Shared libs","*.so;*.dll;*.dylib"),("All files","*.*")])
        if path:
            self.p7m_pkcs11_var.set(path)

    def _browse_cert_der(self):
        path = ask_file(filetypes=[("DER cert","*.der;*.cer;*.crt"),("All files","*.*")])
        if path:
            self.cert_der_var.set(path)

    def _do_sign_p7m(self):
        input_path = self.file_input_var.get().strip()
        output_path = self.file_output_var.get().strip()
        pkcs11_lib_path = self.p7m_pkcs11_var.get().strip()
        slot_index = int(self.slot_index_var.get()) if self.slot_index_var.get() != "" else 0
        pin = self.p7m_pin_var.get()
        key_label = self.key_label_var.get().strip()
        cert_der_path = self.cert_der_var.get().strip() or None

        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Missing input", "Please select an existing input file.")
            return
        if not output_path:
            messagebox.showerror("Missing output", "Please choose an output filename.")
            return
        if not pkcs11_lib_path:
            messagebox.showerror("Missing PKCS#11 library", "Please specify the PKCS#11 library path.")
            return

        try:
            #messagebox.showinfo("Signing", f"Calling sign_file_p7m...\n\nInput: {input_path}\nOutput: {output_path}")
            sign_file_p7m(
                input_path=input_path,
                output_path=output_path,
                pkcs11_lib_path=pkcs11_lib_path,
                slot_index=slot_index,
                pin=pin,
                key_label=key_label,
                cert_der_path=cert_der_path
            )
            messagebox.showinfo("Done", f"File signed and saved to:\n{output_path}")
        except Exception as e:
            messagebox.showerror("Signing failed", f"An error occurred while signing the file:\n\n{e}")

# ----------------------------------------------------------------------
# Run the app
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app = SignerApp()
    app.mainloop()

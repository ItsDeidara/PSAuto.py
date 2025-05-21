import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab, ImageTk, Image

README_PATH = 'README.md'
SCREENSHOTS_DIR = 'screenshots'

# Regex to extract image placeholders from README
IMG_PATTERN = re.compile(r'!\[([^\]]+)\]\(\./([^\)]+)\)')

class ScreenshotApp(tk.Tk):
    def __init__(self, sections):
        super().__init__()
        self.title('Screenshot Generator for README Tabs')
        self.geometry('600x500')
        self.sections = sections
        self.current_idx = 0
        self.images = {}
        self.skipped = []
        self._build_ui()
        self._show_section()

    def _build_ui(self):
        self.section_label = ttk.Label(self, text='', font=('Arial', 16, 'bold'))
        self.section_label.pack(pady=10)
        self.preview_label = ttk.Label(self, text='No image pasted yet.', relief=tk.SUNKEN, width=50, anchor='center')
        self.preview_label.pack(pady=10, fill=tk.BOTH, expand=True)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        self.paste_btn = ttk.Button(btn_frame, text='Paste Image (Ctrl+V)', command=self._paste_image)
        self.paste_btn.pack(side=tk.LEFT, padx=5)
        self.save_btn = ttk.Button(btn_frame, text='Save Screenshot', command=self._save_image, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=5)
        self.next_btn = ttk.Button(btn_frame, text='Next Section', command=self._next_section, state=tk.DISABLED)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        self.skip_btn = ttk.Button(btn_frame, text='Skip Section', command=self._skip_section)
        self.skip_btn.pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(self, text='')
        self.status_label.pack(pady=5)
        self.bind('<Control-v>', lambda e: self._paste_image())
        self.bind('<Control-V>', lambda e: self._paste_image())

    def _show_section(self):
        if self.current_idx >= len(self.sections):
            self._show_summary()
            return
        section = self.sections[self.current_idx]
        self.section_label.config(text=f'Section: {section}')
        self.preview_label.config(image='', text='No image pasted yet.')
        self.save_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)
        self.status_label.config(text=f'Section {self.current_idx+1} of {len(self.sections)}')
        self.current_image = None
        self.current_imgtk = None

    def _paste_image(self):
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                # Resize preview if too large
                preview = img.copy()
                preview.thumbnail((400, 300))
                self.current_imgtk = ImageTk.PhotoImage(preview)
                self.preview_label.config(image=self.current_imgtk, text='')
                self.current_image = img
                self.save_btn.config(state=tk.NORMAL)
                self.status_label.config(text='Image pasted. Click "Save Screenshot".')
            else:
                messagebox.showerror('No Image', 'Clipboard does not contain an image.')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to grab image from clipboard: {e}')

    def _save_image(self):
        if not self.current_image:
            messagebox.showerror('No Image', 'Paste an image first!')
            return
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        section = self.sections[self.current_idx]
        filename = os.path.join(SCREENSHOTS_DIR, f'{section.replace(" ", "")}.png')
        try:
            self.current_image.save(filename, 'PNG')
            self.images[section] = filename
            self.status_label.config(text=f'Saved: {filename}')
            self.next_btn.config(state=tk.NORMAL)
            self.save_btn.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save image: {e}')

    def _next_section(self):
        self.current_idx += 1
        self._show_section()

    def _skip_section(self):
        section = self.sections[self.current_idx]
        self.skipped.append(section)
        self.current_idx += 1
        self._show_section()

    def _show_summary(self):
        self.section_label.config(text='All Done!')
        self.preview_label.config(image='', text='')
        self.save_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)
        self.skip_btn.config(state=tk.DISABLED)
        summary = ''
        if self.images:
            summary += 'Saved screenshots:\n' + '\n'.join([f'{sec}: {os.path.basename(path)}' for sec, path in self.images.items()]) + '\n\n'
        if self.skipped:
            summary += 'Skipped sections:\n' + '\n'.join(self.skipped)
        if not summary:
            summary = 'No screenshots saved or skipped.'
        self.status_label.config(text=f'Screenshots saved in "{SCREENSHOTS_DIR}" folder.\n\n{summary}')


def extract_sections_from_readme(readme_path):
    with open(readme_path, encoding='utf-8') as f:
        content = f.read()
    # Find all image placeholders and extract section names
    matches = IMG_PATTERN.findall(content)
    # Use the alt text or filename (without extension) as the section name
    sections = []
    for alt, fname in matches:
        # Remove extension and any non-alphanum for filename fallback
        if alt.strip():
            sections.append(alt.strip().replace('.png', '').replace('.PNG', ''))
        else:
            sections.append(os.path.splitext(fname)[0])
    # Remove duplicates while preserving order
    seen = set()
    unique_sections = []
    for s in sections:
        if s not in seen:
            unique_sections.append(s)
            seen.add(s)
    return unique_sections


def main():
    sections = extract_sections_from_readme(README_PATH)
    if not sections:
        print('No screenshot sections found in README.md!')
        return
    app = ScreenshotApp(sections)
    app.mainloop()

if __name__ == '__main__':
    main() 
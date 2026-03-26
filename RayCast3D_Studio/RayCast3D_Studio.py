"""
RayCast3D Studio
A GUI application for building maps, managing textures, and sprites for the RayCast3D graphics library.
Automatically saves project state and exports to assets folder.
"""

import subprocess
import sys
import os
import platform
import shutil

# Auto-install missing dependencies
def _ensure_dependencies():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Pillow not found. Installing automatically...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        print("Pillow installed successfully!")

_ensure_dependencies()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
from PIL import Image, ImageTk, ImageFont, ImageDraw
import json

# Constants
MAP_SIZE = 24
CELL_SIZE = 24  # pixels per cell in the grid display
LABEL_MARGIN = 20  # pixels reserved for coordinate labels
DEFAULT_TEX_RESOLUTION = 64

# Game display constants (for accurate preview)
GAME_WIDTH = 128
GAME_HEIGHT = 160

# Paths - detect if running as PyInstaller bundle
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(SCRIPT_DIR, "../assets")
PROJECT_FILE = os.path.join(SCRIPT_DIR, "studio_project.json")

# Track last-used directory for file dialogs
_last_file_dir = SCRIPT_DIR


def _native_open_file_dialog(title="Select File", filetypes=None):
    """Open a native file dialog, using zenity/kdialog on Linux for a better UX.
    Falls back to tkinter's built-in dialog if neither is available."""
    global _last_file_dir

    if platform.system() == "Linux":
        # Build a zenity/kdialog file filter string from tkinter-style filetypes
        # filetypes example: [("Image files", "*.png *.jpg"), ("All files", "*.*")]
        extensions = []
        if filetypes:
            for desc, patterns in filetypes:
                if patterns != "*.*":
                    for p in patterns.split():
                        extensions.append(p)

        # Try zenity first (GNOME/GTK desktops)
        if shutil.which("zenity"):
            cmd = ["zenity", "--file-selection", "--title", title]
            if extensions:
                # Zenity uses --file-filter="Description | *.png *.jpg"
                filter_str = "Image files | " + " ".join(extensions)
                cmd += ["--file-filter", filter_str, "--file-filter", "All files | *"]
            if _last_file_dir and os.path.isdir(_last_file_dir):
                cmd += ["--filename", _last_file_dir + "/"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    path = result.stdout.strip()
                    _last_file_dir = os.path.dirname(path)
                    return path
                return ""  # User cancelled
            except Exception:
                pass  # Fall through to tkinter

        # Try kdialog (KDE desktops)
        if shutil.which("kdialog"):
            filter_str = ""
            if extensions:
                filter_str = " ".join(extensions) + " | Image files"
            cmd = ["kdialog", "--getopenfilename", _last_file_dir or ".", filter_str, "--title", title]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    path = result.stdout.strip()
                    _last_file_dir = os.path.dirname(path)
                    return path
                return ""  # User cancelled
            except Exception:
                pass  # Fall through to tkinter

    # Fallback: tkinter's built-in dialog (always used on Windows/macOS, or if zenity/kdialog unavailable)
    path = filedialog.askopenfilename(
        title=title,
        filetypes=filetypes or [("All files", "*.*")],
        initialdir=_last_file_dir
    )
    if path:
        _last_file_dir = os.path.dirname(path)
    return path


def resize_and_letterbox(img, width, height, bg_color=(0, 0, 0)):
    """Resize image with aspect ratio preserved and letterbox padding."""
    img_copy = img.copy()
    img_copy.thumbnail((width, height), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), bg_color)
    x = (width - img_copy.width) // 2
    y = (height - img_copy.height) // 2
    canvas.paste(img_copy, (x, y))
    return canvas


def image_to_bgr565_array(img, resolution):
    """Convert PIL image to BGR565 C array format."""
    img = resize_and_letterbox(img, resolution, resolution)
    img = img.convert("RGB")
    pixels = img.load()

    c_vals = []
    for y in range(resolution):
        for x in range(resolution):
            r, g, b = pixels[x, y]
            blue5 = b >> 3
            green6 = g >> 2
            red5 = r >> 3
            color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
            c_vals.append(f"0x{color:04X}")

    return c_vals


def create_checkerboard(width, height, cell_size=4):
    """Create a checkerboard pattern image for transparency preview."""
    checker = Image.new("RGB", (width, height))
    pixels = checker.load()
    colors = [(180, 180, 180), (220, 220, 220)]  # Light and lighter gray
    for y in range(height):
        for x in range(width):
            color_idx = ((x // cell_size) + (y // cell_size)) % 2
            pixels[x, y] = colors[color_idx]
    return checker


class Texture:
    """Represents a wall texture."""
    def __init__(self, name, image_path, resolution, c_array=None):
        self.name = name
        self.image_path = image_path
        self.resolution = resolution
        self.c_array = c_array or []
        self.preview = None  # Tkinter PhotoImage for large preview
        self.tile_preview = None  # Tkinter PhotoImage for map grid (CELL_SIZE x CELL_SIZE)
        self.pil_image = None  # Original PIL image for reprocessing
        self.index = 0  # Texture index in map (1-based, 0 = empty)

    def memory_bytes(self):
        return self.resolution * self.resolution * 2

    def to_dict(self):
        return {
            'name': self.name,
            'image_path': self.image_path,
            'resolution': self.resolution
        }

    @staticmethod
    def from_dict(d):
        return Texture(d['name'], d['image_path'], d['resolution'])


class Sprite:
    """Represents a sprite (always square)."""
    def __init__(self, name, image_path, resolution, c_array=None, transparent=0x0000):
        self.name = name
        self.image_path = image_path
        self.resolution = resolution  # Sprites are always square
        self.c_array = c_array or []
        self.transparent = transparent  # Auto-detected transparent color (BGR565)
        self.preview = None
        self.crop_bounds = None  # (x1, y1, x2, y2) in original source image pixels, or None

    def memory_bytes(self):
        return self.resolution * self.resolution * 2

    def to_dict(self):
        d = {
            'name': self.name,
            'image_path': self.image_path,
            'resolution': self.resolution,
            'transparent': self.transparent
        }
        if self.crop_bounds is not None:
            d['crop_bounds'] = list(self.crop_bounds)
        return d

    @staticmethod
    def from_dict(d):
        # Support loading old projects with width/height
        if 'resolution' in d:
            resolution = d['resolution']
        elif 'width' in d:
            resolution = d['width']  # Use width as resolution for old projects
        else:
            resolution = 32  # Default
        sprite = Sprite(d['name'], d['image_path'], resolution,
                        transparent=d.get('transparent', 0x0000))
        if 'crop_bounds' in d:
            sprite.crop_bounds = tuple(d['crop_bounds'])
        return sprite


class Color:
    """Represents a named color for the game."""
    def __init__(self, name, r, g, b):
        self.name = name
        self.r = r  # 0-255
        self.g = g  # 0-255
        self.b = b  # 0-255

    def to_bgr565(self):
        """Convert RGB to BGR565 format."""
        blue5 = self.b >> 3
        green6 = self.g >> 2
        red5 = self.r >> 3
        return ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)

    def to_hex_string(self):
        """Return color as #RRGGBB hex string for tkinter."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def to_dict(self):
        return {'name': self.name, 'r': self.r, 'g': self.g, 'b': self.b}

    @staticmethod
    def from_dict(d):
        return Color(d['name'], d['r'], d['g'], d['b'])


class RayCast3DStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("RayCast3D Studio")
        self.root.geometry("1000x850")

        # Data
        self.textures = []  # List of Texture objects
        self.sprites = []   # List of Sprite objects
        self.colors = []    # List of Color objects

        # Preserve unloaded entries so saves don't silently drop them
        self._unloaded_textures = []  # List of dicts from JSON that couldn't be loaded
        self._unloaded_sprites = []

        # Multiple maps support
        self.maps = [{"name": "map1", "data": [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]}]
        self.current_map_idx = 0

        self.selected_texture_idx = 1  # 0 = erase, 1+ = texture
        self.is_drawing = False
        self.is_erasing = False  # True when in temporary erase mode (clicked same texture)
        self.tile_images = {}  # Cache for tile PhotoImages on canvas
        self.auto_export_enabled = True  # Auto-export on changes
        self.map_undo_stack = []  # List of (map_idx, data_copy) for undo

        # Font data: 255 characters, each 5 bytes (column-encoded 5x8 bitmap)
        self.font_data = None  # Will be loaded from font.h or initialized to default
        self.font_path = None  # Path to imported TTF/OTF font file

        # UI references for list items
        self.texture_rows = []  # List of (frame, combo_var) tuples
        self.sprite_rows = []
        self.color_rows = []

        # Multi-selection support (sets of selected indices)
        self.selected_texture_rows = set()
        self.selected_sprite_rows = set()
        self.selected_color_rows = set()

        # Last clicked index for Shift+Click range selection
        self.last_texture_click = None
        self.last_sprite_click = None
        self.last_color_click = None

        # Initialize perimeter walls for the first map
        self._init_perimeter()

        # Build UI
        self._build_ui()

        # Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Load saved project if exists
        self._load_project()

        self._update_memory_display()

        # Save on window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_keyboard_shortcuts(self):
        """Setup global keyboard shortcuts."""
        self.root.bind('<Control-t>', lambda e: self._add_texture())
        self.root.bind('<Control-T>', lambda e: self._add_texture())
        self.root.bind('<Control-p>', lambda e: self._add_sprite())  # p for sPrite
        self.root.bind('<Control-P>', lambda e: self._add_sprite())
        self.root.bind('<Delete>', self._on_delete_key)
        self.root.bind('<Control-s>', lambda e: self._save_and_export())
        self.root.bind('<Control-S>', lambda e: self._save_and_export())

        # Tab navigation hints
        self.root.bind('<Control-Key-1>', lambda e: self.notebook.select(0))  # Map tab
        self.root.bind('<Control-Key-2>', lambda e: self.notebook.select(1))  # Textures tab
        self.root.bind('<Control-Key-3>', lambda e: self.notebook.select(2))  # Sprites tab
        self.root.bind('<Control-Key-4>', lambda e: self.notebook.select(3))  # Colors tab
        self.root.bind('<Control-Key-5>', lambda e: self.notebook.select(4))  # Font tab

        # Undo
        self.root.bind('<Control-z>', lambda e: self._undo())
        self.root.bind('<Control-Z>', lambda e: self._undo())

        # Arrow key navigation
        self.root.bind('<Up>', self._on_arrow_up)
        self.root.bind('<Down>', self._on_arrow_down)

        # Escape to deselect
        self.root.bind('<Escape>', self._on_escape_key)

    def _bind_mousewheel(self, canvas, inner_frame):
        def _on_mousewheel(event):
            if platform.system() == 'Windows':
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif platform.system() == 'Darwin':
                canvas.yview_scroll(int(-1 * event.delta), "units")

        def _on_button4(event):  # Linux up
            canvas.yview_scroll(-1, "units")

        def _on_button5(event):  # Linux down
            canvas.yview_scroll(1, "units")

        def _bind_to_all_children(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>", _on_button4)
            widget.bind("<Button-5>", _on_button5)
            for child in widget.winfo_children():
                _bind_to_all_children(child)

        def _unbind_from_all_children(widget):
            widget.unbind("<MouseWheel>")
            widget.unbind("<Button-4>")
            widget.unbind("<Button-5>")
            for child in widget.winfo_children():
                _unbind_from_all_children(child)

        def _enter(e):
            _bind_to_all_children(inner_frame)

        def _leave(e):
            _unbind_from_all_children(inner_frame)

        inner_frame.bind("<Enter>", _enter)
        inner_frame.bind("<Leave>", _leave)

    def _save_and_export(self):
        """Manual save and export."""
        self._save_project()
        self._auto_export()
        self.status_label.config(text="Saved!", foreground='green')

    def _on_delete_key(self, event):
        """Handle delete key press - supports multi-select deletion."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1 and self.selected_texture_rows:
            self._remove_textures()
        elif current_tab == 2 and self.selected_sprite_rows:
            self._remove_sprites()
        elif current_tab == 3 and self.selected_color_rows:
            self._remove_colors()

    def _on_arrow_up(self, event):
        """Handle up arrow key - move selection up (clears multi-select)."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:  # Textures tab
            if not self.selected_texture_rows:
                if self.textures:
                    self._select_texture_row(len(self.textures) - 1, event)
            elif self.last_texture_click is not None and self.last_texture_click > 0:
                self._select_texture_row(self.last_texture_click - 1, event)
        elif current_tab == 2:  # Sprites tab
            if not self.selected_sprite_rows:
                if self.sprites:
                    self._select_sprite_row(len(self.sprites) - 1, event)
            elif self.last_sprite_click is not None and self.last_sprite_click > 0:
                self._select_sprite_row(self.last_sprite_click - 1, event)
        elif current_tab == 3:  # Colors tab
            if not self.selected_color_rows:
                if self.colors:
                    self._select_color_row(len(self.colors) - 1, event)
            elif self.last_color_click is not None and self.last_color_click > 0:
                self._select_color_row(self.last_color_click - 1, event)

    def _on_arrow_down(self, event):
        """Handle down arrow key - move selection down (clears multi-select)."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:  # Textures tab
            if not self.selected_texture_rows:
                if self.textures:
                    self._select_texture_row(0, event)
            elif self.last_texture_click is not None and self.last_texture_click < len(self.textures) - 1:
                self._select_texture_row(self.last_texture_click + 1, event)
        elif current_tab == 2:  # Sprites tab
            if not self.selected_sprite_rows:
                if self.sprites:
                    self._select_sprite_row(0, event)
            elif self.last_sprite_click is not None and self.last_sprite_click < len(self.sprites) - 1:
                self._select_sprite_row(self.last_sprite_click + 1, event)
        elif current_tab == 3:  # Colors tab
            if not self.selected_color_rows:
                if self.colors:
                    self._select_color_row(0, event)
            elif self.last_color_click is not None and self.last_color_click < len(self.colors) - 1:
                self._select_color_row(self.last_color_click + 1, event)

    def _on_escape_key(self, event):
        """Handle escape key - deselect all in current tab."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1:
            self._deselect_all_textures()
        elif current_tab == 2:
            self._deselect_all_sprites()
        elif current_tab == 3:
            self._deselect_all_colors()

    def _on_close(self):
        """Handle window close - save and export before closing."""
        print("Closing - saving project...")
        self._save_project()
        self._auto_export()
        self.root.destroy()

    @property
    def map_data(self):
        """Get current map data (for backwards compatibility)."""
        return self.maps[self.current_map_idx]["data"]

    @property
    def current_map_name(self):
        """Get current map name."""
        return self.maps[self.current_map_idx]["name"]

    def _init_perimeter(self, map_idx=None):
        """Initialize perimeter with texture 1 (default wall)."""
        if map_idx is None:
            map_idx = self.current_map_idx
        data = self.maps[map_idx]["data"]
        for i in range(MAP_SIZE):
            data[0][i] = 1       # Top row
            data[MAP_SIZE-1][i] = 1  # Bottom row
            data[i][0] = 1       # Left column
            data[i][MAP_SIZE-1] = 1  # Right column

    def _build_ui(self):
        """Build the main UI."""
        # Top row: memory total + status
        top_row = ttk.Frame(self.root)
        top_row.pack(fill='x', padx=10, pady=(5, 0))

        self.memory_label = ttk.Label(top_row, text="Memory Usage: 0 bytes", font=('Consolas', 12, 'bold'))
        self.memory_label.pack(side='left')

        self.status_label = ttk.Label(top_row, text="Auto-saving to assets/", font=('Consolas', 9), foreground='green')
        self.status_label.pack(side='right')

        # Second row: memory breakdown + shortcuts
        detail_row = ttk.Frame(self.root)
        detail_row.pack(fill='x', padx=10, pady=(0, 5))

        self.memory_detail = ttk.Label(detail_row, text="", font=('Consolas', 9))
        self.memory_detail.pack(side='left')

        shortcuts_label = ttk.Label(detail_row, text="Ctrl+T/P: Add | Del: Remove | Ctrl+1-5: Tabs",
                                    font=('Consolas', 8), foreground='gray')
        shortcuts_label.pack(side='right')

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab 1: Map Builder
        self.map_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.map_tab, text='Map Builder (Ctrl+1)')
        self._build_map_tab()

        # Tab 2: Texture Manager
        self.texture_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.texture_tab, text='Textures (Ctrl+2)')
        self._build_texture_tab()

        # Tab 3: Sprite Manager
        self.sprite_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.sprite_tab, text='Sprites (Ctrl+3)')
        self._build_sprite_tab()

        # Tab 4: Color Manager
        self.color_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.color_tab, text='Colors (Ctrl+4)')
        self._build_color_tab()

        # Tab 5: Font Manager
        self.font_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.font_tab, text='Font (Ctrl+5)')
        self._build_font_tab()

    def _build_map_tab(self):
        """Build the map editor tab."""
        # Map selection controls at top
        map_ctrl_frame = ttk.Frame(self.map_tab)
        map_ctrl_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(map_ctrl_frame, text="Current Map:", font=('Arial', 10, 'bold')).pack(side='left', padx=5)

        self.map_selector_var = tk.StringVar(value=self.maps[0]["name"])
        self.map_selector = ttk.Combobox(map_ctrl_frame, textvariable=self.map_selector_var,
                                          state='readonly', width=15)
        self.map_selector['values'] = [m["name"] for m in self.maps]
        self.map_selector.pack(side='left', padx=5)
        self.map_selector.bind('<<ComboboxSelected>>', self._on_map_selected)

        ttk.Button(map_ctrl_frame, text="Add Map", command=self._add_map).pack(side='left', padx=5)
        ttk.Button(map_ctrl_frame, text="Rename", command=self._rename_map).pack(side='left', padx=5)
        ttk.Button(map_ctrl_frame, text="Delete", command=self._delete_map).pack(side='left', padx=5)

        ttk.Label(map_ctrl_frame, text=f"({len(self.maps)} map(s))", font=('Arial', 9)).pack(side='left', padx=10)
        self.map_count_label = map_ctrl_frame.winfo_children()[-1]  # Reference to update later

        main_frame = ttk.Frame(self.map_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Left side: Map grid
        left_frame = ttk.LabelFrame(main_frame, text="Map Grid (24x24)")
        left_frame.pack(side='left', fill='both', expand=True)

        # Canvas for map
        canvas_frame = ttk.Frame(left_frame)
        canvas_frame.pack(padx=10, pady=10)

        self.map_canvas = tk.Canvas(canvas_frame,
                                     width=MAP_SIZE * CELL_SIZE + LABEL_MARGIN,
                                     height=MAP_SIZE * CELL_SIZE + LABEL_MARGIN,
                                     highlightthickness=1)
        self.map_canvas.pack()

        # Bind mouse events
        self.map_canvas.bind('<Button-1>', self._on_map_click)
        self.map_canvas.bind('<B1-Motion>', self._on_map_drag)
        self.map_canvas.bind('<ButtonRelease-1>', self._on_map_release)

        self._draw_map_grid()

        # Right side: Texture palette
        right_frame = ttk.LabelFrame(main_frame, text="Texture Palette")
        right_frame.pack(side='right', fill='y', padx=(10, 0))

        # Erase button (only for interior cells)
        self.erase_btn = ttk.Button(right_frame, text="Erase (interior only)", command=lambda: self._select_texture(0))
        self.erase_btn.pack(pady=5, padx=5, fill='x')

        # Texture list with scrollbar
        self.texture_palette_frame = ttk.Frame(right_frame)
        self.texture_palette_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.palette_canvas = tk.Canvas(self.texture_palette_frame, width=150)
        scrollbar = ttk.Scrollbar(self.texture_palette_frame, orient='vertical', command=self.palette_canvas.yview)
        self.palette_inner = ttk.Frame(self.palette_canvas)

        self.palette_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.palette_canvas.pack(side='left', fill='both', expand=True)
        self.palette_canvas.create_window((0, 0), window=self.palette_inner, anchor='nw')

        self.palette_inner.bind('<Configure>', lambda e: self.palette_canvas.configure(scrollregion=self.palette_canvas.bbox('all')))

        # Selected texture indicator
        self.selected_label = ttk.Label(right_frame, text="Selected: Erase", font=('Arial', 10, 'bold'))
        self.selected_label.pack(pady=10)

        # Preview of selected texture
        self.selected_preview_label = ttk.Label(right_frame)
        self.selected_preview_label.pack(pady=5)

        # Instructions
        instr = ttk.Label(right_frame, text="Click/drag to place walls\nPerimeter: texture only\nInterior: any or erase",
                          font=('Arial', 9), foreground='gray')
        instr.pack(pady=10)

        # Floor texture selector
        floor_frame = ttk.LabelFrame(right_frame, text="Floor Texture")
        floor_frame.pack(fill='x', padx=5, pady=(5, 10))

        self.floor_tex_var = tk.StringVar(value="None (gradient)")
        self.floor_tex_combo = ttk.Combobox(floor_frame, textvariable=self.floor_tex_var,
                                             state='readonly', width=18)
        self.floor_tex_combo.pack(padx=5, pady=5, fill='x')
        self.floor_tex_combo.bind('<<ComboboxSelected>>', self._on_floor_texture_changed)
        self._update_floor_texture_combo()

        # Ceiling texture selector
        ceil_frame = ttk.LabelFrame(right_frame, text="Ceiling Texture")
        ceil_frame.pack(fill='x', padx=5, pady=(5, 10))

        self.ceil_tex_var = tk.StringVar(value="None (solid color)")
        self.ceil_tex_combo = ttk.Combobox(ceil_frame, textvariable=self.ceil_tex_var,
                                            state='readonly', width=18)
        self.ceil_tex_combo.pack(padx=5, pady=5, fill='x')
        self.ceil_tex_combo.bind('<<ComboboxSelected>>', self._on_ceil_texture_changed)
        self._update_ceil_texture_combo()

    def _update_floor_texture_combo(self):
        """Update the floor texture dropdown with current textures."""
        choices = ["None (gradient)"] + [t.name for t in self.textures]
        self.floor_tex_combo['values'] = choices

        # Restore selection from map data
        floor_idx = self.maps[self.current_map_idx].get("floor_texture", 0)
        if floor_idx > 0 and floor_idx <= len(self.textures):
            self.floor_tex_var.set(self.textures[floor_idx - 1].name)
        else:
            self.floor_tex_var.set("None (gradient)")

    def _update_ceil_texture_combo(self):
        """Update the ceiling texture dropdown with current textures."""
        choices = ["None (solid color)"] + [t.name for t in self.textures]
        self.ceil_tex_combo['values'] = choices

        # Restore selection from map data
        ceil_idx = self.maps[self.current_map_idx].get("ceiling_texture", 0)
        if ceil_idx > 0 and ceil_idx <= len(self.textures):
            self.ceil_tex_var.set(self.textures[ceil_idx - 1].name)
        else:
            self.ceil_tex_var.set("None (solid color)")

    def _on_floor_texture_changed(self, event=None):
        """Handle floor texture selection change."""
        selection = self.floor_tex_var.get()
        if selection == "None (gradient)":
            self.maps[self.current_map_idx]["floor_texture"] = 0
        else:
            for i, tex in enumerate(self.textures):
                if tex.name == selection:
                    self.maps[self.current_map_idx]["floor_texture"] = i + 1
                    break
        self._auto_export()
        self._save_project()

    def _on_ceil_texture_changed(self, event=None):
        """Handle ceiling texture selection change."""
        selection = self.ceil_tex_var.get()
        if selection == "None (solid color)":
            self.maps[self.current_map_idx]["ceiling_texture"] = 0
        else:
            for i, tex in enumerate(self.textures):
                if tex.name == selection:
                    self.maps[self.current_map_idx]["ceiling_texture"] = i + 1
                    break
        self._auto_export()
        self._save_project()

    def _build_texture_tab(self):
        """Build the texture manager tab."""
        main_frame = ttk.Frame(self.texture_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Controls
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill='x', pady=(0, 10))

        add_btn = ttk.Button(ctrl_frame, text="Add Texture (Ctrl+T)", command=self._add_texture)
        add_btn.pack(side='left', padx=5)

        remove_btn = ttk.Button(ctrl_frame, text="Remove Selected (Del)", command=self._remove_textures)
        remove_btn.pack(side='left', padx=5)

        rename_btn = ttk.Button(ctrl_frame, text="Rename", command=self._rename_texture)
        rename_btn.pack(side='left', padx=5)

        ttk.Label(ctrl_frame, text="Default Resolution:").pack(side='left', padx=(20, 5))
        self.tex_res_var = tk.StringVar(value="64")
        res_combo = ttk.Combobox(ctrl_frame, textvariable=self.tex_res_var, values=["16", "32", "64", "128"], width=6)
        res_combo.pack(side='left')

        # Column widths for alignment (in pixels)
        self.tex_col_widths = [150, 100, 100]  # Name, Resolution, Memory

        # Header row (padx on right accounts for scrollbar width)
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(5, 0), padx=(0, 15))
        header_frame.columnconfigure(0, minsize=self.tex_col_widths[0])
        header_frame.columnconfigure(1, minsize=self.tex_col_widths[1])
        header_frame.columnconfigure(2, minsize=self.tex_col_widths[2])
        ttk.Label(header_frame, text="Name", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=0, sticky='w', padx=5)
        ttk.Label(header_frame, text="Resolution", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(header_frame, text="Memory", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=2, sticky='w', padx=5)

        # Scrollable texture list
        list_container = ttk.Frame(main_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.texture_canvas = tk.Canvas(list_container, highlightthickness=0)
        texture_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.texture_canvas.yview)
        self.texture_list_frame = ttk.Frame(self.texture_canvas)
        self._bind_mousewheel(self.texture_canvas, self.texture_list_frame)

        # Configure grid columns on list frame to match header
        self.texture_list_frame.columnconfigure(0, minsize=self.tex_col_widths[0])
        self.texture_list_frame.columnconfigure(1, minsize=self.tex_col_widths[1])
        self.texture_list_frame.columnconfigure(2, minsize=self.tex_col_widths[2])

        self.texture_canvas.configure(yscrollcommand=texture_scrollbar.set)
        texture_scrollbar.pack(side='right', fill='y')
        self.texture_canvas.pack(side='left', fill='both', expand=True)
        self.texture_canvas_window = self.texture_canvas.create_window((0, 0), window=self.texture_list_frame, anchor='nw')

        self.texture_list_frame.bind('<Configure>', lambda e: self.texture_canvas.configure(scrollregion=self.texture_canvas.bbox('all')))
        self.texture_canvas.bind('<Configure>', lambda e: self.texture_canvas.itemconfig(self.texture_canvas_window, width=e.width))

        # Preview area
        preview_frame = ttk.LabelFrame(main_frame, text="Preview (Simulated In-Game Wall View)")
        preview_frame.pack(fill='x', pady=10)

        preview_inner = ttk.Frame(preview_frame)
        preview_inner.pack(padx=10, pady=10)

        self.tex_preview_label = ttk.Label(preview_inner)
        self.tex_preview_label.pack(side='left', padx=10)

        self.tex_preview_info = ttk.Label(preview_inner, text="", font=('Consolas', 9), justify='left')
        self.tex_preview_info.pack(side='left', padx=10)

    def _build_sprite_tab(self):
        """Build the sprite manager tab."""
        main_frame = ttk.Frame(self.sprite_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Controls
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill='x', pady=(0, 10))

        add_btn = ttk.Button(ctrl_frame, text="Add Sprite (Ctrl+P)", command=self._add_sprite)
        add_btn.pack(side='left', padx=5)

        remove_btn = ttk.Button(ctrl_frame, text="Remove Selected (Del)", command=self._remove_sprites)
        remove_btn.pack(side='left', padx=5)

        rename_btn = ttk.Button(ctrl_frame, text="Rename", command=self._rename_sprite)
        rename_btn.pack(side='left', padx=5)

        ttk.Label(ctrl_frame, text="Default Resolution:").pack(side='left', padx=(20, 5))
        self.sprite_res_var = tk.StringVar(value="32")
        ttk.Combobox(ctrl_frame, textvariable=self.sprite_res_var, values=["16", "32", "64", "128"], width=5).pack(side='left')

        # Column widths for alignment (in pixels)
        self.sprite_col_widths = [150, 100, 100]  # Name, Resolution, Memory

        # Header row (padx on right accounts for scrollbar width)
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(5, 0), padx=(0, 15))
        header_frame.columnconfigure(0, minsize=self.sprite_col_widths[0])
        header_frame.columnconfigure(1, minsize=self.sprite_col_widths[1])
        header_frame.columnconfigure(2, minsize=self.sprite_col_widths[2])
        ttk.Label(header_frame, text="Name", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=0, sticky='w', padx=5)
        ttk.Label(header_frame, text="Resolution", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(header_frame, text="Memory", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=2, sticky='w', padx=5)

        # Scrollable sprite list
        list_container = ttk.Frame(main_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.sprite_canvas = tk.Canvas(list_container, highlightthickness=0)
        sprite_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.sprite_canvas.yview)
        self.sprite_list_frame = ttk.Frame(self.sprite_canvas)
        self._bind_mousewheel(self.sprite_canvas, self.sprite_list_frame)

        # Configure grid columns on list frame to match header
        self.sprite_list_frame.columnconfigure(0, minsize=self.sprite_col_widths[0])
        self.sprite_list_frame.columnconfigure(1, minsize=self.sprite_col_widths[1])
        self.sprite_list_frame.columnconfigure(2, minsize=self.sprite_col_widths[2])

        self.sprite_canvas.configure(yscrollcommand=sprite_scrollbar.set)
        sprite_scrollbar.pack(side='right', fill='y')
        self.sprite_canvas.pack(side='left', fill='both', expand=True)
        self.sprite_canvas_window = self.sprite_canvas.create_window((0, 0), window=self.sprite_list_frame, anchor='nw')

        self.sprite_list_frame.bind('<Configure>', lambda e: self.sprite_canvas.configure(scrollregion=self.sprite_canvas.bbox('all')))
        self.sprite_canvas.bind('<Configure>', lambda e: self.sprite_canvas.itemconfig(self.sprite_canvas_window, width=e.width))

        # Preview area
        preview_frame = ttk.LabelFrame(main_frame, text="Preview (Simulated In-Game Sprite)")
        preview_frame.pack(fill='x', pady=10)

        preview_inner = ttk.Frame(preview_frame)
        preview_inner.pack(padx=10, pady=10)

        self.sprite_preview_label = ttk.Label(preview_inner)
        self.sprite_preview_label.pack(side='left', padx=10)

        self.sprite_preview_info = ttk.Label(preview_inner, text="", font=('Consolas', 9), justify='left')
        self.sprite_preview_info.pack(side='left', padx=10)

        # Edit Sprite button
        self.edit_sprite_btn = ttk.Button(preview_inner, text="Edit Sprite",
                                                 command=self._edit_sprite_transparency, state='disabled')
        self.edit_sprite_btn.pack(side='left', padx=10)

    def _build_color_tab(self):
        """Build the color manager tab."""
        main_frame = ttk.Frame(self.color_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Controls
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill='x', pady=(0, 10))

        add_btn = ttk.Button(ctrl_frame, text="Add Color", command=self._add_color)
        add_btn.pack(side='left', padx=5)

        remove_btn = ttk.Button(ctrl_frame, text="Remove Selected", command=self._remove_colors)
        remove_btn.pack(side='left', padx=5)

        edit_btn = ttk.Button(ctrl_frame, text="Edit Color", command=self._edit_color)
        edit_btn.pack(side='left', padx=5)

        rename_btn = ttk.Button(ctrl_frame, text="Rename", command=self._rename_color)
        rename_btn.pack(side='left', padx=5)

        # Column widths for alignment (in pixels)
        self.color_col_widths = [150, 55, 80, 110]  # Name, Color, BGR565, RGB

        # Header row (padx on right accounts for scrollbar width)
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(5, 0), padx=(0, 15))
        header_frame.columnconfigure(0, minsize=self.color_col_widths[0])
        header_frame.columnconfigure(1, minsize=self.color_col_widths[1])
        header_frame.columnconfigure(2, minsize=self.color_col_widths[2])
        header_frame.columnconfigure(3, minsize=self.color_col_widths[3])
        ttk.Label(header_frame, text="Name", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=0, sticky='w', padx=5)
        ttk.Label(header_frame, text="Color", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=1, sticky='w', padx=5)
        ttk.Label(header_frame, text="BGR565", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=2, sticky='w', padx=5)
        ttk.Label(header_frame, text="RGB", font=('Arial', 10, 'bold'), anchor='w').grid(row=0, column=3, sticky='w', padx=5)

        # Scrollable color list
        list_container = ttk.Frame(main_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.color_canvas = tk.Canvas(list_container, highlightthickness=0)
        color_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.color_canvas.yview)
        self.color_list_frame = ttk.Frame(self.color_canvas)
        self._bind_mousewheel(self.color_canvas, self.color_list_frame)

        # Configure grid columns on list frame to match header
        self.color_list_frame.columnconfigure(0, minsize=self.color_col_widths[0])
        self.color_list_frame.columnconfigure(1, minsize=self.color_col_widths[1])
        self.color_list_frame.columnconfigure(2, minsize=self.color_col_widths[2])
        self.color_list_frame.columnconfigure(3, minsize=self.color_col_widths[3])

        self.color_canvas.configure(yscrollcommand=color_scrollbar.set)
        color_scrollbar.pack(side='right', fill='y')
        self.color_canvas.pack(side='left', fill='both', expand=True)
        self.color_canvas_window = self.color_canvas.create_window((0, 0), window=self.color_list_frame, anchor='nw')

        self.color_list_frame.bind('<Configure>', lambda e: self.color_canvas.configure(scrollregion=self.color_canvas.bbox('all')))
        self.color_canvas.bind('<Configure>', lambda e: self.color_canvas.itemconfig(self.color_canvas_window, width=e.width))

        # Color rows tracking
        self.color_rows = []
        self.selected_color_row = None

        # Info area
        info_frame = ttk.LabelFrame(main_frame, text="Info")
        info_frame.pack(fill='x', pady=10)

        info_text = ttk.Label(info_frame, text="Colors are exported to assets/colors.h as BGR565 constants.\n"
                                               "Use them in your code like: Graphics_SetFloorColor(COLOR_SKY);",
                              font=('Consolas', 9), justify='left')
        info_text.pack(padx=10, pady=10)

    def _build_font_tab(self):
        """Build the font manager tab."""
        main_frame = ttk.Frame(self.font_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Controls
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(ctrl_frame, text="Import Font (TTF/OTF)", command=self._import_font).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Reset to Default", command=self._reset_font_to_default).pack(side='left', padx=5)

        # Font info label
        self.font_info_label = ttk.Label(ctrl_frame, text="Font: default (5x8)", font=('Consolas', 9))
        self.font_info_label.pack(side='left', padx=15)

        # Content area: character grid on the left, editor on the right
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill='both', expand=True)

        # LEFT: Character grid preview
        grid_outer = ttk.LabelFrame(content_frame, text="Character Map (click to edit)")
        grid_outer.pack(side='left', fill='both', expand=True, padx=(0, 5))

        # Scrollable canvas for the character grid
        grid_scroll_frame = ttk.Frame(grid_outer)
        grid_scroll_frame.pack(fill='both', expand=True)

        grid_vscroll = ttk.Scrollbar(grid_scroll_frame, orient='vertical')
        self.font_grid_canvas = tk.Canvas(grid_scroll_frame, highlightthickness=0,
                                          yscrollcommand=grid_vscroll.set)
        grid_vscroll.config(command=self.font_grid_canvas.yview)
        grid_vscroll.pack(side='right', fill='y')
        self.font_grid_canvas.pack(side='left', fill='both', expand=True)
        self._bind_mousewheel(self.font_grid_canvas, grid_scroll_frame)

        self.font_grid_canvas.bind('<Button-1>', self._on_font_grid_click)

        # RIGHT: Pixel editor for selected character
        editor_outer = ttk.LabelFrame(content_frame, text="Character Editor")
        editor_outer.pack(side='right', fill='y', padx=(5, 0))

        self.font_char_label = ttk.Label(editor_outer, text="Select a character", font=('Consolas', 10))
        self.font_char_label.pack(pady=5)

        # Pixel editing canvas (5 cols x 8 rows, each pixel drawn as a large square)
        FONT_PIXEL = 28  # Size of each pixel in the editor
        editor_w = 5 * FONT_PIXEL
        editor_h = 8 * FONT_PIXEL
        self.font_editor_canvas = tk.Canvas(editor_outer, width=editor_w, height=editor_h,
                                            bg='white', highlightthickness=1, highlightbackground='gray')
        self.font_editor_canvas.pack(padx=10, pady=5)
        self.font_editor_canvas.bind('<Button-1>', self._on_font_pixel_click)
        self.font_editor_canvas.bind('<B1-Motion>', self._on_font_pixel_drag)
        self.font_editor_pixel_size = FONT_PIXEL
        self.font_selected_char = None
        self.font_draw_value = 1  # 1 = draw, 0 = erase (set on press)

        # Navigation buttons
        nav_frame = ttk.Frame(editor_outer)
        nav_frame.pack(pady=5)
        ttk.Button(nav_frame, text="< Prev", command=self._font_prev_char).pack(side='left', padx=5)
        ttk.Button(nav_frame, text="Next >", command=self._font_next_char).pack(side='left', padx=5)
        ttk.Button(nav_frame, text="Clear", command=self._font_clear_char).pack(side='left', padx=5)
        ttk.Button(nav_frame, text="Invert", command=self._font_invert_char).pack(side='left', padx=5)

        # Character preview at actual size
        ttk.Label(editor_outer, text="Preview (actual size):", font=('Arial', 9)).pack(pady=(10, 2))
        self.font_preview_canvas = tk.Canvas(editor_outer, width=60, height=48, bg='black',
                                             highlightthickness=1, highlightbackground='gray')
        self.font_preview_canvas.pack(padx=10, pady=5)

        # Info
        info_frame = ttk.LabelFrame(main_frame, text="Info")
        info_frame.pack(fill='x', pady=(10, 0))
        ttk.Label(info_frame,
                  text="Font is exported to assets/font.h as a 5x8 column-encoded bitmap array (5 bytes per character).\n"
                       "Import a TTF/OTF file to auto-generate all glyphs, then fine-tune individual characters in the editor.",
                  font=('Consolas', 9), justify='left').pack(padx=10, pady=10)

    def _load_font_from_h(self):
        """Parse the existing font.h and load font_data from it."""
        font_h_path = os.path.join(ASSETS_DIR, "font.h")
        if not os.path.exists(font_h_path):
            return False

        try:
            import re
            with open(font_h_path, 'r') as f:
                content = f.read()

            # Find the Font[] array data (between { and };)
            match = re.search(r'static\s+const\s+uint8_t\s+Font\[\]\s*=\s*\{(.*?)\};', content, re.DOTALL)
            if not match:
                return False

            array_body = match.group(1)

            # Extract all byte values (hex like 0xFF or decimal like 127)
            # Each line has 5 values + a comment
            byte_values = []
            for line in array_body.split('\n'):
                # Strip comments
                line = line.split('//')[0].strip()
                if not line:
                    continue
                # Handle preprocessor directives - skip #if/#else/#endif but include data lines
                if line.startswith('#'):
                    continue
                # Find all numeric values
                for token in re.findall(r'0x[0-9A-Fa-f]+|\d+', line):
                    if token.startswith('0x') or token.startswith('0X'):
                        byte_values.append(int(token, 16))
                    else:
                        byte_values.append(int(token))

            # Should be 255 * 5 = 1275 bytes (chars 0-254)
            # Due to #if blocks, we may have extra data. Take exactly 255 chars worth.
            if len(byte_values) < 255 * 5:
                return False

            self.font_data = []
            for i in range(255):
                offset = i * 5
                self.font_data.append(list(byte_values[offset:offset + 5]))

            return True
        except Exception as e:
            print(f"Error parsing font.h: {e}")
            return False

    def _get_default_font_data(self):
        """Return the default ASCII 5x7 font data (255 chars x 5 bytes)."""
        # Standard ASCII font from Adafruit glcdfont.c
        default = [
            [0x00,0x00,0x00,0x00,0x00],[0x3E,0x5B,0x4F,0x5B,0x3E],[0x3E,0x6B,0x4F,0x6B,0x3E],
            [0x1C,0x3E,0x7C,0x3E,0x1C],[0x18,0x3C,0x7E,0x3C,0x18],[0x1C,0x57,0x7D,0x57,0x1C],
            [0x1C,0x5E,0x7F,0x5E,0x1C],[0x00,0x18,0x3C,0x18,0x00],[0xFF,0xE7,0xC3,0xE7,0xFF],
            [0x00,0x18,0x24,0x18,0x00],[0xFF,0xE7,0xDB,0xE7,0xFF],[0x30,0x48,0x3A,0x06,0x0E],
            [0x26,0x29,0x79,0x29,0x26],[0x40,0x7F,0x05,0x05,0x07],[0x40,0x7F,0x05,0x25,0x3F],
            [0x5A,0x3C,0xE7,0x3C,0x5A],[0x7F,0x3E,0x1C,0x1C,0x08],[0x08,0x1C,0x1C,0x3E,0x7F],
            [0x14,0x22,0x7F,0x22,0x14],[0x5F,0x5F,0x00,0x5F,0x5F],[0x06,0x09,0x7F,0x01,0x7F],
            [0x00,0x66,0x89,0x95,0x6A],[0x60,0x60,0x60,0x60,0x60],[0x94,0xA2,0xFF,0xA2,0x94],
            [0x08,0x04,0x7E,0x04,0x08],[0x10,0x20,0x7E,0x20,0x10],[0x08,0x08,0x2A,0x1C,0x08],
            [0x08,0x1C,0x2A,0x08,0x08],[0x1E,0x10,0x10,0x10,0x10],[0x0C,0x1E,0x0C,0x1E,0x0C],
            [0x30,0x38,0x3E,0x38,0x30],[0x06,0x0E,0x3E,0x0E,0x06],
            # 32-47: SP ! " # $ % & ' ( ) * + , - . /
            [0x00,0x00,0x00,0x00,0x00],[0x00,0x00,0x5F,0x00,0x00],[0x00,0x07,0x00,0x07,0x00],
            [0x14,0x7F,0x14,0x7F,0x14],[0x24,0x2A,0x7F,0x2A,0x12],[0x23,0x13,0x08,0x64,0x62],
            [0x36,0x49,0x56,0x20,0x50],[0x00,0x08,0x07,0x03,0x00],[0x00,0x1C,0x22,0x41,0x00],
            [0x00,0x41,0x22,0x1C,0x00],[0x2A,0x1C,0x7F,0x1C,0x2A],[0x08,0x08,0x3E,0x08,0x08],
            [0x00,0x80,0x70,0x30,0x00],[0x08,0x08,0x08,0x08,0x08],[0x00,0x00,0x60,0x60,0x00],
            [0x20,0x10,0x08,0x04,0x02],
            # 48-63: 0-9 : ; < = > ?
            [0x3E,0x51,0x49,0x45,0x3E],[0x00,0x42,0x7F,0x40,0x00],[0x72,0x49,0x49,0x49,0x46],
            [0x21,0x41,0x49,0x4D,0x33],[0x18,0x14,0x12,0x7F,0x10],[0x27,0x45,0x45,0x45,0x39],
            [0x3C,0x4A,0x49,0x49,0x31],[0x41,0x21,0x11,0x09,0x07],[0x36,0x49,0x49,0x49,0x36],
            [0x46,0x49,0x49,0x29,0x1E],[0x00,0x00,0x14,0x00,0x00],[0x00,0x40,0x34,0x00,0x00],
            [0x00,0x08,0x14,0x22,0x41],[0x14,0x14,0x14,0x14,0x14],[0x00,0x41,0x22,0x14,0x08],
            [0x02,0x01,0x59,0x09,0x06],
            # 64: @
            [0x3E,0x41,0x5D,0x59,0x4E],
            # 65-90: A-Z
            [0x7C,0x12,0x11,0x12,0x7C],[0x7F,0x49,0x49,0x49,0x36],[0x3E,0x41,0x41,0x41,0x22],
            [0x7F,0x41,0x41,0x41,0x3E],[0x7F,0x49,0x49,0x49,0x41],[0x7F,0x09,0x09,0x09,0x01],
            [0x3E,0x41,0x41,0x51,0x73],[0x7F,0x08,0x08,0x08,0x7F],[0x00,0x41,0x7F,0x41,0x00],
            [0x20,0x40,0x41,0x3F,0x01],[0x7F,0x08,0x14,0x22,0x41],[0x7F,0x40,0x40,0x40,0x40],
            [0x7F,0x02,0x1C,0x02,0x7F],[0x7F,0x04,0x08,0x10,0x7F],[0x3E,0x41,0x41,0x41,0x3E],
            [0x7F,0x09,0x09,0x09,0x06],[0x3E,0x41,0x51,0x21,0x5E],[0x7F,0x09,0x19,0x29,0x46],
            [0x26,0x49,0x49,0x49,0x32],[0x03,0x01,0x7F,0x01,0x03],[0x3F,0x40,0x40,0x40,0x3F],
            [0x1F,0x20,0x40,0x20,0x1F],[0x3F,0x40,0x38,0x40,0x3F],[0x63,0x14,0x08,0x14,0x63],
            [0x03,0x04,0x78,0x04,0x03],[0x61,0x59,0x49,0x4D,0x43],
            # 91-96: [ \ ] ^ _ `
            [0x00,0x7F,0x41,0x41,0x41],[0x02,0x04,0x08,0x10,0x20],[0x00,0x41,0x41,0x41,0x7F],
            [0x04,0x02,0x01,0x02,0x04],[0x40,0x40,0x40,0x40,0x40],[0x00,0x03,0x07,0x08,0x00],
            # 97-122: a-z
            [0x20,0x54,0x54,0x78,0x40],[0x7F,0x28,0x44,0x44,0x38],[0x38,0x44,0x44,0x44,0x28],
            [0x38,0x44,0x44,0x28,0x7F],[0x38,0x54,0x54,0x54,0x18],[0x00,0x08,0x7E,0x09,0x02],
            [0x18,0xA4,0xA4,0x9C,0x78],[0x7F,0x08,0x04,0x04,0x78],[0x00,0x44,0x7D,0x40,0x00],
            [0x20,0x40,0x40,0x3D,0x00],[0x7F,0x10,0x28,0x44,0x00],[0x00,0x41,0x7F,0x40,0x00],
            [0x7C,0x04,0x78,0x04,0x78],[0x7C,0x08,0x04,0x04,0x78],[0x38,0x44,0x44,0x44,0x38],
            [0xFC,0x18,0x24,0x24,0x18],[0x18,0x24,0x24,0x18,0xFC],[0x7C,0x08,0x04,0x04,0x08],
            [0x48,0x54,0x54,0x54,0x24],[0x04,0x04,0x3F,0x44,0x24],[0x3C,0x40,0x40,0x20,0x7C],
            [0x1C,0x20,0x40,0x20,0x1C],[0x3C,0x40,0x30,0x40,0x3C],[0x44,0x28,0x10,0x28,0x44],
            [0x4C,0x90,0x90,0x90,0x7C],[0x44,0x64,0x54,0x4C,0x44],
            # 123-127: { | } ~ DEL
            [0x00,0x08,0x36,0x41,0x00],[0x00,0x00,0x77,0x00,0x00],[0x00,0x41,0x36,0x08,0x00],
            [0x02,0x01,0x02,0x04,0x02],[0x3C,0x26,0x23,0x26,0x3C],
            # 128-254: extended ASCII
            [0x1E,0xA1,0xA1,0x61,0x12],[0x3A,0x40,0x40,0x20,0x7A],[0x38,0x54,0x54,0x55,0x59],
            [0x21,0x55,0x55,0x79,0x41],[0x21,0x54,0x54,0x78,0x41],[0x21,0x55,0x54,0x78,0x40],
            [0x20,0x54,0x55,0x79,0x40],[0x0C,0x1E,0x52,0x72,0x12],[0x39,0x55,0x55,0x55,0x59],
            [0x39,0x54,0x54,0x54,0x59],[0x39,0x55,0x54,0x54,0x58],[0x00,0x00,0x45,0x7C,0x41],
            [0x00,0x02,0x45,0x7D,0x42],[0x00,0x01,0x45,0x7C,0x40],[0xF0,0x29,0x24,0x29,0xF0],
            [0xF0,0x28,0x25,0x28,0xF0],[0x7C,0x54,0x55,0x45,0x00],[0x20,0x54,0x54,0x7C,0x54],
            [0x7C,0x0A,0x09,0x7F,0x49],[0x32,0x49,0x49,0x49,0x32],[0x32,0x48,0x48,0x48,0x32],
            [0x32,0x4A,0x48,0x48,0x30],[0x3A,0x41,0x41,0x21,0x7A],[0x3A,0x42,0x40,0x20,0x78],
            [0x00,0x9D,0xA0,0xA0,0x7D],[0x39,0x44,0x44,0x44,0x39],[0x3D,0x40,0x40,0x40,0x3D],
            [0x3C,0x24,0xFF,0x24,0x24],[0x48,0x7E,0x49,0x43,0x66],[0x2B,0x2F,0xFC,0x2F,0x2B],
            [0xFF,0x09,0x29,0xF6,0x20],[0xC0,0x88,0x7E,0x09,0x03],[0x20,0x54,0x54,0x79,0x41],
            [0x00,0x00,0x44,0x7D,0x41],[0x30,0x48,0x48,0x4A,0x32],[0x38,0x40,0x40,0x22,0x7A],
            [0x00,0x7A,0x0A,0x0A,0x72],[0x7D,0x0D,0x19,0x31,0x7D],[0x26,0x29,0x29,0x2F,0x28],
            [0x26,0x29,0x29,0x29,0x26],[0x30,0x48,0x4D,0x40,0x20],[0x38,0x08,0x08,0x08,0x08],
            [0x08,0x08,0x08,0x08,0x38],[0x2F,0x10,0xC8,0xAC,0xBA],[0x2F,0x10,0x28,0x34,0xFA],
            [0x00,0x00,0x7B,0x00,0x00],[0x08,0x14,0x2A,0x14,0x22],[0x22,0x14,0x2A,0x14,0x08],
            [0xAA,0x00,0x55,0x00,0xAA],[0xAA,0x55,0xAA,0x55,0xAA],[0x00,0x00,0x00,0xFF,0x00],
            [0x10,0x10,0x10,0xFF,0x00],[0x14,0x14,0x14,0xFF,0x00],[0x10,0x10,0xFF,0x00,0xFF],
            [0x10,0x10,0xF0,0x10,0xF0],[0x14,0x14,0x14,0xFC,0x00],[0x14,0x14,0xF7,0x00,0xFF],
            [0x00,0x00,0xFF,0x00,0xFF],[0x14,0x14,0xF4,0x04,0xFC],[0x14,0x14,0x17,0x10,0x1F],
            [0x10,0x10,0x1F,0x10,0x1F],[0x14,0x14,0x14,0x1F,0x00],[0x10,0x10,0x10,0xF0,0x00],
            [0x00,0x00,0x00,0x1F,0x10],[0x10,0x10,0x10,0x1F,0x10],[0x10,0x10,0x10,0xF0,0x10],
            [0x00,0x00,0x00,0xFF,0x10],[0x10,0x10,0x10,0x10,0x10],[0x10,0x10,0x10,0xFF,0x10],
            [0x00,0x00,0x00,0xFF,0x14],[0x00,0x00,0xFF,0x00,0xFF],[0x00,0x00,0x1F,0x10,0x17],
            [0x00,0x00,0xFC,0x04,0xF4],[0x14,0x14,0x17,0x10,0x17],[0x14,0x14,0xF4,0x04,0xF4],
            [0x00,0x00,0xFF,0x00,0xF7],[0x14,0x14,0x14,0x14,0x14],[0x14,0x14,0xF7,0x00,0xF7],
            [0x14,0x14,0x14,0x17,0x14],[0x10,0x10,0x1F,0x10,0x1F],[0x14,0x14,0x14,0xF4,0x14],
            [0x10,0x10,0xF0,0x10,0xF0],[0x00,0x00,0x1F,0x10,0x1F],[0x00,0x00,0x00,0x1F,0x14],
            [0x00,0x00,0x00,0xFC,0x14],[0x00,0x00,0xF0,0x10,0xF0],[0x10,0x10,0xFF,0x10,0xFF],
            [0x14,0x14,0x14,0xFF,0x14],[0x10,0x10,0x10,0x1F,0x00],[0x00,0x00,0x00,0xF0,0x10],
            [0xFF,0xFF,0xFF,0xFF,0xFF],[0xF0,0xF0,0xF0,0xF0,0xF0],[0xFF,0xFF,0xFF,0x00,0x00],
            [0x00,0x00,0x00,0xFF,0xFF],[0x0F,0x0F,0x0F,0x0F,0x0F],[0x38,0x44,0x44,0x38,0x44],
            [0x7C,0x2A,0x2A,0x3E,0x14],[0x7E,0x02,0x02,0x06,0x06],[0x02,0x7E,0x02,0x7E,0x02],
            [0x63,0x55,0x49,0x41,0x63],[0x38,0x44,0x44,0x3C,0x04],[0x40,0x7E,0x20,0x1E,0x20],
            [0x06,0x02,0x7E,0x02,0x02],[0x99,0xA5,0xE7,0xA5,0x99],[0x1C,0x2A,0x49,0x2A,0x1C],
            [0x4C,0x72,0x01,0x72,0x4C],[0x30,0x4A,0x4D,0x4D,0x30],[0x30,0x48,0x78,0x48,0x30],
            [0xBC,0x62,0x5A,0x46,0x3D],[0x3E,0x49,0x49,0x49,0x00],[0x7E,0x01,0x01,0x01,0x7E],
            [0x2A,0x2A,0x2A,0x2A,0x2A],[0x44,0x44,0x5F,0x44,0x44],[0x40,0x51,0x4A,0x44,0x40],
            [0x40,0x44,0x4A,0x51,0x40],[0x00,0x00,0xFF,0x01,0x03],[0xE0,0x80,0xFF,0x00,0x00],
            [0x08,0x08,0x6B,0x6B,0x08],[0x36,0x12,0x36,0x24,0x36],[0x06,0x0F,0x09,0x0F,0x06],
            [0x00,0x00,0x18,0x18,0x00],[0x00,0x00,0x10,0x10,0x00],[0x30,0x40,0xFF,0x01,0x01],
            [0x00,0x1F,0x01,0x01,0x1E],[0x00,0x19,0x1D,0x17,0x12],[0x00,0x3C,0x3C,0x3C,0x3C],
            [0x00,0x00,0x00,0x00,0x00],
        ]
        return default

    def _init_font_data(self):
        """Initialize font data from font.h or defaults."""
        if self.font_data is None:
            if not self._load_font_from_h():
                self.font_data = self._get_default_font_data()

    def _refresh_font_grid(self):
        """Redraw the character map grid on the font tab canvas."""
        self._init_font_data()
        canvas = self.font_grid_canvas
        canvas.delete('all')

        cols = 16  # Characters per row
        rows = 16  # 256 / 16 (we show 0-254, char 255 slot is empty)
        cell = 32  # Cell size in pixels for each character
        pad = 2

        # Draw column headers (hex digit)
        for c in range(cols):
            canvas.create_text(cell + c * cell + cell // 2, cell // 2,
                               text=f"{c:X}", font=('Consolas', 9, 'bold'), fill='gray')
        # Draw row headers
        for r in range(rows):
            canvas.create_text(cell // 2, cell + r * cell + cell // 2,
                               text=f"{r:X}x", font=('Consolas', 9, 'bold'), fill='gray')

        total_w = cell * (cols + 1)
        total_h = cell * (rows + 1)

        for char_idx in range(255):
            r = char_idx // cols
            c = char_idx % cols
            x0 = cell + c * cell
            y0 = cell + r * cell

            # Draw cell background
            bg = '#E0E8FF' if char_idx == self.font_selected_char else 'white'
            canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=bg, outline='#CCCCCC')

            # Render the 5x8 character bitmap into the cell
            char_bytes = self.font_data[char_idx]
            pixel = 3  # Pixel size within cell
            ox = x0 + (cell - 5 * pixel) // 2
            oy = y0 + (cell - 8 * pixel) // 2
            for col in range(5):
                col_data = char_bytes[col]
                for row in range(8):
                    if (col_data >> row) & 1:
                        px = ox + col * pixel
                        py = oy + row * pixel
                        canvas.create_rectangle(px, py, px + pixel, py + pixel,
                                                fill='black', outline='')

        canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _on_font_grid_click(self, event):
        """Handle click on the character grid to select a character for editing."""
        cell = 32
        col = (event.x - cell) // cell
        row = (self.font_grid_canvas.canvasy(event.y) - cell) // cell

        if 0 <= col < 16 and 0 <= row < 16:
            char_idx = int(row) * 16 + int(col)
            if 0 <= char_idx < 255:
                self.font_selected_char = char_idx
                self._refresh_font_grid()
                self._refresh_font_editor()

    def _refresh_font_editor(self):
        """Redraw the pixel editor for the selected character."""
        canvas = self.font_editor_canvas
        canvas.delete('all')
        ps = self.font_editor_pixel_size

        if self.font_selected_char is None or self.font_data is None:
            self.font_char_label.config(text="Select a character")
            return

        idx = self.font_selected_char
        char_bytes = self.font_data[idx]

        # Label
        if 32 <= idx <= 126:
            display = chr(idx)
        else:
            display = f"#{idx}"
        self.font_char_label.config(text=f"Char {idx} ({display})  —  0x{idx:02X}")

        # Draw grid with pixels
        for col in range(5):
            col_data = char_bytes[col]
            for row in range(8):
                x0 = col * ps
                y0 = row * ps
                on = (col_data >> row) & 1
                fill = 'black' if on else 'white'
                canvas.create_rectangle(x0, y0, x0 + ps, y0 + ps,
                                        fill=fill, outline='#CCCCCC')

        # Draw actual-size preview
        self._refresh_font_preview()

    def _refresh_font_preview(self):
        """Draw actual-size preview of the selected character."""
        canvas = self.font_preview_canvas
        canvas.delete('all')

        if self.font_selected_char is None or self.font_data is None:
            return

        char_bytes = self.font_data[self.font_selected_char]
        # Draw at 6x scale for visibility (30x48 pixels to show in 60x48 canvas)
        scale = 6
        ox = (60 - 5 * scale) // 2
        oy = (48 - 8 * scale) // 2
        for col in range(5):
            col_data = char_bytes[col]
            for row in range(8):
                if (col_data >> row) & 1:
                    x = ox + col * scale
                    y = oy + row * scale
                    canvas.create_rectangle(x, y, x + scale, y + scale,
                                            fill='white', outline='')

    def _on_font_pixel_click(self, event):
        """Toggle a pixel in the character editor."""
        if self.font_selected_char is None or self.font_data is None:
            return
        ps = self.font_editor_pixel_size
        col = event.x // ps
        row = event.y // ps
        if 0 <= col < 5 and 0 <= row < 8:
            char_bytes = self.font_data[self.font_selected_char]
            # Determine draw value based on current state (toggle)
            on = (char_bytes[col] >> row) & 1
            self.font_draw_value = 0 if on else 1
            if self.font_draw_value:
                char_bytes[col] |= (1 << row)
            else:
                char_bytes[col] &= ~(1 << row)
            self._refresh_font_editor()
            self._refresh_font_grid()
            self._auto_export()
            self._save_project()

    def _on_font_pixel_drag(self, event):
        """Handle drag in the character editor for continuous drawing."""
        if self.font_selected_char is None or self.font_data is None:
            return
        ps = self.font_editor_pixel_size
        col = event.x // ps
        row = event.y // ps
        if 0 <= col < 5 and 0 <= row < 8:
            char_bytes = self.font_data[self.font_selected_char]
            if self.font_draw_value:
                char_bytes[col] |= (1 << row)
            else:
                char_bytes[col] &= ~(1 << row)
            self._refresh_font_editor()
            self._refresh_font_grid()

    def _font_prev_char(self):
        """Navigate to previous character."""
        if self.font_selected_char is not None and self.font_selected_char > 0:
            self.font_selected_char -= 1
            self._refresh_font_grid()
            self._refresh_font_editor()

    def _font_next_char(self):
        """Navigate to next character."""
        if self.font_selected_char is not None and self.font_selected_char < 254:
            self.font_selected_char += 1
            self._refresh_font_grid()
            self._refresh_font_editor()

    def _font_clear_char(self):
        """Clear the selected character (all pixels off)."""
        if self.font_selected_char is not None and self.font_data is not None:
            self.font_data[self.font_selected_char] = [0, 0, 0, 0, 0]
            self._refresh_font_editor()
            self._refresh_font_grid()
            self._auto_export()
            self._save_project()

    def _font_invert_char(self):
        """Invert the selected character."""
        if self.font_selected_char is not None and self.font_data is not None:
            char_bytes = self.font_data[self.font_selected_char]
            for i in range(5):
                char_bytes[i] = (~char_bytes[i]) & 0xFF
            self._refresh_font_editor()
            self._refresh_font_grid()
            self._auto_export()
            self._save_project()

    def _import_font(self):
        """Import a TTF/OTF font and render all characters to 5x8 bitmaps."""
        file_path = filedialog.askopenfilename(
            title="Select Font File",
            filetypes=[("Font files", "*.ttf *.otf *.TTF *.OTF"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            # Try different font sizes to find best fit for 5x8
            best_size = 8
            for try_size in range(6, 16):
                font = ImageFont.truetype(file_path, try_size)
                bbox = font.getbbox("M")
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                if w <= 5 and h <= 8:
                    best_size = try_size
                else:
                    break

            font = ImageFont.truetype(file_path, best_size)

            self._init_font_data()
            # Render printable ASCII characters (32-126)
            for char_idx in range(32, 127):
                char = chr(char_idx)
                # Render character to a small image
                img = Image.new('L', (12, 16), 0)
                draw = ImageDraw.Draw(img)
                draw.text((0, 0), char, fill=255, font=font)

                # Find bounding box of the rendered character
                bbox = img.getbbox()
                if bbox is None:
                    # Empty character (e.g., space)
                    self.font_data[char_idx] = [0, 0, 0, 0, 0]
                    continue

                # Crop to content
                cropped = img.crop(bbox)
                cw, ch = cropped.size

                # Scale/fit to 5x7 (leave bottom row for descenders)
                if cw > 5 or ch > 7:
                    # Scale down to fit
                    scale = min(5 / max(cw, 1), 7 / max(ch, 1))
                    new_w = max(1, int(cw * scale))
                    new_h = max(1, int(ch * scale))
                    cropped = cropped.resize((new_w, new_h), Image.LANCZOS)
                    cw, ch = new_w, new_h

                # Center horizontally in 5 columns, top-align in 8 rows
                ox = (5 - cw) // 2
                oy = 0  # Top-aligned (descenders will naturally extend)

                # Convert to column-encoded bytes
                new_bytes = [0, 0, 0, 0, 0]
                pixels = cropped.load()
                for c in range(cw):
                    for r in range(ch):
                        target_col = ox + c
                        target_row = oy + r
                        if 0 <= target_col < 5 and 0 <= target_row < 8:
                            if pixels[c, r] > 127:  # Threshold
                                new_bytes[target_col] |= (1 << target_row)

                self.font_data[char_idx] = new_bytes

            self.font_path = file_path
            font_name = os.path.basename(file_path)
            self.font_info_label.config(text=f"Font: {font_name} (5x8)")

            self._refresh_font_grid()
            if self.font_selected_char is not None:
                self._refresh_font_editor()
            self._auto_export()
            self._save_project()

        except Exception as e:
            messagebox.showerror("Font Import Error", f"Failed to import font: {e}")

    def _reset_font_to_default(self):
        """Reset font data to the default ASCII font."""
        self.font_data = self._get_default_font_data()
        self.font_path = None
        self.font_info_label.config(text="Font: default (5x8)")
        self._refresh_font_grid()
        if self.font_selected_char is not None:
            self._refresh_font_editor()
        self._auto_export()
        self._save_project()

    def _generate_font_h(self):
        """Generate font.h content from font_data."""
        self._init_font_data()

        # Character name table for comments
        char_names = {}
        char_names[0] = 'NUL'
        char_names[1] = 'SOH'
        char_names[2] = 'STX'
        char_names[3] = 'ETX'
        char_names[4] = 'EOT'
        char_names[5] = 'ENQ'
        char_names[6] = 'ACK'
        char_names[7] = 'BEL'
        char_names[8] = 'BS'
        char_names[9] = 'TAB'
        char_names[10] = 'LF'
        char_names[11] = 'VT'
        char_names[12] = 'FF'
        char_names[13] = 'CR'
        char_names[14] = 'SO'
        char_names[15] = 'SI'
        char_names[16] = 'DLE'
        char_names[17] = 'DC1'
        char_names[18] = 'DC2'
        char_names[19] = 'DC3'
        char_names[20] = 'DC4'
        char_names[21] = 'NAK'
        char_names[22] = 'SYN'
        char_names[23] = 'ETB'
        char_names[24] = 'CAN'
        char_names[25] = 'EM'
        char_names[26] = 'SUB'
        char_names[27] = 'ESC'
        char_names[28] = 'FS'
        char_names[29] = 'GS'
        char_names[30] = 'RS'
        char_names[31] = 'US'
        char_names[32] = 'SP'
        char_names[127] = 'DEL'

        lines = [
            "#ifndef _FONT_H_",
            "#define _FONT_H_",
            "",
            "#include <stdint.h>",
            "",
            "#define FONT_WIDTH 5",
            "#define FONT_HEIGHT 8",
            "#define FONT_BYTES_PER_CHAR 5",
            "#define FONT_SPACE 1 // Space between characters",
            "",
            "// 5x8 font - Generated by RayCast3D Studio",
            "static const uint8_t Font[] = {",
        ]

        for i in range(255):
            b = self.font_data[i]
            hex_vals = ', '.join(f'0x{v:02X}' for v in b)

            # Build comment
            if i in char_names:
                comment = f"{char_names[i]:3s} char = {i:3d}"
            elif 33 <= i <= 126:
                comment = f"{chr(i):3s} char = {i:3d}"
            else:
                comment = f"char = {i:3d}"

            lines.append(f"  {hex_vals},  // {comment}")

        lines.append("")
        lines.append("};")
        lines.append("")
        lines.append("#endif")

        return "\n".join(lines)

    def _refresh_color_list(self):
        """Refresh the color list display."""
        # Clear existing rows
        for widget in self.color_list_frame.winfo_children():
            widget.destroy()
        self.color_rows = []
        self.selected_color_rows = set()
        self.last_color_click = None

        for i, color in enumerate(self.colors):
            # Name label
            name_label = ttk.Label(self.color_list_frame, text=color.name, anchor='w')
            name_label.grid(row=i, column=0, sticky='w', padx=5, pady=1)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))
            name_label.bind('<Double-Button-1>', lambda e, idx=i: self._edit_color_at(idx))

            # Color swatch (using a small canvas)
            swatch = tk.Canvas(self.color_list_frame, width=40, height=20, highlightthickness=1, highlightbackground='gray')
            swatch.create_rectangle(0, 0, 40, 20, fill=color.to_hex_string(), outline='')
            swatch.grid(row=i, column=1, sticky='w', padx=5, pady=1)
            swatch.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))
            swatch.bind('<Double-Button-1>', lambda e, idx=i: self._edit_color_at(idx))

            # BGR565 value
            bgr565_label = ttk.Label(self.color_list_frame, text=f"0x{color.to_bgr565():04X}", anchor='w', font=('Consolas', 9))
            bgr565_label.grid(row=i, column=2, sticky='w', padx=5, pady=1)
            bgr565_label.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))

            # RGB values
            rgb_label = ttk.Label(self.color_list_frame, text=f"({color.r}, {color.g}, {color.b})", anchor='w')
            rgb_label.grid(row=i, column=3, sticky='w', padx=5, pady=1)
            rgb_label.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))

            self.color_rows.append((name_label, swatch, bgr565_label, rgb_label))

    def _deselect_all_colors(self):
        """Deselect all color rows."""
        for idx in list(self.selected_color_rows):
            if idx < len(self.color_rows):
                name_label, _, bgr565_label, rgb_label = self.color_rows[idx]
                name_label.configure(background='')
                bgr565_label.configure(background='')
                rgb_label.configure(background='')
        self.selected_color_rows = set()
        self.last_color_click = None

    def _update_color_highlights(self):
        """Update visual highlighting for all color rows based on selection."""
        for idx, row_data in enumerate(self.color_rows):
            name_label, _, bgr565_label, rgb_label = row_data
            bg = '#cce5ff' if idx in self.selected_color_rows else ''
            name_label.configure(background=bg)
            bgr565_label.configure(background=bg)
            rgb_label.configure(background=bg)

    def _select_color_row(self, idx, event=None):
        """Select a color row with multi-select support.

        - Normal click: Select only this row
        - Ctrl+Click: Toggle this row in selection
        - Shift+Click: Select range from last click to this row
        """
        ctrl_held = event and (event.state & 0x4)  # Control key
        shift_held = event and (event.state & 0x1)  # Shift key

        if ctrl_held:
            # Toggle this row in selection
            if idx in self.selected_color_rows:
                self.selected_color_rows.discard(idx)
            else:
                self.selected_color_rows.add(idx)
            self.last_color_click = idx
        elif shift_held and self.last_color_click is not None:
            # Select range from last click to current
            start = min(self.last_color_click, idx)
            end = max(self.last_color_click, idx)
            self.selected_color_rows = set(range(start, end + 1))
        else:
            # Normal click - select only this row (or deselect if already only selection)
            if self.selected_color_rows == {idx}:
                self.selected_color_rows = set()
                self.last_color_click = None
            else:
                self.selected_color_rows = {idx}
                self.last_color_click = idx

        self._update_color_highlights()

    def _add_color(self):
        """Add a new color using the color picker."""
        # Open color chooser
        result = colorchooser.askcolor(title="Choose a Color")
        if result[0] is None:
            return

        rgb = result[0]  # (r, g, b) tuple
        r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])

        # Ask for name
        name = simpledialog.askstring("Color Name", "Enter a name for this color:")
        if not name:
            return

        # Clean name for C constant (uppercase with underscores)
        name = ''.join(c.upper() if c.isalnum() else '_' for c in name)
        if not name[0].isalpha():
            name = 'COLOR_' + name

        # Check for duplicate
        if any(c.name == name for c in self.colors):
            messagebox.showerror("Error", f"Color '{name}' already exists.")
            return

        color = Color(name, r, g, b)
        self.colors.append(color)

        self._refresh_color_list()
        self._auto_export()
        self._save_project()

    def _edit_color(self):
        """Edit the selected color (edits last clicked if multiple selected)."""
        if not self.selected_color_rows or self.last_color_click is None:
            messagebox.showinfo("Info", "Please select a color to edit.")
            return
        self._edit_color_at(self.last_color_click)

    def _edit_color_at(self, idx):
        """Edit color at the given index."""
        if idx >= len(self.colors):
            return

        color = self.colors[idx]

        # Open color chooser with current color
        result = colorchooser.askcolor(
            initialcolor=color.to_hex_string(),
            title=f"Edit Color: {color.name}"
        )
        if result[0] is None:
            return

        rgb = result[0]
        color.r, color.g, color.b = int(rgb[0]), int(rgb[1]), int(rgb[2])

        self._refresh_color_list()
        self._auto_export()
        self._save_project()

    def _rename_color(self):
        """Rename the selected color."""
        if not self.selected_color_rows or self.last_color_click is None:
            messagebox.showinfo("Info", "Please select a color to rename.")
            return

        idx = self.last_color_click
        if idx >= len(self.colors):
            return

        color = self.colors[idx]
        old_name = color.name

        new_name = simpledialog.askstring("Rename Color", "Enter new name:", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return

        # Clean name for C variable
        new_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in new_name)

        # Check for duplicate
        if any(c.name == new_name for c in self.colors):
            messagebox.showerror("Error", f"Color '{new_name}' already exists.")
            return

        color.name = new_name
        self._refresh_color_list()
        self._auto_export()
        self._save_project()

    def _remove_colors(self):
        """Remove all selected colors (supports multi-select)."""
        if not self.selected_color_rows:
            return

        # Sort indices in reverse order to delete from end first
        indices_to_remove = sorted(self.selected_color_rows, reverse=True)

        for idx in indices_to_remove:
            if idx < len(self.colors):
                del self.colors[idx]

        self.selected_color_rows = set()
        self.last_color_click = None
        self._refresh_color_list()
        self._auto_export()
        self._save_project()

    def _is_perimeter(self, row, col):
        """Check if a cell is on the perimeter."""
        return row == 0 or row == MAP_SIZE-1 or col == 0 or col == MAP_SIZE-1

    def _draw_map_grid(self):
        """Draw the map grid on canvas with actual texture images."""
        self.map_canvas.delete('all')
        self.tile_images = {}  # Clear image references

        # Offset for coordinate labels
        offset = LABEL_MARGIN

        for row in range(MAP_SIZE):
            for col in range(MAP_SIZE):
                x1 = col * CELL_SIZE + offset
                y1 = row * CELL_SIZE + offset
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE

                val = self.map_data[row][col]

                if val == 0:
                    # Empty cell - black
                    self.map_canvas.create_rectangle(x1, y1, x2, y2, fill='black', outline='#333333')
                elif val > 0 and val <= len(self.textures):
                    # Has texture - draw the texture tile
                    tex = self.textures[val - 1]
                    if tex.tile_preview:
                        self.map_canvas.create_image(x1, y1, anchor='nw', image=tex.tile_preview)
                        self.tile_images[(row, col)] = tex.tile_preview  # Keep reference
                    else:
                        # Fallback if no preview
                        self.map_canvas.create_rectangle(x1, y1, x2, y2, fill='#666666', outline='#333333')
                else:
                    # Wall with no texture defined yet - gray placeholder
                    self.map_canvas.create_rectangle(x1, y1, x2, y2, fill='#444444', outline='#333333')

        # Grid lines
        for i in range(1, MAP_SIZE):
            self.map_canvas.create_line(i * CELL_SIZE + offset, offset,
                                        i * CELL_SIZE + offset, MAP_SIZE * CELL_SIZE + offset, fill='#333333')
            self.map_canvas.create_line(offset, i * CELL_SIZE + offset,
                                        MAP_SIZE * CELL_SIZE + offset, i * CELL_SIZE + offset, fill='#333333')

        # Coordinate labels on grid lines (0-indexed)
        for i in range(1, MAP_SIZE):
            # X-axis labels (top)
            x_pos = i * CELL_SIZE + offset
            self.map_canvas.create_text(x_pos, offset - 4, text=str(i),
                                        fill='black', font=('Arial', 7), anchor='s')
            # Y-axis labels (left)
            y_pos = i * CELL_SIZE + offset
            self.map_canvas.create_text(offset - 4, y_pos, text=str(i),
                                        fill='black', font=('Arial', 7), anchor='e')

    def _on_map_click(self, event):
        """Handle map click."""
        self.is_drawing = True

        # Save current map state for undo before painting
        self.map_undo_stack.append((self.current_map_idx, [row[:] for row in self.map_data]))
        if len(self.map_undo_stack) > 50:
            self.map_undo_stack.pop(0)

        # Check if clicking a cell with the same texture - if so, enter erase mode
        col = (event.x - LABEL_MARGIN) // CELL_SIZE
        row = (event.y - LABEL_MARGIN) // CELL_SIZE
        if 0 <= row < MAP_SIZE and 0 <= col < MAP_SIZE:
            current_value = self.map_data[row][col]
            is_perimeter = self._is_perimeter(row, col)
            
            # If clicking same texture on interior cell, enter erase mode
            if current_value == self.selected_texture_idx and not is_perimeter:
                self.is_erasing = True
            else:
                self.is_erasing = False
        
        self._paint_cell(event)

    def _on_map_drag(self, event):
        """Handle map drag."""
        if self.is_drawing:
            self._paint_cell(event)

    def _on_map_release(self, event):
        """Handle mouse release."""
        self.is_drawing = False
        self.is_erasing = False  # Reset erase mode
        # Auto-export and save on release
        self._auto_export()
        self._save_project()

    def _undo(self):
        """Undo the last map paint operation."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 0:  # Map tab
            if self.map_undo_stack:
                map_idx, data = self.map_undo_stack.pop()
                self.maps[map_idx]["data"] = data
                if self.current_map_idx == map_idx:
                    self._draw_map_grid()
                self._auto_export()
                self._save_project()

    def _on_map_selected(self, event=None):
        """Handle map selection from dropdown."""
        selected_name = self.map_selector_var.get()
        for i, m in enumerate(self.maps):
            if m["name"] == selected_name:
                self.current_map_idx = i
                self._draw_map_grid()
                if hasattr(self, 'floor_tex_combo'):
                    self._update_floor_texture_combo()
                if hasattr(self, 'ceil_tex_combo'):
                    self._update_ceil_texture_combo()
                break

    def _add_map(self):
        """Add a new map."""
        # Generate unique name
        base_name = "map"
        counter = len(self.maps) + 1
        while any(m["name"] == f"{base_name}{counter}" for m in self.maps):
            counter += 1
        new_name = f"{base_name}{counter}"

        name = simpledialog.askstring("New Map", "Enter map name:", initialvalue=new_name)
        if not name:
            return

        # Clean name for C variable
        name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)

        # Check for duplicate
        if any(m["name"] == name for m in self.maps):
            messagebox.showerror("Error", f"Map '{name}' already exists.")
            return

        # Create new map with perimeter
        new_map = {"name": name, "data": [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]}
        self.maps.append(new_map)
        self.current_map_idx = len(self.maps) - 1
        self._init_perimeter()

        self._update_map_selector()
        self._draw_map_grid()
        self._auto_export()
        self._save_project()

    def _rename_map(self):
        """Rename the current map."""
        old_name = self.maps[self.current_map_idx]["name"]
        new_name = simpledialog.askstring("Rename Map", "Enter new name:", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return

        # Clean name for C variable
        new_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in new_name)

        # Check for duplicate
        if any(m["name"] == new_name for m in self.maps):
            messagebox.showerror("Error", f"Map '{new_name}' already exists.")
            return

        self.maps[self.current_map_idx]["name"] = new_name
        self._update_map_selector()
        self._auto_export()
        self._save_project()

    def _delete_map(self):
        """Delete the current map."""
        if len(self.maps) <= 1:
            messagebox.showwarning("Cannot Delete", "At least one map must exist.")
            return

        name = self.maps[self.current_map_idx]["name"]
        if not messagebox.askyesno("Delete Map", f"Delete map '{name}'?"):
            return

        del self.maps[self.current_map_idx]
        self.current_map_idx = min(self.current_map_idx, len(self.maps) - 1)

        self._update_map_selector()
        self._draw_map_grid()
        self._auto_export()
        self._save_project()

    def _update_map_selector(self):
        """Update the map selector dropdown."""
        self.map_selector['values'] = [m["name"] for m in self.maps]
        self.map_selector_var.set(self.maps[self.current_map_idx]["name"])
        self.map_count_label.config(text=f"({len(self.maps)} map(s))")

    def _paint_cell(self, event):
        """Paint a cell at mouse position."""
        col = (event.x - LABEL_MARGIN) // CELL_SIZE
        row = (event.y - LABEL_MARGIN) // CELL_SIZE

        if 0 <= row < MAP_SIZE and 0 <= col < MAP_SIZE:
            is_perimeter = self._is_perimeter(row, col)

            # If in erase mode, erase the cell (but not perimeter)
            if self.is_erasing:
                if not is_perimeter:
                    self.map_data[row][col] = 0  # Erase
                    self._draw_map_grid()
                return

            # Normal painting mode
            # Perimeter cells can't be erased (must have texture >= 1)
            if is_perimeter and self.selected_texture_idx == 0:
                return  # Can't erase perimeter

            # Perimeter must have a valid texture
            if is_perimeter and self.selected_texture_idx > len(self.textures):
                return  # No valid texture selected

            self.map_data[row][col] = self.selected_texture_idx
            self._draw_map_grid()

    def _select_texture(self, idx):
        """Select a texture for painting."""
        self.selected_texture_idx = idx
        if idx == 0:
            self.selected_label.config(text="Selected: Erase")
            self.selected_preview_label.config(image='')
        else:
            if idx <= len(self.textures):
                tex = self.textures[idx-1]
                self.selected_label.config(text=f"Selected: {tex.name}")
                if tex.tile_preview:
                    self.selected_preview_label.config(image=tex.tile_preview)
            else:
                self.selected_label.config(text=f"Selected: Texture {idx}")
                self.selected_preview_label.config(image='')

    def _update_texture_palette(self):
        """Update the texture palette in map tab."""
        for widget in self.palette_inner.winfo_children():
            widget.destroy()

        for i, tex in enumerate(self.textures):
            idx = i + 1
            frame = ttk.Frame(self.palette_inner)
            frame.pack(fill='x', pady=2)

            # Show texture name with small preview
            btn = ttk.Button(frame, text=tex.name,
                            command=lambda i=idx: self._select_texture(i))
            btn.pack(fill='x')

        # Also refresh the floor/ceiling texture dropdowns
        if hasattr(self, 'floor_tex_combo'):
            self._update_floor_texture_combo()
        if hasattr(self, 'ceil_tex_combo'):
            self._update_ceil_texture_combo()

    def _create_texture_previews(self, tex):
        """Create both large preview (simulating in-game wall) and tile preview for a texture."""
        try:
            img = Image.open(tex.image_path)

            # First resize to target resolution (this is what goes in-game)
            processed = resize_and_letterbox(img, tex.resolution, tex.resolution)
            tex.pil_image = processed

            # Create simulated wall view preview
            tex.preview = self._create_wall_preview(processed, tex.resolution)

            # Tile preview: scale to cell size with NEAREST
            tile = processed.resize((CELL_SIZE, CELL_SIZE), Image.NEAREST)
            tex.tile_preview = ImageTk.PhotoImage(tile)

            # Regenerate C array
            tex.c_array = image_to_bgr565_array(img, tex.resolution)
        except Exception as e:
            print(f"Error creating previews for {tex.name}: {e}")

    def _create_wall_preview(self, texture_img, tex_resolution):
        """
        Create a SQUARE preview that simulates how the texture looks on a wall in-game.

        Accurately shows horizontal banding artifacts caused by the raycaster's
        integer division when vertically stretching textures to fill wall height.

        The banding occurs because when a 32x32 texture is stretched to ~120 pixels,
        some texture rows are displayed more times than others due to integer math:
        tex_y = (screen_y * tex_resolution) // wall_height

        This creates visible horizontal bands where rows "bunch up".
        """
        # Use a square preview for accurate representation
        preview_size = 128  # Square preview

        # Simulate typical wall rendering: texture stretched to ~120 pixels on 160px screen
        simulated_wall_height = 120

        # Create preview image
        preview = Image.new("RGB", (preview_size, preview_size), (0, 0, 0))
        preview_pixels = preview.load()

        texture_pixels = texture_img.convert("RGB").load()

        # For each preview pixel, simulate the double-sampling that creates banding:
        # 1. First, simulate stretching: map preview_y -> simulated wall position
        # 2. Then, simulate raycaster sampling: wall position -> texture coordinate

        for x in range(preview_size):
            # Map preview x to texture x (simple scaling)
            tex_x = (x * tex_resolution) // preview_size
            tex_x = min(tex_x, tex_resolution - 1)

            for y in range(preview_size):
                # Step 1: Map preview coordinate to simulated wall position
                # (scale preview down to simulated wall height proportionally)
                wall_y = (y * simulated_wall_height) // preview_size

                # Step 2: Simulate raycaster's integer division sampling
                # This is where banding originates - integer division causes
                # some texture rows to be selected multiple times
                tex_y = (wall_y * tex_resolution) // simulated_wall_height
                tex_y = min(tex_y, tex_resolution - 1)

                preview_pixels[x, y] = texture_pixels[tex_x, tex_y]

        return ImageTk.PhotoImage(preview)

    def _refresh_texture_list(self):
        """Refresh the texture list with inline dropdown."""
        # Clear existing rows
        for widget in self.texture_list_frame.winfo_children():
            widget.destroy()
        self.texture_rows = []
        self.selected_texture_rows = set()
        self.last_texture_click = None

        for i, tex in enumerate(self.textures):
            # Name label
            name_label = ttk.Label(self.texture_list_frame, text=tex.name, anchor='w')
            name_label.grid(row=i, column=0, sticky='w', padx=5, pady=1)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx, e))

            # Resolution dropdown (always visible)
            res_var = tk.StringVar(value=str(tex.resolution))
            res_combo = ttk.Combobox(self.texture_list_frame, textvariable=res_var, values=["16", "32", "64", "128"],
                                     width=7, state='readonly')
            res_combo.grid(row=i, column=1, sticky='w', padx=5, pady=1)
            res_combo.bind('<<ComboboxSelected>>', lambda e, idx=i, var=res_var: self._on_texture_resolution_change(idx, var))

            # Memory label
            mem_label = ttk.Label(self.texture_list_frame, text=f"{tex.memory_bytes()} bytes", anchor='w')
            mem_label.grid(row=i, column=2, sticky='w', padx=5, pady=1)
            mem_label.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx, e))

            self.texture_rows.append((name_label, res_var, res_combo, mem_label))

    def _deselect_all_textures(self):
        """Deselect all texture rows."""
        for idx in list(self.selected_texture_rows):
            if idx < len(self.texture_rows):
                name_label, _, _, mem_label = self.texture_rows[idx]
                name_label.configure(background='')
                mem_label.configure(background='')
        self.selected_texture_rows = set()
        self.last_texture_click = None
        self.tex_preview_label.config(image='')
        self.tex_preview_info.config(text='Select a texture to see preview')

    def _update_texture_highlights(self):
        """Update visual highlighting for all texture rows based on selection."""
        for idx, row_data in enumerate(self.texture_rows):
            name_label, _, _, mem_label = row_data
            bg = '#cce5ff' if idx in self.selected_texture_rows else ''
            name_label.configure(background=bg)
            mem_label.configure(background=bg)

    def _select_texture_row(self, idx, event=None):
        """Select a texture row with multi-select support.

        - Normal click: Select only this row
        - Ctrl+Click: Toggle this row in selection
        - Shift+Click: Select range from last click to this row
        """
        ctrl_held = event and (event.state & 0x4)  # Control key
        shift_held = event and (event.state & 0x1)  # Shift key

        if ctrl_held:
            # Toggle this row in selection
            if idx in self.selected_texture_rows:
                self.selected_texture_rows.discard(idx)
            else:
                self.selected_texture_rows.add(idx)
            self.last_texture_click = idx
        elif shift_held and self.last_texture_click is not None:
            # Select range from last click to current
            start = min(self.last_texture_click, idx)
            end = max(self.last_texture_click, idx)
            self.selected_texture_rows = set(range(start, end + 1))
        else:
            # Normal click - select only this row (or deselect if already only selection)
            if self.selected_texture_rows == {idx}:
                self.selected_texture_rows = set()
                self.last_texture_click = None
            else:
                self.selected_texture_rows = {idx}
                self.last_texture_click = idx

        self._update_texture_highlights()

        # Show preview for last clicked item
        if self.last_texture_click is not None and self.last_texture_click < len(self.textures):
            tex = self.textures[self.last_texture_click]
            if tex.preview:
                self.tex_preview_label.config(image=tex.preview)
            count = len(self.selected_texture_rows)
            if count > 1:
                self.tex_preview_info.config(text=f"{count} textures selected\n\n"
                                                  f"Showing: {tex.name}\n"
                                                  f"Resolution: {tex.resolution}x{tex.resolution}")
            else:
                self.tex_preview_info.config(text=f"Resolution: {tex.resolution}x{tex.resolution}\n"
                                                  f"Memory: {tex.memory_bytes()} bytes")
        elif not self.selected_texture_rows:
            self.tex_preview_label.config(image='')
            self.tex_preview_info.config(text='Select a texture to see preview')

    def _on_texture_resolution_change(self, idx, var):
        """Handle texture resolution dropdown change."""
        if idx >= len(self.textures):
            return

        try:
            new_res = int(var.get())
            tex = self.textures[idx]

            if new_res != tex.resolution:
                self._update_texture_resolution(tex, new_res)
                self._refresh_texture_list()
                # Reselect the row
                self._select_texture_row(idx)
        except ValueError:
            pass

    def _update_texture_resolution(self, tex, new_res):
        """Update a texture's resolution."""
        if not os.path.exists(tex.image_path):
            messagebox.showerror("Error", f"Image file not found: {tex.image_path}")
            return

        try:
            img = Image.open(tex.image_path)
            tex.resolution = new_res
            tex.c_array = image_to_bgr565_array(img, new_res)
            self._create_texture_previews(tex)
            self._update_texture_palette()
            self._draw_map_grid()
            self._update_memory_display()
            self._auto_export()
            self._save_project()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update resolution: {e}")

    def _add_texture(self):
        """Add a new texture."""
        file_path = _native_open_file_dialog(
            title="Select Texture Image",
            filetypes=[("Image files", "*.png *.PNG *.bmp *.BMP *.jpg *.JPG *.jpeg *.JPEG"), ("All files", "*.*")]
        )

        if not file_path:
            return

        # Get name
        default_name = os.path.splitext(os.path.basename(file_path))[0]
        name = simpledialog.askstring("Texture Name", "Enter texture name:", initialvalue=default_name)
        if not name:
            return

        # Clean name for C variable
        name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)

        # Check for duplicate name and ask to overwrite
        existing_idx = None
        for i, t in enumerate(self.textures):
            if t.name == name:
                existing_idx = i
                break
        if existing_idx is not None:
            if not messagebox.askyesno("Duplicate Texture",
                    f"A texture named \"{name}\" already exists. Overwrite it?"):
                return

        try:
            resolution = int(self.tex_res_var.get())
            img = Image.open(file_path)
            c_array = image_to_bgr565_array(img, resolution)

            tex = Texture(name, file_path, resolution, c_array)

            if existing_idx is not None:
                # Overwrite in place, preserving index
                tex.index = self.textures[existing_idx].index
                self.textures[existing_idx] = tex
            else:
                tex.index = len(self.textures) + 1
                self.textures.append(tex)

            # Create previews (pixelated)
            self._create_texture_previews(tex)

            self._refresh_texture_list()
            self._update_texture_palette()
            self._draw_map_grid()
            self._update_memory_display()
            self._auto_export()
            self._save_project()

            # Select the texture
            select_idx = existing_idx if existing_idx is not None else len(self.textures) - 1
            self._select_texture_row(select_idx)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load texture: {e}")

    def _remove_textures(self):
        """Remove all selected textures (supports multi-select)."""
        if not self.selected_texture_rows:
            return

        # Check if we'd be removing all textures (perimeter needs at least one)
        remaining = len(self.textures) - len(self.selected_texture_rows)
        if remaining < 1:
            messagebox.showwarning("Cannot Remove", "Cannot remove all textures - perimeter walls need at least one texture.")
            return

        # Sort indices in reverse order to delete from end first (preserves earlier indices)
        indices_to_remove = sorted(self.selected_texture_rows, reverse=True)

        # Remove textures and update map cells
        for idx in indices_to_remove:
            if idx >= len(self.textures):
                continue

            removed_tex_num = idx + 1  # 1-based texture number in map

            del self.textures[idx]

            # Update map cells: shift texture references down
            for row in range(MAP_SIZE):
                for col in range(MAP_SIZE):
                    cell_val = self.map_data[row][col]
                    if cell_val == removed_tex_num:
                        # This cell used the removed texture
                        if self._is_perimeter(row, col):
                            self.map_data[row][col] = 1  # Reset to texture 1
                        else:
                            self.map_data[row][col] = 0  # Erase
                    elif cell_val > removed_tex_num:
                        # Shift down
                        self.map_data[row][col] = cell_val - 1

        # Update texture indices
        for i, tex in enumerate(self.textures):
            tex.index = i + 1

        self.selected_texture_rows = set()
        self.last_texture_click = None
        self._refresh_texture_list()
        self._update_texture_palette()
        self._draw_map_grid()
        self._update_memory_display()
        self._auto_export()
        self._save_project()

        # Clear preview
        self.tex_preview_label.config(image='')
        self.tex_preview_info.config(text='')

    def _rename_texture(self):
        """Rename the selected texture."""
        if not self.selected_texture_rows or self.last_texture_click is None:
            messagebox.showinfo("Info", "Please select a texture to rename.")
            return

        idx = self.last_texture_click
        if idx >= len(self.textures):
            return

        texture = self.textures[idx]
        old_name = texture.name

        new_name = simpledialog.askstring("Rename Texture", "Enter new name:", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return

        # Clean name for C variable
        new_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in new_name)

        # Check for duplicate
        if any(t.name == new_name for t in self.textures):
            messagebox.showerror("Error", f"Texture '{new_name}' already exists.")
            return

        texture.name = new_name
        self._refresh_texture_list()
        self._update_texture_palette()
        self._auto_export()
        self._save_project()

    def _detect_transparent_color(self, img, width, height):
        """
        Detect the transparent color from an image.
        - If image has alpha channel: use black (0x0000) for transparent pixels
        - If no alpha: use top-left corner pixel as transparent color
        Returns: (transparent_color_bgr565, processed_rgb_image)
        """
        img_resized = resize_and_letterbox(img, width, height)

        # Check if image has alpha channel
        if img_resized.mode == 'RGBA' or 'A' in img_resized.getbands():
            img_rgba = img_resized.convert("RGBA")
            pixels_rgba = img_rgba.load()

            # Check if there are any transparent pixels
            has_transparency = False
            for y in range(height):
                for x in range(width):
                    if pixels_rgba[x, y][3] < 128:  # Alpha < 50%
                        has_transparency = True
                        break
                if has_transparency:
                    break

            if has_transparency:
                # Replace transparent pixels with black, use black as transparent key
                img_rgb = Image.new("RGB", (width, height), (0, 0, 0))
                for y in range(height):
                    for x in range(width):
                        r, g, b, a = pixels_rgba[x, y]
                        if a >= 128:
                            img_rgb.putpixel((x, y), (r, g, b))
                        # else leave as black (transparent)
                return 0x0000, img_rgb  # Black is transparent

        # No alpha or no transparent pixels - use top-left corner as transparent
        img_rgb = img_resized.convert("RGB")
        pixels = img_rgb.load()
        r, g, b = pixels[0, 0]  # Top-left corner
        blue5 = b >> 3
        green6 = g >> 2
        red5 = r >> 3
        transparent = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)

        return transparent, img_rgb

    def _refresh_sprite_list(self):
        """Refresh the sprite list with inline dropdown."""
        # Clear existing rows
        for widget in self.sprite_list_frame.winfo_children():
            widget.destroy()
        self.sprite_rows = []
        self.selected_sprite_rows = set()
        self.last_sprite_click = None

        for i, sprite in enumerate(self.sprites):
            # Name label
            name_label = ttk.Label(self.sprite_list_frame, text=sprite.name, anchor='w')
            name_label.grid(row=i, column=0, sticky='w', padx=5, pady=1)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx, e))

            # Resolution dropdown (always visible)
            res_var = tk.StringVar(value=str(sprite.resolution))
            res_combo = ttk.Combobox(self.sprite_list_frame, textvariable=res_var, values=["16", "32", "64", "128"],
                                     width=7, state='readonly')
            res_combo.grid(row=i, column=1, sticky='w', padx=5, pady=1)
            res_combo.bind('<<ComboboxSelected>>', lambda e, idx=i, var=res_var: self._on_sprite_resolution_change(idx, var))

            # Memory label
            mem_label = ttk.Label(self.sprite_list_frame, text=f"{sprite.memory_bytes()} bytes", anchor='w')
            mem_label.grid(row=i, column=2, sticky='w', padx=5, pady=1)
            mem_label.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx, e))

            self.sprite_rows.append((name_label, res_var, res_combo, mem_label))

    def _deselect_all_sprites(self):
        """Deselect all sprite rows."""
        for idx in list(self.selected_sprite_rows):
            if idx < len(self.sprite_rows):
                name_label, _, _, mem_label = self.sprite_rows[idx]
                name_label.configure(background='')
                mem_label.configure(background='')
        self.selected_sprite_rows = set()
        self.last_sprite_click = None
        self.sprite_preview_label.config(image='')
        self.sprite_preview_info.config(text='Select a sprite to see preview')

    def _update_sprite_highlights(self):
        """Update visual highlighting for all sprite rows based on selection."""
        for idx, row_data in enumerate(self.sprite_rows):
            name_label, _, _, mem_label = row_data
            bg = '#cce5ff' if idx in self.selected_sprite_rows else ''
            name_label.configure(background=bg)
            mem_label.configure(background=bg)

    def _select_sprite_row(self, idx, event=None):
        """Select a sprite row with multi-select support.

        - Normal click: Select only this row
        - Ctrl+Click: Toggle this row in selection
        - Shift+Click: Select range from last click to this row
        """
        ctrl_held = event and (event.state & 0x4)  # Control key
        shift_held = event and (event.state & 0x1)  # Shift key

        if ctrl_held:
            # Toggle this row in selection
            if idx in self.selected_sprite_rows:
                self.selected_sprite_rows.discard(idx)
            else:
                self.selected_sprite_rows.add(idx)
            self.last_sprite_click = idx
        elif shift_held and self.last_sprite_click is not None:
            # Select range from last click to current
            start = min(self.last_sprite_click, idx)
            end = max(self.last_sprite_click, idx)
            self.selected_sprite_rows = set(range(start, end + 1))
        else:
            # Normal click - select only this row (or deselect if already only selection)
            if self.selected_sprite_rows == {idx}:
                self.selected_sprite_rows = set()
                self.last_sprite_click = None
            else:
                self.selected_sprite_rows = {idx}
                self.last_sprite_click = idx

        self._update_sprite_highlights()

        # Show preview for last clicked item
        if self.last_sprite_click is not None and self.last_sprite_click < len(self.sprites):
            sprite = self.sprites[self.last_sprite_click]
            if sprite.preview:
                self.sprite_preview_label.config(image=sprite.preview)
            count = len(self.selected_sprite_rows)
            if count > 1:
                self.sprite_preview_info.config(text=f"{count} sprites selected\n\n"
                                                     f"Showing: {sprite.name}\n"
                                                     f"Resolution: {sprite.resolution}x{sprite.resolution}")
                self.edit_sprite_btn.config(state='disabled')
            else:
                self.sprite_preview_info.config(text=f"Resolution: {sprite.resolution}x{sprite.resolution}\n"
                                                     f"Memory: {sprite.memory_bytes()} bytes\n"
                                                     f"Transparent: 0x{sprite.transparent:04X}\n\n"
                                                     f"Preview shows sprite at\n"
                                                     f"simulated in-game scale\n"
                                                     f"with transparency.")
                self.edit_sprite_btn.config(state='normal')
        elif not self.selected_sprite_rows:
            self.sprite_preview_label.config(image='')
            self.sprite_preview_info.config(text='Select a sprite to see preview')
            self.edit_sprite_btn.config(state='disabled')

    def _on_sprite_resolution_change(self, idx, var):
        """Handle sprite resolution dropdown change."""
        if idx >= len(self.sprites):
            return

        try:
            new_res = int(var.get())
            sprite = self.sprites[idx]

            if new_res != sprite.resolution:
                if not os.path.exists(sprite.image_path):
                    if not messagebox.askyesno("Missing Source Image",
                            f"The original image file could not be found:\n{sprite.image_path}\n\n"
                            "The sprite will be resampled from its current low-resolution data, "
                            "which may result in a loss of quality. Continue?"):
                        var.set(str(sprite.resolution))  # Revert dropdown
                        return
                self._update_sprite_resolution(sprite, new_res)
                self._refresh_sprite_list()
                # Reselect the row
                self._select_sprite_row(idx)
        except ValueError:
            pass

    def _update_sprite_resolution(self, sprite, new_res):
        """Update a sprite's resolution. Reloads from original file, re-applying crop if set.
        Falls back to resampling from c_array if the source file is missing."""
        old_res = sprite.resolution
        try:
            if os.path.exists(sprite.image_path):
                img = Image.open(sprite.image_path)

                # Re-apply saved crop bounds if present
                if sprite.crop_bounds is not None:
                    x1, y1, x2, y2 = sprite.crop_bounds
                    img = img.crop((x1, y1, x2, y2))

                transparent, img_rgb = self._detect_transparent_color(img, new_res, new_res)
            elif sprite.c_array and len(sprite.c_array) == old_res * old_res:
                # Fallback: resample from current pixel data
                current_img = Image.new("RGB", (old_res, old_res))
                px = current_img.load()
                for i, hex_val in enumerate(sprite.c_array):
                    bgr565 = int(hex_val, 16)
                    blue5 = (bgr565 >> 11) & 0x1F
                    green6 = (bgr565 >> 5) & 0x3F
                    red5 = bgr565 & 0x1F
                    r = (red5 << 3) | (red5 >> 2)
                    g = (green6 << 2) | (green6 >> 4)
                    b = (blue5 << 3) | (blue5 >> 2)
                    px[i % old_res, i // old_res] = (r, g, b)
                img_rgb = resize_and_letterbox(current_img, new_res, new_res)
                transparent = sprite.transparent
            else:
                messagebox.showerror("Error", f"Image file not found and no pixel data available.")
                return

            pixels = img_rgb.load()

            c_vals = []
            for y in range(new_res):
                for x in range(new_res):
                    r, g, b = pixels[x, y]
                    blue5 = b >> 3
                    green6 = g >> 2
                    red5 = r >> 3
                    color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
                    c_vals.append(f"0x{color:04X}")

            sprite.resolution = new_res
            sprite.c_array = c_vals
            sprite.transparent = transparent
            sprite.preview = self._create_sprite_preview(img_rgb, new_res, new_res, transparent)

            self._update_memory_display()
            self._auto_export()
            self._save_project()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update resolution: {e}")

    def _add_sprite(self):
        """Add a new sprite."""
        file_path = _native_open_file_dialog(
            title="Select Sprite Image",
            filetypes=[("Image files", "*.png *.PNG *.bmp *.BMP *.jpg *.JPG *.jpeg *.JPEG"), ("All files", "*.*")]
        )

        if not file_path:
            return

        # Get name
        default_name = os.path.splitext(os.path.basename(file_path))[0]
        name = simpledialog.askstring("Sprite Name", "Enter sprite name:", initialvalue=default_name)
        if not name:
            return

        # Clean name for C variable
        name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)

        # Check for duplicate name and ask to overwrite
        existing_idx = None
        for i, s in enumerate(self.sprites):
            if s.name == name:
                existing_idx = i
                break
        if existing_idx is not None:
            if not messagebox.askyesno("Duplicate Sprite",
                    f"A sprite named \"{name}\" already exists. Overwrite it?"):
                return

        try:
            resolution = int(self.sprite_res_var.get())

            img = Image.open(file_path)

            # Detect transparent color and get processed image
            transparent, img_rgb = self._detect_transparent_color(img, resolution, resolution)
            pixels = img_rgb.load()

            # Convert to BGR565
            c_vals = []
            for y in range(resolution):
                for x in range(resolution):
                    r, g, b = pixels[x, y]
                    blue5 = b >> 3
                    green6 = g >> 2
                    red5 = r >> 3
                    color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
                    c_vals.append(f"0x{color:04X}")

            sprite = Sprite(name, file_path, resolution, c_vals, transparent)

            # Create transparency-aware preview with checkerboard background
            sprite.preview = self._create_sprite_preview(img_rgb, resolution, resolution, transparent)

            if existing_idx is not None:
                self.sprites[existing_idx] = sprite
            else:
                self.sprites.append(sprite)

            self._refresh_sprite_list()
            self._update_memory_display()
            self._auto_export()
            self._save_project()

            # Select the sprite
            select_idx = existing_idx if existing_idx is not None else len(self.sprites) - 1
            self._select_sprite_row(select_idx)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sprite: {e}")

    def _remove_sprites(self):
        """Remove all selected sprites (supports multi-select)."""
        if not self.selected_sprite_rows:
            return

        # Sort indices in reverse order to delete from end first
        indices_to_remove = sorted(self.selected_sprite_rows, reverse=True)

        for idx in indices_to_remove:
            if idx < len(self.sprites):
                del self.sprites[idx]

        self.selected_sprite_rows = set()
        self.last_sprite_click = None
        self._refresh_sprite_list()
        self._update_memory_display()
        self._auto_export()
        self._save_project()

        # Clear preview
        self.sprite_preview_label.config(image='')
        self.sprite_preview_info.config(text='')

    def _rename_sprite(self):
        """Rename the selected sprite."""
        if not self.selected_sprite_rows or self.last_sprite_click is None:
            messagebox.showinfo("Info", "Please select a sprite to rename.")
            return

        idx = self.last_sprite_click
        if idx >= len(self.sprites):
            return

        sprite = self.sprites[idx]
        old_name = sprite.name

        new_name = simpledialog.askstring("Rename Sprite", "Enter new name:", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return

        # Clean name for C variable
        new_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in new_name)

        # Check for duplicate
        if any(s.name == new_name for s in self.sprites):
            messagebox.showerror("Error", f"Sprite '{new_name}' already exists.")
            return

        sprite.name = new_name
        self._refresh_sprite_list()
        self._auto_export()
        self._save_project()

    def _edit_sprite_transparency(self):
        """Open dialog to edit sprite transparency by color picking from preview."""
        if not self.selected_sprite_rows or self.last_sprite_click is None:
            messagebox.showinfo("Info", "Please select a sprite to edit transparency.")
            return

        idx = self.last_sprite_click
        if idx >= len(self.sprites):
            return

        sprite = self.sprites[idx]

        # Store original transparent color and c_array for cancel
        original_transparent = sprite.transparent
        original_c_array = sprite.c_array[:] if sprite.c_array else None

        # Load image from c_array if it exists (preserves previous edits), otherwise from file
        try:
            if sprite.c_array and len(sprite.c_array) == sprite.resolution * sprite.resolution:
                # Reconstruct image from saved c_array data (preserves erase/de-erase edits)
                img_rgb = Image.new("RGB", (sprite.resolution, sprite.resolution))
                pixels = img_rgb.load()

                for i, hex_val in enumerate(sprite.c_array):
                    bgr565 = int(hex_val, 16)
                    # Convert BGR565 to RGB
                    blue5 = (bgr565 >> 11) & 0x1F
                    green6 = (bgr565 >> 5) & 0x3F
                    red5 = bgr565 & 0x1F

                    r = (red5 << 3) | (red5 >> 2)
                    g = (green6 << 2) | (green6 >> 4)
                    b = (blue5 << 3) | (blue5 >> 2)

                    x = i % sprite.resolution
                    y = i // sprite.resolution
                    pixels[x, y] = (r, g, b)
            else:
                # No c_array yet - load from original image file
                if not os.path.exists(sprite.image_path):
                    messagebox.showerror("Error", f"Image file not found: {sprite.image_path}")
                    return

                img = Image.open(sprite.image_path)
                # Process image to match sprite resolution
                img_resized = resize_and_letterbox(img, sprite.resolution, sprite.resolution)
                img_rgb = img_resized.convert("RGB")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")
            return

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Sprite - {sprite.name}")
        dialog.geometry("960x720")
        dialog.transient(self.root)
        dialog.grab_set()

        # Main frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Instructions
        instr_label = ttk.Label(main_frame,
                                text="Use the edit modes below to pick transparency, erase/restore pixels, or crop the sprite.",
                                font=('Arial', 10))
        instr_label.pack(pady=(0, 10))

        # Preview size (larger for easier pixel editing)
        preview_size = 384
        # Calculate scale to fit sprite in preview (at least 4x for visibility)
        max_scale = preview_size // sprite.resolution
        scale = max(4, min(max_scale, 16))  # Scale between 4x and 16x for easier editing
        display_size = sprite.resolution * scale
        offset_x = (preview_size - display_size) // 2
        offset_y = (preview_size - display_size) // 2

        # Scale sprite for display (will be updated when pixels change)
        sprite_scaled = img_rgb.resize((display_size, display_size), Image.NEAREST)
        sprite_pixels = sprite_scaled.load()

        # Preview container (side by side)
        preview_container = ttk.Frame(main_frame)
        preview_container.pack(pady=10)

        # LEFT: Original sprite (no transparency) - clickable
        left_frame = ttk.LabelFrame(preview_container, text="Original (Click to Pick)")
        left_frame.pack(side='left', padx=10)

        # Create original sprite preview (no transparency)
        def update_original_preview():
            """Update the left preview with current image."""
            # Regenerate scaled sprite from current img_rgb
            current_scaled = img_rgb.resize((display_size, display_size), Image.NEAREST)
            original_img = Image.new("RGB", (preview_size, preview_size), (200, 200, 200))
            original_img.paste(current_scaled, (offset_x, offset_y))
            original_photo_new = ImageTk.PhotoImage(original_img)
            original_canvas.delete('all')
            original_canvas.create_image(0, 0, anchor='nw', image=original_photo_new)
            original_canvas.image = original_photo_new  # Keep reference

        original_img = Image.new("RGB", (preview_size, preview_size), (200, 200, 200))
        original_img.paste(sprite_scaled, (offset_x, offset_y))
        original_photo = ImageTk.PhotoImage(original_img)

        original_canvas = tk.Canvas(left_frame, width=preview_size, height=preview_size, 
                                   highlightthickness=2, highlightbackground='blue', cursor='crosshair')
        original_canvas.pack(padx=10, pady=10)
        original_canvas.create_image(0, 0, anchor='nw', image=original_photo)
        original_canvas.image = original_photo  # Keep reference

        # RIGHT: Transparent version (updates in real-time)
        right_frame = ttk.LabelFrame(preview_container, text="With Transparency")
        right_frame.pack(side='left', padx=10)

        transparent_canvas = tk.Canvas(right_frame, width=preview_size, height=preview_size, 
                                       highlightthickness=2, highlightbackground='black', cursor='crosshair')
        transparent_canvas.pack(padx=10, pady=10)

        # Mode tracking: 'pick', 'erase', 'de_erase', 'crop', 'fill_transparent'
        edit_mode = 'pick'
        is_drawing_on_transparent = False
        brush_size = 1  # Brush radius in pixels

        # Undo stack: list of (img_rgb_copy, transparent_color) snapshots
        sprite_undo_stack = []

        # Crop state (coordinates in crop_source_img pixel space)
        crop_x1 = 0
        crop_y1 = 0
        crop_x2 = 0
        crop_y2 = 0
        crop_rect_id = None    # Canvas rectangle ID for the selection overlay
        crop_handle_ids = []   # Canvas IDs for the 8 drag handles
        crop_active = False    # True once a crop region has been drawn
        crop_drag_mode = None  # None, 'new', or handle name ('nw','n','ne','e','se','s','sw','w','move')
        crop_drag_anchor = None  # (x, y) for move/drag reference
        crop_square = False    # Constrain to square

        # The image displayed on the left canvas during crop mode, and its display params
        crop_source_img = None   # PIL Image (full-res original or img_rgb fallback)
        crop_source_w = 0
        crop_source_h = 0
        crop_display_scale = 1.0   # canvas pixels per source pixel (may be < 1)
        crop_display_size_x = 0
        crop_display_size_y = 0
        crop_display_offset_x = 0
        crop_display_offset_y = 0

        # Load original source image for high-quality cropping (if available)
        original_source_img = None
        if sprite.image_path and os.path.exists(sprite.image_path):
            try:
                original_source_img = Image.open(sprite.image_path).convert("RGB")
            except Exception:
                original_source_img = None

        def update_both_previews():
            """Update both the original and transparent previews."""
            # Update original preview (left side)
            update_original_preview()
            
            # Update transparent preview (right side)
            update_transparent_preview()

        def update_transparent_preview():
            """Update the right preview with current transparent color - uses same function as actual preview."""
            # Use the exact same function that creates the actual sprite preview (PIL Image version)
            preview_pil_img = self._create_sprite_preview_image(img_rgb, sprite.resolution, sprite.resolution, sprite.transparent)
            
            # Scale to fill the entire canvas (resize to fit preview_size)
            preview_pil_img = preview_pil_img.resize((preview_size, preview_size), Image.NEAREST)
            
            preview_photo = ImageTk.PhotoImage(preview_pil_img)
            transparent_canvas.delete('all')
            transparent_canvas.create_image(0, 0, anchor='nw', image=preview_photo)
            transparent_canvas.image = preview_photo  # Keep reference

        # Initial transparent preview
        update_transparent_preview()

        # Helper: convert canvas event to sprite pixel coordinates
        def canvas_to_sprite(event):
            canvas_x = event.x - offset_x
            canvas_y = event.y - offset_y
            if 0 <= canvas_x < display_size and 0 <= canvas_y < display_size:
                sx = max(0, min(sprite.resolution - 1, canvas_x // scale))
                sy = max(0, min(sprite.resolution - 1, canvas_y // scale))
                return sx, sy
            return None

        # --- Crop drawing and interaction ---
        HANDLE_SIZE = 6  # Half-size of drag handles in canvas pixels

        def _setup_crop_display():
            """Configure crop display params and show source image on left canvas."""
            nonlocal crop_source_img, crop_source_w, crop_source_h
            nonlocal crop_display_scale, crop_display_size_x, crop_display_size_y
            nonlocal crop_display_offset_x, crop_display_offset_y

            # Use full-res original if available, otherwise fall back to img_rgb
            if original_source_img is not None:
                crop_source_img = original_source_img
            else:
                crop_source_img = img_rgb

            crop_source_w, crop_source_h = crop_source_img.size

            # Compute scale to fit the source image in preview_size, preserving aspect ratio
            scale_x = preview_size / crop_source_w
            scale_y = preview_size / crop_source_h
            crop_display_scale = min(scale_x, scale_y)
            crop_display_size_x = int(crop_source_w * crop_display_scale)
            crop_display_size_y = int(crop_source_h * crop_display_scale)
            crop_display_offset_x = (preview_size - crop_display_size_x) // 2
            crop_display_offset_y = (preview_size - crop_display_size_y) // 2

            # Render source image on the left canvas
            display_img = crop_source_img.resize(
                (crop_display_size_x, crop_display_size_y), Image.LANCZOS)
            canvas_img = Image.new("RGB", (preview_size, preview_size), (200, 200, 200))
            canvas_img.paste(display_img, (crop_display_offset_x, crop_display_offset_y))
            photo = ImageTk.PhotoImage(canvas_img)
            original_canvas.delete('all')
            original_canvas.create_image(0, 0, anchor='nw', image=photo)
            original_canvas.image = photo

        def _crop_canvas_coords():
            """Return (cx1, cy1, cx2, cy2) canvas pixel coords for the current crop rect."""
            s = crop_display_scale
            ox, oy = crop_display_offset_x, crop_display_offset_y
            cx1 = crop_x1 * s + ox
            cy1 = crop_y1 * s + oy
            cx2 = (crop_x2 + 1) * s + ox
            cy2 = (crop_y2 + 1) * s + oy
            return cx1, cy1, cx2, cy2

        def canvas_to_crop(event):
            """Convert canvas event coords to source image pixel coords."""
            cx = event.x - crop_display_offset_x
            cy = event.y - crop_display_offset_y
            if 0 <= cx < crop_display_size_x and 0 <= cy < crop_display_size_y:
                px = max(0, min(crop_source_w - 1, int(cx / crop_display_scale)))
                py = max(0, min(crop_source_h - 1, int(cy / crop_display_scale)))
                return px, py
            return None

        def draw_crop_rect():
            """Draw/update the crop rectangle and its 8 resize handles on the original canvas."""
            nonlocal crop_rect_id, crop_handle_ids
            # Remove old drawings
            if crop_rect_id is not None:
                original_canvas.delete(crop_rect_id)
                crop_rect_id = None
            for hid in crop_handle_ids:
                original_canvas.delete(hid)
            crop_handle_ids = []

            if not crop_active:
                return

            cx1, cy1, cx2, cy2 = _crop_canvas_coords()
            crop_rect_id = original_canvas.create_rectangle(
                cx1, cy1, cx2, cy2, outline='yellow', width=2, dash=(4, 4))

            # Draw 8 handles: corners + edge midpoints
            mx, my = (cx1 + cx2) / 2, (cy1 + cy2) / 2
            handle_positions = [
                (cx1, cy1), (mx, cy1), (cx2, cy1),   # nw, n, ne
                (cx1, my),              (cx2, my),     # w, e
                (cx1, cy2), (mx, cy2), (cx2, cy2),    # sw, s, se
            ]
            hs = HANDLE_SIZE
            for hx, hy in handle_positions:
                hid = original_canvas.create_rectangle(
                    hx - hs, hy - hs, hx + hs, hy + hs,
                    fill='yellow', outline='black', width=1)
                crop_handle_ids.append(hid)

        def _hit_test_handle(event):
            """Check if event hits a resize handle. Returns handle name or None."""
            if not crop_active:
                return None
            cx1, cy1, cx2, cy2 = _crop_canvas_coords()
            mx, my = (cx1 + cx2) / 2, (cy1 + cy2) / 2
            ex, ey = event.x, event.y
            hs = HANDLE_SIZE + 3  # Generous hit area

            handles = [
                ('nw', cx1, cy1), ('n', mx, cy1), ('ne', cx2, cy1),
                ('w', cx1, my),                    ('e', cx2, my),
                ('sw', cx1, cy2), ('s', mx, cy2), ('se', cx2, cy2),
            ]
            for name, hx, hy in handles:
                if abs(ex - hx) <= hs and abs(ey - hy) <= hs:
                    return name

            # Check if inside the rectangle (for move)
            if cx1 <= ex <= cx2 and cy1 <= ey <= cy2:
                return 'move'
            return None

        def _constrain_square(ax, ay, bx, by):
            """Constrain bx,by so the rectangle from (ax,ay) to (bx,by) is square."""
            dx = bx - ax
            dy = by - ay
            side = max(abs(dx), abs(dy))
            bx = ax + (side if dx >= 0 else -side)
            by = ay + (side if dy >= 0 else -side)
            return bx, by

        def _clamp_crop():
            """Clamp crop coordinates to valid source image range and enforce ordering."""
            nonlocal crop_x1, crop_y1, crop_x2, crop_y2
            crop_x1 = max(0, min(crop_source_w - 1, crop_x1))
            crop_y1 = max(0, min(crop_source_h - 1, crop_y1))
            crop_x2 = max(0, min(crop_source_w - 1, crop_x2))
            crop_y2 = max(0, min(crop_source_h - 1, crop_y2))
            if crop_x1 > crop_x2:
                crop_x1, crop_x2 = crop_x2, crop_x1
            if crop_y1 > crop_y2:
                crop_y1, crop_y2 = crop_y2, crop_y1

        # Click handler for original canvas (mode-aware)
        def on_original_press(event):
            nonlocal crop_x1, crop_y1, crop_x2, crop_y2
            nonlocal crop_active, crop_drag_mode, crop_drag_anchor
            if edit_mode == 'crop':
                # Check if clicking on an existing handle first
                if crop_active:
                    handle = _hit_test_handle(event)
                    if handle:
                        crop_drag_mode = handle
                        crop_drag_anchor = canvas_to_crop(event)
                        return

                # Start a new crop rectangle
                coords = canvas_to_crop(event)
                if coords:
                    crop_x1, crop_y1 = coords
                    crop_x2, crop_y2 = coords
                    crop_active = True
                    crop_drag_mode = 'new'
                    crop_drag_anchor = coords
                    draw_crop_rect()
                    update_crop_preview()
            else:
                # Color pick mode
                coords = canvas_to_sprite(event)
                if coords:
                    sprite_x, sprite_y = coords
                    pixels = img_rgb.load()
                    r, g, b = pixels[sprite_x, sprite_y]

                    blue5 = b >> 3
                    green6 = g >> 2
                    red5 = r >> 3
                    new_transparent = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)

                    # Save undo snapshot before changing transparent color
                    sprite_undo_stack.append((img_rgb.copy(), sprite.transparent))
                    if len(sprite_undo_stack) > 50:
                        sprite_undo_stack.pop(0)

                    sprite.transparent = new_transparent
                    update_transparent_preview()
                    status_label.config(text=f"Transparent color set to 0x{new_transparent:04X} (RGB: {r}, {g}, {b})",
                                       foreground='green')

        def on_original_drag(event):
            nonlocal crop_x1, crop_y1, crop_x2, crop_y2, crop_drag_anchor
            if edit_mode != 'crop' or crop_drag_mode is None:
                return
            coords = canvas_to_crop(event)
            if not coords:
                return
            sx, sy = coords
            max_w = crop_source_w - 1
            max_h = crop_source_h - 1

            if crop_drag_mode == 'new':
                ax, ay = crop_drag_anchor
                bx, by = sx, sy
                if crop_square:
                    bx, by = _constrain_square(ax, ay, bx, by)
                crop_x1, crop_y1 = min(ax, bx), min(ay, by)
                crop_x2, crop_y2 = max(ax, bx), max(ay, by)

            elif crop_drag_mode == 'move':
                if crop_drag_anchor:
                    dx = sx - crop_drag_anchor[0]
                    dy = sy - crop_drag_anchor[1]
                    w = crop_x2 - crop_x1
                    h = crop_y2 - crop_y1
                    nx1 = crop_x1 + dx
                    ny1 = crop_y1 + dy
                    nx1 = max(0, min(max_w - w, nx1))
                    ny1 = max(0, min(max_h - h, ny1))
                    crop_x1, crop_y1 = nx1, ny1
                    crop_x2, crop_y2 = nx1 + w, ny1 + h
                    crop_drag_anchor = (sx, sy)

            else:
                mode = crop_drag_mode
                nx1, ny1, nx2, ny2 = crop_x1, crop_y1, crop_x2, crop_y2

                if 'w' in mode:
                    nx1 = sx
                if 'e' in mode:
                    nx2 = sx
                if 'n' in mode:
                    ny1 = sy
                if 's' in mode:
                    ny2 = sy

                if crop_square:
                    if mode == 'nw':
                        nx1, ny1 = _constrain_square(nx2, ny2, nx1, ny1)
                    elif mode == 'ne':
                        nx2, ny1 = _constrain_square(nx1, ny2, nx2, ny1)
                    elif mode == 'sw':
                        nx1, ny2 = _constrain_square(nx2, ny1, nx1, ny2)
                    elif mode == 'se':
                        nx2, ny2 = _constrain_square(nx1, ny1, nx2, ny2)
                    elif mode in ('n', 's'):
                        h = abs(ny2 - ny1)
                        mid = (nx1 + nx2) / 2
                        nx1 = int(mid - h / 2)
                        nx2 = int(mid + h / 2)
                    elif mode in ('e', 'w'):
                        w = abs(nx2 - nx1)
                        mid = (ny1 + ny2) / 2
                        ny1 = int(mid - w / 2)
                        ny2 = int(mid + w / 2)

                crop_x1, crop_y1 = min(nx1, nx2), min(ny1, ny2)
                crop_x2, crop_y2 = max(nx1, nx2), max(ny1, ny2)

            _clamp_crop()
            draw_crop_rect()
            update_crop_preview()

        def on_original_release(event):
            nonlocal crop_drag_mode, crop_drag_anchor
            if edit_mode == 'crop':
                crop_drag_mode = None
                crop_drag_anchor = None

        original_canvas.bind('<Button-1>', on_original_press)
        original_canvas.bind('<B1-Motion>', on_original_drag)
        original_canvas.bind('<ButtonRelease-1>', on_original_release)

        # Crop preview: show what the cropped region looks like at full sprite resolution
        def update_crop_preview():
            if not crop_active:
                return
            w = crop_x2 - crop_x1 + 1
            h = crop_y2 - crop_y1 + 1
            if w < 1 or h < 1:
                return

            # Crop directly from the source image (full-res or img_rgb fallback)
            cropped = crop_source_img.crop((crop_x1, crop_y1, crop_x2 + 1, crop_y2 + 1))
            cropped_resized = resize_and_letterbox(cropped, sprite.resolution, sprite.resolution)
            crop_display = cropped_resized.resize((preview_size, preview_size), Image.NEAREST)
            crop_photo = ImageTk.PhotoImage(crop_display)
            transparent_canvas.delete('all')
            transparent_canvas.create_image(0, 0, anchor='nw', image=crop_photo)
            transparent_canvas.image = crop_photo

        # Click handler for transparent canvas (right side) - for erase/de-erase
        def on_transparent_click(event):
            """Handle clicks on the transparent preview for erase/de-erase/fill_transparent."""
            if edit_mode not in ('erase', 'de_erase', 'fill_transparent'):
                return

            # Convert canvas coordinates to sprite coordinates
            # The transparent preview is scaled to preview_size, so we need to scale back
            center_x = int((event.x / preview_size) * sprite.resolution)
            center_y = int((event.y / preview_size) * sprite.resolution)
            
            # Clamp center to valid range
            center_x = max(0, min(sprite.resolution - 1, center_x))
            center_y = max(0, min(sprite.resolution - 1, center_y))
            
            pixels = img_rgb.load()

            # Fill transparent mode: replace all pixels of clicked color with transparent
            if edit_mode == 'fill_transparent':
                r, g, b = pixels[center_x, center_y]
                target_bgr565 = ((b >> 3) << 11) | ((g >> 2) << 5) | (r >> 3)

                if target_bgr565 == sprite.transparent:
                    status_label.config(text="That color is already the transparent color.",
                                       foreground='orange')
                    return

                # Save undo snapshot before fill
                sprite_undo_stack.append((img_rgb.copy(), sprite.transparent))
                if len(sprite_undo_stack) > 50:
                    sprite_undo_stack.pop(0)

                trans_b = ((sprite.transparent >> 11) & 0x1F) << 3
                trans_g = ((sprite.transparent >> 5) & 0x3F) << 2
                trans_r = (sprite.transparent & 0x1F) << 3

                count = 0
                for py in range(sprite.resolution):
                    for px in range(sprite.resolution):
                        pr, pg, pb = pixels[px, py]
                        pixel_bgr = ((pb >> 3) << 11) | ((pg >> 2) << 5) | (pr >> 3)
                        if pixel_bgr == target_bgr565:
                            pixels[px, py] = (trans_r, trans_g, trans_b)
                            count += 1

                update_both_previews()
                status_label.config(
                    text=f"Filled {count} pixels of 0x{target_bgr565:04X} with transparent color 0x{sprite.transparent:04X}",
                    foreground='green')
                return

            radius = brush_size

            # Paint all pixels within brush radius (circular brush)
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    # Check if pixel is within circular brush
                    if dx * dx + dy * dy <= radius * radius:
                        sprite_x = center_x + dx
                        sprite_y = center_y + dy
                        
                        # Clamp to valid range
                        if 0 <= sprite_x < sprite.resolution and 0 <= sprite_y < sprite.resolution:
                            if edit_mode == 'erase':
                                # Set pixel to transparent color
                                trans_b = ((sprite.transparent >> 11) & 0x1F) << 3
                                trans_g = ((sprite.transparent >> 5) & 0x3F) << 2
                                trans_r = (sprite.transparent & 0x1F) << 3
                                pixels[sprite_x, sprite_y] = (trans_r, trans_g, trans_b)
                                
                            elif edit_mode == 'de_erase':
                                # Only modify pixels that are currently transparent (exact BGR565 match)
                                # Change LSB of BGR565 for minimal visual effect
                                current_r, current_g, current_b = pixels[sprite_x, sprite_y]
                                
                                # Convert current pixel to BGR565
                                current_bgr565 = ((current_b >> 3) << 11) | ((current_g >> 2) << 5) | (current_r >> 3)
                                
                                # Only proceed if pixel is exactly transparent
                                if current_bgr565 == sprite.transparent:
                                    # Flip LSB (bit 0) of BGR565 - this changes it by 1 (minimal change)
                                    new_bgr565 = current_bgr565 ^ 1
                                    
                                    # Convert new BGR565 back to RGB
                                    # Extract components
                                    new_blue5 = (new_bgr565 >> 11) & 0x1F
                                    new_green6 = (new_bgr565 >> 5) & 0x3F
                                    new_red5 = new_bgr565 & 0x1F
                                    
                                    # Convert back to 8-bit RGB (reconstruct from 5/6 bit values)
                                    # For 5-bit: multiply by 8 and add 4 for better approximation
                                    # For 6-bit: multiply by 4 and add 2
                                    new_r = (new_red5 << 3) | (new_red5 >> 2)
                                    new_g = (new_green6 << 2) | (new_green6 >> 4)
                                    new_b = (new_blue5 << 3) | (new_blue5 >> 2)
                                    
                                    # Clamp to valid range
                                    new_r = max(0, min(255, new_r))
                                    new_g = max(0, min(255, new_g))
                                    new_b = max(0, min(255, new_b))
                                    
                                    # Set pixel to this "almost transparent" color
                                    pixels[sprite_x, sprite_y] = (new_r, new_g, new_b)
                                # If pixel is not transparent, do nothing (don't modify visible pixels)
            
            # Update both previews
            update_both_previews()

        def on_transparent_drag(event):
            """Handle drag on transparent preview."""
            nonlocal is_drawing_on_transparent
            if is_drawing_on_transparent:
                on_transparent_click(event)

        def on_transparent_press(event):
            """Handle mouse press on transparent preview."""
            nonlocal is_drawing_on_transparent
            if edit_mode == 'fill_transparent':
                # Fill is a single-click action (undo saved inside on_transparent_click)
                on_transparent_click(event)
            elif edit_mode in ('erase', 'de_erase'):
                # Save undo snapshot before stroke begins
                sprite_undo_stack.append((img_rgb.copy(), sprite.transparent))
                if len(sprite_undo_stack) > 50:
                    sprite_undo_stack.pop(0)
                is_drawing_on_transparent = True
                on_transparent_click(event)

        def on_transparent_release(event):
            """Handle mouse release on transparent preview."""
            nonlocal is_drawing_on_transparent
            is_drawing_on_transparent = False

        transparent_canvas.bind('<Button-1>', on_transparent_press)
        transparent_canvas.bind('<B1-Motion>', on_transparent_drag)
        transparent_canvas.bind('<ButtonRelease-1>', on_transparent_release)

        # Undo handler for sprite editor
        def sprite_undo(event=None):
            nonlocal img_rgb
            if sprite_undo_stack:
                img_rgb_copy, trans = sprite_undo_stack.pop()
                img_rgb = img_rgb_copy
                sprite.transparent = trans
                update_both_previews()
                status_label.config(text="Undo applied.", foreground='blue')

        dialog.bind('<Control-z>', sprite_undo)
        dialog.bind('<Control-Z>', sprite_undo)

        # Status label
        status_label = ttk.Label(main_frame, 
                                text=f"Current transparent: 0x{sprite.transparent:04X}\nClick on the left preview to pick a new transparent color.",
                                font=('Consolas', 9), justify='center')
        status_label.pack(pady=10)

        # Mode buttons
        mode_frame = ttk.Frame(main_frame)
        mode_frame.pack(pady=5)

        def clear_crop():
            """Clear crop selection overlay and state."""
            nonlocal crop_rect_id, crop_handle_ids, crop_active, crop_drag_mode, crop_drag_anchor
            if crop_rect_id is not None:
                original_canvas.delete(crop_rect_id)
                crop_rect_id = None
            for hid in crop_handle_ids:
                original_canvas.delete(hid)
            crop_handle_ids = []
            crop_active = False
            crop_drag_mode = None
            crop_drag_anchor = None

        def _restore_sprite_view():
            """Restore the left canvas to show img_rgb at sprite resolution."""
            clear_crop()
            update_original_preview()

        def set_erase_mode():
            nonlocal edit_mode
            if edit_mode == 'crop':
                _restore_sprite_view()
            edit_mode = 'erase'
            status_label.config(text="Mode: Erase - Click on right preview to set pixels to transparent",
                               foreground='red')
            erase_btn.config(state='pressed' if hasattr(erase_btn, 'state') else 'active')
            de_erase_btn.config(state='normal')
            brush_frame.pack(pady=5)  # Show brush slider
            crop_frame.pack_forget()  # Hide crop controls
            update_transparent_preview()

        def set_de_erase_mode():
            nonlocal edit_mode
            if edit_mode == 'crop':
                _restore_sprite_view()
            edit_mode = 'de_erase'
            status_label.config(text="Mode: De-Erase - Click on right preview to make pixels visible (off by 1)",
                               foreground='orange')
            de_erase_btn.config(state='pressed' if hasattr(de_erase_btn, 'state') else 'active')
            erase_btn.config(state='normal')
            brush_frame.pack(pady=5)  # Show brush slider
            crop_frame.pack_forget()  # Hide crop controls
            update_transparent_preview()

        def set_pick_mode():
            nonlocal edit_mode
            if edit_mode == 'crop':
                _restore_sprite_view()
            edit_mode = 'pick'
            status_label.config(text=f"Current transparent: 0x{sprite.transparent:04X}\nClick on the left preview to pick a new transparent color.",
                               foreground='black')
            erase_btn.config(state='normal')
            de_erase_btn.config(state='normal')
            brush_frame.pack_forget()  # Hide brush slider
            crop_frame.pack_forget()  # Hide crop controls
            update_transparent_preview()

        def set_fill_transparent_mode():
            nonlocal edit_mode
            if edit_mode == 'crop':
                _restore_sprite_view()
            edit_mode = 'fill_transparent'
            status_label.config(
                text="Mode: Fill Transparent - Click a color on the left preview to make all matching pixels transparent",
                foreground='purple')
            erase_btn.config(state='normal')
            de_erase_btn.config(state='normal')
            brush_frame.pack_forget()
            crop_frame.pack_forget()
            update_transparent_preview()

        def set_crop_mode():
            nonlocal edit_mode, crop_x1, crop_y1, crop_x2, crop_y2, crop_active
            edit_mode = 'crop'
            clear_crop()
            _setup_crop_display()  # Show full-res source image on left canvas

            # Restore previous crop bounds if they exist (so user can adjust)
            if sprite.crop_bounds is not None and original_source_img is not None:
                bx1, by1, bx2, by2 = sprite.crop_bounds
                crop_x1, crop_y1 = bx1, by1
                crop_x2, crop_y2 = bx2 - 1, by2 - 1  # Convert back from exclusive to inclusive
                crop_active = True
                draw_crop_rect()
                update_crop_preview()

            status_label.config(text="Mode: Crop - Click and drag on the left preview to select a region.",
                               foreground='blue')
            erase_btn.config(state='normal')
            de_erase_btn.config(state='normal')
            brush_frame.pack_forget()  # Hide brush slider
            crop_frame.pack(pady=5)   # Show crop controls

        def apply_crop():
            """Apply the crop: replace img_rgb with cropped and resized region."""
            nonlocal img_rgb
            if not crop_active:
                return
            w = crop_x2 - crop_x1 + 1
            h = crop_y2 - crop_y1 + 1
            if w < 1 or h < 1:
                return

            # Save undo snapshot before crop
            sprite_undo_stack.append((img_rgb.copy(), sprite.transparent))
            if len(sprite_undo_stack) > 50:
                sprite_undo_stack.pop(0)

            # Crop directly from the source image (coordinates are already in its pixel space)
            cropped = crop_source_img.crop((crop_x1, crop_y1, crop_x2 + 1, crop_y2 + 1))
            img_rgb = resize_and_letterbox(cropped, sprite.resolution, sprite.resolution)

            # Save crop bounds so resolution changes can re-crop from the original
            # If cropping from the original source, store the absolute pixel bounds.
            # If cropping from img_rgb fallback, store None (can't meaningfully re-apply).
            if original_source_img is not None:
                sprite.crop_bounds = (crop_x1, crop_y1, crop_x2 + 1, crop_y2 + 1)
            else:
                sprite.crop_bounds = None

            # set_pick_mode restores the sprite-resolution view and clears crop state
            set_pick_mode()
            update_both_previews()
            status_label.config(text="Crop applied.", foreground='green')

        ttk.Label(mode_frame, text="Edit Modes:", font=('Arial', 9, 'bold')).pack(side='left', padx=5)
        erase_btn = ttk.Button(mode_frame, text="Erase", command=set_erase_mode)
        erase_btn.pack(side='left', padx=5)
        de_erase_btn = ttk.Button(mode_frame, text="De-Erase", command=set_de_erase_mode)
        de_erase_btn.pack(side='left', padx=5)
        ttk.Button(mode_frame, text="Pick Color", command=set_pick_mode).pack(side='left', padx=5)
        ttk.Button(mode_frame, text="Fill Transparent", command=set_fill_transparent_mode).pack(side='left', padx=5)
        ttk.Button(mode_frame, text="Crop", command=set_crop_mode).pack(side='left', padx=5)

        # Brush size slider (only visible in erase/de-erase modes)
        brush_frame = ttk.Frame(main_frame)

        brush_size_var = tk.IntVar(value=1)
        brush_size_label = ttk.Label(brush_frame, text="Brush Size: 1", font=('Arial', 9))
        brush_size_label.pack(side='left', padx=5)
        def update_brush_size(val):
            nonlocal brush_size
            brush_size = int(float(val))
            brush_size_label.config(text=f"Brush Size: {brush_size}")

        brush_size_slider = ttk.Scale(brush_frame, from_=1, to=10, orient='horizontal',
                                      variable=brush_size_var, length=150,
                                      command=update_brush_size)
        brush_size_slider.pack(side='left', padx=5)

        # Initially hide brush slider
        brush_frame.pack_forget()

        # Crop controls (only visible in crop mode)
        crop_frame = ttk.Frame(main_frame)
        ttk.Button(crop_frame, text="Apply Crop", command=apply_crop).pack(side='left', padx=5)
        crop_square_var = tk.BooleanVar(value=False)
        def on_square_toggle():
            nonlocal crop_square
            crop_square = crop_square_var.get()
        ttk.Checkbutton(crop_frame, text="Square", variable=crop_square_var,
                        command=on_square_toggle).pack(side='left', padx=5)
        ttk.Label(crop_frame, text="Drag to select, then adjust handles. Click Apply Crop when done.",
                  font=('Arial', 9)).pack(side='left', padx=5)
        crop_frame.pack_forget()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        def apply_changes():
            """Apply the transparency change and regenerate sprite data."""
            # Regenerate C array with new transparent color
            pixels = img_rgb.load()
            c_vals = []
            for y in range(sprite.resolution):
                for x in range(sprite.resolution):
                    r, g, b = pixels[x, y]
                    blue5 = b >> 3
                    green6 = g >> 2
                    red5 = r >> 3
                    color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
                    c_vals.append(f"0x{color:04X}")
            
            sprite.c_array = c_vals
            
            # Regenerate preview
            sprite.preview = self._create_sprite_preview(img_rgb, sprite.resolution, sprite.resolution, sprite.transparent)
            
            # Update UI
            self._refresh_sprite_list()
            self._select_sprite_row(idx)  # Reselect to update preview
            self._update_memory_display()
            self._auto_export()
            self._save_project()
            
            dialog.destroy()

        def cancel_changes():
            """Cancel and restore original transparent color and data."""
            sprite.transparent = original_transparent
            if original_c_array is not None:
                sprite.c_array = original_c_array
            dialog.destroy()

        ttk.Button(button_frame, text="Apply", command=apply_changes).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel_changes).pack(side='left', padx=5)

    def _create_sprite_preview_image(self, img_rgb, width, height, transparent_bgr565):
        """
        Create a transparency-aware sprite preview PIL Image that simulates in-game appearance.
        Shows checkerboard pattern behind transparent pixels, scaled as it would appear in-game.
        Returns PIL Image (not PhotoImage).
        """
        # Simulate sprite at larger scale for better visibility
        scale = max(2, 128 // height)
        display_w = width * scale
        display_h = height * scale

        # Create checkerboard background
        checker = create_checkerboard(display_w, display_h, cell_size=max(4, scale))

        # Scale sprite with NEAREST to simulate in-game sampling
        sprite_scaled = img_rgb.resize((display_w, display_h), Image.NEAREST)
        sprite_pixels = sprite_scaled.load()

        # Convert transparent color back to RGB for comparison
        # BGR565: ((b>>3)<<11) | ((g>>2)<<5) | (r>>3)
        trans_b = ((transparent_bgr565 >> 11) & 0x1F) << 3
        trans_g = ((transparent_bgr565 >> 5) & 0x3F) << 2
        trans_r = (transparent_bgr565 & 0x1F) << 3

        # Composite: draw sprite pixels on checkerboard, skip transparent
        checker_pixels = checker.load()
        for y in range(display_h):
            for x in range(display_w):
                r, g, b = sprite_pixels[x, y]
                # Check if this pixel matches transparent color EXACTLY (no tolerance - matches C code)
                # Convert pixel to BGR565 and compare
                pixel_bgr565 = ((b >> 3) << 11) | ((g >> 2) << 5) | (r >> 3)
                if pixel_bgr565 == transparent_bgr565:
                    # Transparent - leave checkerboard visible
                    pass
                else:
                    # Opaque - draw sprite pixel
                    checker_pixels[x, y] = (r, g, b)

        return checker

    def _create_sprite_preview(self, img_rgb, width, height, transparent_bgr565):
        """
        Create a transparency-aware sprite preview that simulates in-game appearance.
        Shows checkerboard pattern behind transparent pixels, scaled as it would appear in-game.
        Returns PhotoImage for tkinter.
        """
        preview_img = self._create_sprite_preview_image(img_rgb, width, height, transparent_bgr565)
        return ImageTk.PhotoImage(preview_img)

    def _update_memory_display(self):
        """Update the memory usage display."""
        tex_memory = sum(t.memory_bytes() for t in self.textures)
        sprite_memory = sum(s.memory_bytes() for s in self.sprites)
        map_memory = MAP_SIZE * MAP_SIZE * len(self.maps)  # 1 byte per cell per map
        font_memory = 255 * 5 if self.font_data else 0  # 5 bytes per character
        total = tex_memory + sprite_memory + map_memory + font_memory

        self.memory_label.config(text=f"Memory Usage: {total:,} bytes")
        self.memory_detail.config(
            text=f"Tex: {tex_memory:,}  |  Spr: {sprite_memory:,}  |  Maps: {map_memory}  |  Font: {font_memory}"
        )

    # ========== Project Save/Load ==========

    def _save_project(self):
        """Save project state to JSON file."""
        try:
            project = {
                'maps': self.maps,  # List of {"name": str, "data": 2D list}
                'current_map_idx': self.current_map_idx,
                'textures': [t.to_dict() for t in self.textures] + self._unloaded_textures,
                'sprites': [s.to_dict() for s in self.sprites] + self._unloaded_sprites,
                'colors': [c.to_dict() for c in self.colors]
            }
            if self.font_data is not None:
                project['font_data'] = self.font_data
            if self.font_path:
                project['font_path'] = self.font_path
            with open(PROJECT_FILE, 'w') as f:
                json.dump(project, f, indent=2)
            print(f"Saved: {len(self.textures)} textures, {len(self.sprites)} sprites, {len(self.maps)} maps, {len(self.colors)} colors")
        except Exception as e:
            print(f"Error saving project: {e}")
            messagebox.showerror("Save Error", f"Failed to save project: {e}")

    def _parse_textures_h(self):
        """Parse textures.h to extract texture data (c_array, resolution)."""
        textures_h_path = os.path.join(ASSETS_DIR, "textures.h")
        if not os.path.exists(textures_h_path):
            return {}

        texture_data = {}
        try:
            import re
            with open(textures_h_path, 'r') as f:
                lines = f.readlines()

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Look for texture comment: // NAME (RESxRES)
                comment_match = re.match(r'//\s*(\w+)\s*\((\d+)x(\d+)\)', line)
                if comment_match:
                    name = comment_match.group(1)
                    res = int(comment_match.group(2))

                    # Find the data array
                    i += 1
                    data_array = []
                    while i < len(lines):
                        line = lines[i].strip()
                        if line.startswith('static const uint16_t') and '_data[' in line:
                            i += 1
                            while i < len(lines):
                                line = lines[i].strip()
                                if line == '};':
                                    break
                                hex_values = re.findall(r'0x[0-9A-Fa-f]+', line, re.IGNORECASE)
                                data_array.extend([val.upper() for val in hex_values])
                                i += 1
                            break
                        i += 1

                    if data_array:
                        texture_data[name] = {
                            'c_array': data_array,
                            'resolution': res
                        }
                i += 1
        except Exception as e:
            print(f"Error parsing textures.h: {e}")
            import traceback
            traceback.print_exc()

        return texture_data

    def _create_texture_previews_from_array(self, tex):
        """Create texture previews from BGR565 c_array data (no source image needed)."""
        try:
            res = tex.resolution
            img_rgb = Image.new("RGB", (res, res))
            pixels = img_rgb.load()

            for i, hex_val in enumerate(tex.c_array):
                bgr565 = int(hex_val, 16)
                blue5 = (bgr565 >> 11) & 0x1F
                green6 = (bgr565 >> 5) & 0x3F
                red5 = bgr565 & 0x1F

                r = (red5 << 3) | (red5 >> 2)
                g = (green6 << 2) | (green6 >> 4)
                b = (blue5 << 3) | (blue5 >> 2)

                x = i % res
                y = i // res
                pixels[x, y] = (r, g, b)

            tex.pil_image = img_rgb
            tex.preview = self._create_wall_preview(img_rgb, res)

            tile = img_rgb.resize((CELL_SIZE, CELL_SIZE), Image.NEAREST)
            tex.tile_preview = ImageTk.PhotoImage(tile)
        except Exception as e:
            print(f"Error creating previews from array for {tex.name}: {e}")

    def _parse_images_h(self):
        """Parse images.h to extract sprite data (c_array, transparent, resolution)."""
        images_h_path = os.path.join(ASSETS_DIR, "images.h")
        if not os.path.exists(images_h_path):
            return {}
        
        sprite_data = {}
        try:
            import re
            with open(images_h_path, 'r') as f:
                lines = f.readlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Look for sprite comment: // NAME (RESxRES, transparent=0xXXXX)
                comment_match = re.match(r'//\s*(\w+)\s*\((\d+)x(\d+),\s*transparent=0x([0-9A-Fa-f]+)\)', line)
                if comment_match:
                    name = comment_match.group(1)
                    res = int(comment_match.group(2))
                    transparent_hex = comment_match.group(4)
                    
                    # Find the data array
                    i += 1
                    data_array = []
                    while i < len(lines):
                        line = lines[i].strip()
                        if line.startswith('static const uint16_t') and '_data[' in line:
                            # Found data array start
                            i += 1
                            # Collect all hex values until closing brace
                            while i < len(lines):
                                line = lines[i].strip()
                                if line == '};':
                                    break
                                # Extract hex values from this line
                                hex_values = re.findall(r'0x[0-9A-Fa-f]+', line, re.IGNORECASE)
                                data_array.extend([val.upper() for val in hex_values])
                                i += 1
                            break
                        i += 1
                    
                    # Find the SpriteImage struct to verify transparent color
                    while i < len(lines):
                        line = lines[i].strip()
                        sprite_match = re.match(r'(?:static\s+)?const SpriteImage\s+' + re.escape(name) + r'\s*=\s*\{[^,]+,\s*(\d+),\s*(\d+),\s*0x([0-9A-Fa-f]+)\}', line)
                        if sprite_match:
                            # Use transparent from struct (more reliable)
                            transparent = int(sprite_match.group(3), 16)
                            break
                        i += 1
                    
                    if data_array:
                        sprite_data[name] = {
                            'c_array': data_array,
                            'transparent': int(transparent_hex, 16),
                            'resolution': res
                        }
                i += 1
        except Exception as e:
            print(f"Error parsing images.h: {e}")
            import traceback
            traceback.print_exc()
        
        return sprite_data

    def _load_project(self):
        """Load project state from JSON file."""
        if not os.path.exists(PROJECT_FILE):
            return

        missing_files = []

        try:
            # Parse exported .h files to recover data when source images are missing
            exported_textures = self._parse_textures_h()
            exported_sprites = self._parse_images_h()
            
            with open(PROJECT_FILE, 'r') as f:
                project = json.load(f)

            # Load maps (new format: multiple maps)
            if 'maps' in project:
                self.maps = project['maps']
                self.current_map_idx = project.get('current_map_idx', 0)
                # Ensure index is valid
                self.current_map_idx = min(self.current_map_idx, len(self.maps) - 1)
            # Backwards compatibility: load old single map format
            elif 'map_data' in project:
                self.maps = [{"name": "map1", "data": project['map_data']}]
                self.current_map_idx = 0

            # Update map selector if it exists
            if hasattr(self, 'map_selector'):
                self._update_map_selector()

            # Load textures
            if 'textures' in project:
                for td in project['textures']:
                    tex = Texture.from_dict(td)
                    if os.path.exists(tex.image_path):
                        try:
                            self._create_texture_previews(tex)
                        except Exception as e:
                            print(f"Warning: could not create preview for texture {tex.name}: {e}")
                        tex.index = len(self.textures) + 1
                        self.textures.append(tex)
                    elif tex.name in exported_textures:
                        # Recover from textures.h when source image is missing
                        exported = exported_textures[tex.name]
                        tex.c_array = exported['c_array']
                        tex.resolution = exported['resolution']
                        try:
                            self._create_texture_previews_from_array(tex)
                        except Exception as e:
                            print(f"Warning: could not create preview for texture {tex.name}: {e}")
                        tex.index = len(self.textures) + 1
                        self.textures.append(tex)
                    else:
                        missing_files.append(f"Texture: {tex.name} ({tex.image_path})")
                        self._unloaded_textures.append(td)

            # Load sprites
            if 'sprites' in project:
                for sd in project['sprites']:
                    sprite = Sprite.from_dict(sd)
                    
                    # Check if sprite exists in exported images.h (has edits)
                    if sprite.name in exported_sprites:
                        # Load from exported data (preserves edits)
                        exported = exported_sprites[sprite.name]
                        sprite.c_array = exported['c_array']
                        sprite.transparent = exported['transparent']
                        sprite.resolution = exported['resolution']

                        # Reconstruct RGB image from c_array for preview
                        # We need to create an image from the BGR565 data
                        img_rgb = Image.new("RGB", (sprite.resolution, sprite.resolution))
                        pixels = img_rgb.load()

                        for i, hex_val in enumerate(sprite.c_array):
                            bgr565 = int(hex_val, 16)
                            # Convert BGR565 to RGB
                            blue5 = (bgr565 >> 11) & 0x1F
                            green6 = (bgr565 >> 5) & 0x3F
                            red5 = bgr565 & 0x1F

                            r = (red5 << 3) | (red5 >> 2)
                            g = (green6 << 2) | (green6 >> 4)
                            b = (blue5 << 3) | (blue5 >> 2)

                            x = i % sprite.resolution
                            y = i // sprite.resolution
                            pixels[x, y] = (r, g, b)

                        # Create preview from reconstructed image
                        try:
                            sprite.preview = self._create_sprite_preview(img_rgb, sprite.resolution, sprite.resolution, sprite.transparent)
                        except Exception as e:
                            print(f"Warning: could not create preview for sprite {sprite.name}: {e}")
                            sprite.preview = None

                        self.sprites.append(sprite)
                    elif os.path.exists(sprite.image_path):
                        # Sprite not in images.h - load from original image (new sprite)
                        img = Image.open(sprite.image_path)
                        res = sprite.resolution

                        # Re-detect transparent color and get processed image
                        transparent, img_rgb = self._detect_transparent_color(img, res, res)
                        sprite.transparent = transparent
                        pixels = img_rgb.load()

                        c_vals = []
                        for y in range(res):
                            for x in range(res):
                                r, g, b = pixels[x, y]
                                blue5 = b >> 3
                                green6 = g >> 2
                                red5 = r >> 3
                                color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
                                c_vals.append(f"0x{color:04X}")
                        sprite.c_array = c_vals

                        # Transparency-aware preview with checkerboard background
                        try:
                            sprite.preview = self._create_sprite_preview(img_rgb, res, res, sprite.transparent)
                        except Exception as e:
                            print(f"Warning: could not create preview for sprite {sprite.name}: {e}")
                            sprite.preview = None

                        self.sprites.append(sprite)
                    else:
                        missing_files.append(f"Sprite: {sprite.name} ({sprite.image_path})")
                        self._unloaded_sprites.append(sd)

            # Load colors
            if 'colors' in project:
                for cd in project['colors']:
                    color = Color.from_dict(cd)
                    self.colors.append(color)

            # Load font data
            if 'font_data' in project:
                self.font_data = project['font_data']
                self.font_path = project.get('font_path')
                if self.font_path:
                    self.font_info_label.config(text=f"Font: {os.path.basename(self.font_path)} (5x8)")

            # Update UI
            self._refresh_texture_list()
            self._update_texture_palette()
            self._refresh_sprite_list()
            self._refresh_color_list()
            self._refresh_font_grid()
            self._draw_map_grid()

            # Warn about missing files
            if missing_files:
                messagebox.showwarning(
                    "Missing Image Files",
                    "The following images could not be found:\n\n" + "\n".join(missing_files[:10]) +
                    ("\n..." if len(missing_files) > 10 else "") +
                    "\n\nPlease re-add these textures/sprites."
                )

            print(f"Loaded: {len(self.textures)} textures, {len(self.sprites)} sprites, {len(self.maps)} maps, {len(self.colors)} colors")

        except Exception as e:
            print(f"Error loading project: {e}")
            messagebox.showerror("Load Error", f"Failed to load project: {e}")

    # ========== Auto Export ==========

    def _auto_export(self):
        """Auto-export all files to assets folder."""
        if not self.auto_export_enabled:
            return

        os.makedirs(ASSETS_DIR, exist_ok=True)

        try:
            # Export textures.h (skip if we'd overwrite data with an empty file)
            if self.textures or not self._unloaded_textures:
                content = self._generate_textures_h()
                with open(os.path.join(ASSETS_DIR, "textures.h"), 'w') as f:
                    f.write(content)

            # Export maps.h
            content = self._generate_maps_h()
            with open(os.path.join(ASSETS_DIR, "maps.h"), 'w') as f:
                f.write(content)

            # Export images.h (skip if we'd overwrite data with an empty file)
            if self.sprites or not self._unloaded_sprites:
                content = self._generate_images_h()
                with open(os.path.join(ASSETS_DIR, "images.h"), 'w') as f:
                    f.write(content)

            # Export colors.h
            content = self._generate_colors_h()
            with open(os.path.join(ASSETS_DIR, "colors.h"), 'w') as f:
                f.write(content)

            # Export font.h (only if font data has been initialized)
            if self.font_data is not None:
                content = self._generate_font_h()
                with open(os.path.join(ASSETS_DIR, "font.h"), 'w') as f:
                    f.write(content)

            self.status_label.config(text="Auto-saved to assets/", foreground='green')
        except Exception as e:
            self.status_label.config(text=f"Export error: {e}", foreground='red')

    def _generate_textures_h(self):
        """Generate textures.h content with per-texture resolution support."""
        lines = [
            "#ifndef TEXTURES_H_",
            "#define TEXTURES_H_",
            "",
            "#include <stdint.h>",
            "#include \"../services/graphics.h\"  // For TextureInfo struct",
            "",
        ]

        if self.textures:
            lines.append(f"#define NUM_TEXTURES {len(self.textures)}")
            lines.append("")

        # Generate texture data arrays (row-major order)
        for tex in self.textures:
            lines.append(f"// {tex.name} ({tex.resolution}x{tex.resolution})")
            lines.append(f"static const uint16_t {tex.name}_data[{tex.resolution} * {tex.resolution}] = {{")

            # Format array in rows
            row_size = tex.resolution
            for i in range(0, len(tex.c_array), row_size):
                row = tex.c_array[i:i+row_size]
                lines.append("    " + ", ".join(row) + ",")

            lines.append("};")
            lines.append("")

        # Generate TextureInfo array with per-texture resolution
        if self.textures:
            lines.append("// Texture lookup array with per-texture resolution")
            lines.append("// Map value 1 -> textures[0], value 2 -> textures[1], etc.")
            lines.append("const TextureInfo textures[] = {")
            for tex in self.textures:
                mask = tex.resolution - 1  # Precomputed mask for power-of-2 textures
                lines.append(f"    {{{tex.name}_data, {tex.resolution}, {mask}}},  // {tex.name}")
            lines.append("};")
            lines.append("")

        lines.append("#endif /* TEXTURES_H_ */")

        return "\n".join(lines)

    def _generate_maps_h(self):
        """Generate maps.h content with all maps and pointer array."""
        lines = [
            "#ifndef maps_h_",
            "#define maps_h_",
            "",
            '#include "../services/map.h"',
            "",
            f"#define MAP_COUNT {len(self.maps)}",
            "",
        ]

        # Export each map grid with _grid suffix
        for map_info in self.maps:
            map_name = map_info["name"]
            map_data = map_info["data"]
            lines.append(f"static const uint8_t {map_name}_grid[{MAP_SIZE}][{MAP_SIZE}] = {{")
            for row in map_data:
                lines.append("    {" + ",".join(str(v) for v in row) + "},")
            lines.append("};")
            lines.append("")

        # Export MapInfo descriptors (grid + floor/ceiling textures)
        for map_info in self.maps:
            map_name = map_info["name"]
            floor_tex = map_info.get("floor_texture", 0)
            ceil_tex = map_info.get("ceiling_texture", 0)
            lines.append(f"// floor: {floor_tex} (0=gradient), ceiling: {ceil_tex} (0=solid color)")
            lines.append(f"static const MapInfo {map_name} = {{ {map_name}_grid, {floor_tex}, {ceil_tex} }};")
            lines.append("")

        # Map list for loading by index
        lines.append("// Map list for loading by index")
        lines.append(f"static const MapInfo mapList[{len(self.maps)}] = {{")
        for map_info in self.maps:
            map_name = map_info["name"]
            floor_tex = map_info.get("floor_texture", 0)
            ceil_tex = map_info.get("ceiling_texture", 0)
            lines.append(f"    {{ {map_name}_grid, {floor_tex}, {ceil_tex} }},")
        lines.append("};")
        lines.append("")
        lines.append("#endif /* maps_h_ */")

        return "\n".join(lines)

    def _generate_images_h(self):
        """Generate images.h content with SpriteImage struct for easy dimension access."""
        lines = [
            "#ifndef IMAGES_H_",
            "#define IMAGES_H_",
            "",
            "#include <stdint.h>",
            "",
            "// Sprite image structure - contains pointer, dimensions, and transparent color",
            "typedef struct {",
            "    const uint16_t* data;",
            "    int width;",
            "    int height;",
            "    uint16_t transparent;  // Auto-detected transparent color",
            "} SpriteImage;",
            "",
            "// Clean, user-friendly macros (PRIMARY - use these!)",
            "// No need to specify dimensions or transparent color - all auto-detected!",
            "#define AddSprite(x, y, sprite, scale) \\",
            "    Sprite_Add(x, y, (sprite).data, (sprite).width, (sprite).height, scale, (sprite).transparent)",
            "",
            "#define AddFGSprite(sprite, x, y, scale) \\",
            "    Graphics_ForegroundSprite((sprite).data, x, y, (sprite).width, (sprite).height, scale, (sprite).transparent)",
            "",
        ]

        # Generate sprite data arrays and SpriteImage structs
        for sprite in self.sprites:
            data_name = f"{sprite.name}_data"
            res = sprite.resolution

            # Raw pixel data (static to keep internal)
            lines.append(f"// {sprite.name} ({res}x{res}, transparent=0x{sprite.transparent:04X})")
            lines.append(f"static const uint16_t {data_name}[{res} * {res}] = {{")

            row_size = res
            for i in range(0, len(sprite.c_array), row_size):
                row = sprite.c_array[i:i+row_size]
                lines.append("    " + ", ".join(row) + ",")

            lines.append("};")

            # SpriteImage struct with embedded dimensions and transparent color
            lines.append(f"static const SpriteImage {sprite.name} = {{{data_name}, {res}, {res}, 0x{sprite.transparent:04X}}};")
            lines.append("")

        lines.append("#endif /* IMAGES_H_ */")

        return "\n".join(lines)

    def _generate_colors_h(self):
        """Generate colors.h content with BGR565 color constants."""
        lines = [
            "#ifndef COLORS_H_",
            "#define COLORS_H_",
            "",
            "#include <stdint.h>",
            "",
            "// Color constants in BGR565 format",
            "// Generated by RayCast3D Studio",
            "",
        ]

        for color in self.colors:
            bgr565 = color.to_bgr565()
            lines.append(f"#define {color.name} 0x{bgr565:04X}  // RGB({color.r}, {color.g}, {color.b})")

        lines.append("")
        lines.append("#endif /* COLORS_H_ */")

        return "\n".join(lines)


def main():
    root = tk.Tk()
    app = RayCast3DStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()

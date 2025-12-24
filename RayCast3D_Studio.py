"""
RayCast3D Studio
A GUI application for building maps, managing textures, and sprites for the RayCast3D graphics library.
Automatically saves project state and exports to assets folder.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
from PIL import Image, ImageTk
import os
import json

# Constants
MAP_SIZE = 24
CELL_SIZE = 24  # pixels per cell in the grid display
DEFAULT_TEX_RESOLUTION = 64

# Game display constants (for accurate preview)
GAME_WIDTH = 128
GAME_HEIGHT = 160

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")
PROJECT_FILE = os.path.join(SCRIPT_DIR, "RayCast3D_Studio/studio_project.json")


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

    def memory_bytes(self):
        return self.resolution * self.resolution * 2

    def to_dict(self):
        return {
            'name': self.name,
            'image_path': self.image_path,
            'resolution': self.resolution,
            'transparent': self.transparent
        }

    @staticmethod
    def from_dict(d):
        # Support loading old projects with width/height
        if 'resolution' in d:
            resolution = d['resolution']
        elif 'width' in d:
            resolution = d['width']  # Use width as resolution for old projects
        else:
            resolution = 32  # Default
        return Sprite(d['name'], d['image_path'], resolution,
                      transparent=d.get('transparent', 0x0000))


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
        self.root.geometry("1000x750")

        # Data
        self.textures = []  # List of Texture objects
        self.sprites = []   # List of Sprite objects
        self.colors = []    # List of Color objects

        # Multiple maps support
        self.maps = [{"name": "map1", "data": [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]}]
        self.current_map_idx = 0

        self.selected_texture_idx = 1  # 0 = erase, 1+ = texture
        self.is_drawing = False
        self.tile_images = {}  # Cache for tile PhotoImages on canvas
        self.auto_export_enabled = True  # Auto-export on changes

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

        # Arrow key navigation
        self.root.bind('<Up>', self._on_arrow_up)
        self.root.bind('<Down>', self._on_arrow_down)

        # Escape to deselect
        self.root.bind('<Escape>', self._on_escape_key)

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
        # Top memory display
        memory_frame = ttk.Frame(self.root)
        memory_frame.pack(fill='x', padx=10, pady=5)

        self.memory_label = ttk.Label(memory_frame, text="Memory Usage: 0 bytes", font=('Consolas', 12, 'bold'))
        self.memory_label.pack(side='left')

        self.memory_detail = ttk.Label(memory_frame, text="", font=('Consolas', 10))
        self.memory_detail.pack(side='left', padx=20)

        # Auto-save indicator
        self.status_label = ttk.Label(memory_frame, text="Auto-saving to assets/", font=('Consolas', 9), foreground='green')
        self.status_label.pack(side='right')

        # Keyboard shortcuts hint
        shortcuts_label = ttk.Label(memory_frame, text="Ctrl+T/P: Add | Del: Remove | ↑↓: Navigate | Esc: Deselect | Ctrl+1/2/3: Tabs",
                                    font=('Consolas', 8), foreground='gray')
        shortcuts_label.pack(side='right', padx=20)

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
                                     width=MAP_SIZE * CELL_SIZE,
                                     height=MAP_SIZE * CELL_SIZE,
                                     bg='black', highlightthickness=1)
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

        # Header row
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(5, 0))
        ttk.Label(header_frame, text="Name", font=('Arial', 10, 'bold'), width=20, anchor='w').pack(side='left', padx=5)
        ttk.Label(header_frame, text="Resolution", font=('Arial', 10, 'bold'), width=12, anchor='w').pack(side='left', padx=5)
        ttk.Label(header_frame, text="Memory", font=('Arial', 10, 'bold'), width=12, anchor='w').pack(side='left', padx=5)

        # Scrollable texture list
        list_container = ttk.Frame(main_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.texture_canvas = tk.Canvas(list_container, highlightthickness=0)
        texture_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.texture_canvas.yview)
        self.texture_list_frame = ttk.Frame(self.texture_canvas)

        self.texture_canvas.configure(yscrollcommand=texture_scrollbar.set)
        texture_scrollbar.pack(side='right', fill='y')
        self.texture_canvas.pack(side='left', fill='both', expand=True)
        self.texture_canvas_window = self.texture_canvas.create_window((0, 0), window=self.texture_list_frame, anchor='nw')

        self.texture_list_frame.bind('<Configure>', lambda e: self.texture_canvas.configure(scrollregion=self.texture_canvas.bbox('all')))
        self.texture_canvas.bind('<Configure>', lambda e: self.texture_canvas.itemconfig(self.texture_canvas_window, width=e.width))

        # Mouse wheel scrolling
        self.texture_canvas.bind('<MouseWheel>', lambda e: self.texture_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

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

        # Header row
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(5, 0))
        ttk.Label(header_frame, text="Name", font=('Arial', 10, 'bold'), width=20, anchor='w').pack(side='left', padx=5)
        ttk.Label(header_frame, text="Resolution", font=('Arial', 10, 'bold'), width=12, anchor='w').pack(side='left', padx=5)
        ttk.Label(header_frame, text="Memory", font=('Arial', 10, 'bold'), width=12, anchor='w').pack(side='left', padx=5)

        # Scrollable sprite list
        list_container = ttk.Frame(main_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.sprite_canvas = tk.Canvas(list_container, highlightthickness=0)
        sprite_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.sprite_canvas.yview)
        self.sprite_list_frame = ttk.Frame(self.sprite_canvas)

        self.sprite_canvas.configure(yscrollcommand=sprite_scrollbar.set)
        sprite_scrollbar.pack(side='right', fill='y')
        self.sprite_canvas.pack(side='left', fill='both', expand=True)
        self.sprite_canvas_window = self.sprite_canvas.create_window((0, 0), window=self.sprite_list_frame, anchor='nw')

        self.sprite_list_frame.bind('<Configure>', lambda e: self.sprite_canvas.configure(scrollregion=self.sprite_canvas.bbox('all')))
        self.sprite_canvas.bind('<Configure>', lambda e: self.sprite_canvas.itemconfig(self.sprite_canvas_window, width=e.width))

        # Mouse wheel scrolling
        self.sprite_canvas.bind('<MouseWheel>', lambda e: self.sprite_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Preview area
        preview_frame = ttk.LabelFrame(main_frame, text="Preview (Simulated In-Game Sprite)")
        preview_frame.pack(fill='x', pady=10)

        preview_inner = ttk.Frame(preview_frame)
        preview_inner.pack(padx=10, pady=10)

        self.sprite_preview_label = ttk.Label(preview_inner)
        self.sprite_preview_label.pack(side='left', padx=10)

        self.sprite_preview_info = ttk.Label(preview_inner, text="", font=('Consolas', 9), justify='left')
        self.sprite_preview_info.pack(side='left', padx=10)

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

        # Header row
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(5, 0))
        ttk.Label(header_frame, text="Name", font=('Arial', 10, 'bold'), width=20, anchor='w').pack(side='left', padx=5)
        ttk.Label(header_frame, text="Color", font=('Arial', 10, 'bold'), width=10, anchor='w').pack(side='left', padx=5)
        ttk.Label(header_frame, text="BGR565", font=('Arial', 10, 'bold'), width=12, anchor='w').pack(side='left', padx=5)
        ttk.Label(header_frame, text="RGB", font=('Arial', 10, 'bold'), width=15, anchor='w').pack(side='left', padx=5)

        # Scrollable color list
        list_container = ttk.Frame(main_frame)
        list_container.pack(fill='both', expand=True, pady=5)

        self.color_canvas = tk.Canvas(list_container, highlightthickness=0)
        color_scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.color_canvas.yview)
        self.color_list_frame = ttk.Frame(self.color_canvas)

        self.color_canvas.configure(yscrollcommand=color_scrollbar.set)
        color_scrollbar.pack(side='right', fill='y')
        self.color_canvas.pack(side='left', fill='both', expand=True)
        self.color_canvas_window = self.color_canvas.create_window((0, 0), window=self.color_list_frame, anchor='nw')

        self.color_list_frame.bind('<Configure>', lambda e: self.color_canvas.configure(scrollregion=self.color_canvas.bbox('all')))
        self.color_canvas.bind('<Configure>', lambda e: self.color_canvas.itemconfig(self.color_canvas_window, width=e.width))

        # Mouse wheel scrolling
        self.color_canvas.bind('<MouseWheel>', lambda e: self.color_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

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

    def _refresh_color_list(self):
        """Refresh the color list display."""
        # Clear existing rows
        for widget in self.color_list_frame.winfo_children():
            widget.destroy()
        self.color_rows = []
        self.selected_color_rows = set()
        self.last_color_click = None

        for i, color in enumerate(self.colors):
            row_frame = ttk.Frame(self.color_list_frame)
            row_frame.pack(fill='x', pady=1)

            # Make row clickable for selection (pass event for modifier detection)
            row_frame.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))
            row_frame.bind('<Double-Button-1>', lambda e, idx=i: self._edit_color_at(idx))

            # Name label
            name_label = ttk.Label(row_frame, text=color.name, width=20, anchor='w')
            name_label.pack(side='left', padx=5)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))
            name_label.bind('<Double-Button-1>', lambda e, idx=i: self._edit_color_at(idx))

            # Color swatch (using a small canvas)
            swatch = tk.Canvas(row_frame, width=40, height=20, highlightthickness=1, highlightbackground='gray')
            swatch.create_rectangle(0, 0, 40, 20, fill=color.to_hex_string(), outline='')
            swatch.pack(side='left', padx=5)
            swatch.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))
            swatch.bind('<Double-Button-1>', lambda e, idx=i: self._edit_color_at(idx))

            # BGR565 value
            bgr565_label = ttk.Label(row_frame, text=f"0x{color.to_bgr565():04X}", width=12, anchor='w', font=('Consolas', 9))
            bgr565_label.pack(side='left', padx=5)
            bgr565_label.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))

            # RGB values
            rgb_label = ttk.Label(row_frame, text=f"({color.r}, {color.g}, {color.b})", width=15, anchor='w')
            rgb_label.pack(side='left', padx=5)
            rgb_label.bind('<Button-1>', lambda e, idx=i: self._select_color_row(idx, e))

            self.color_rows.append((row_frame, name_label, swatch, bgr565_label, rgb_label))

    def _deselect_all_colors(self):
        """Deselect all color rows."""
        for idx in list(self.selected_color_rows):
            if idx < len(self.color_rows):
                frame = self.color_rows[idx][0]
                for child in frame.winfo_children():
                    if isinstance(child, ttk.Label):
                        child.configure(background='')
        self.selected_color_rows = set()
        self.last_color_click = None

    def _update_color_highlights(self):
        """Update visual highlighting for all color rows based on selection."""
        for idx, row_data in enumerate(self.color_rows):
            frame = row_data[0]
            bg = '#cce5ff' if idx in self.selected_color_rows else ''
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(background=bg)

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

        for row in range(MAP_SIZE):
            for col in range(MAP_SIZE):
                x1 = col * CELL_SIZE
                y1 = row * CELL_SIZE
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
        for i in range(MAP_SIZE + 1):
            self.map_canvas.create_line(i * CELL_SIZE, 0, i * CELL_SIZE, MAP_SIZE * CELL_SIZE, fill='#333333')
            self.map_canvas.create_line(0, i * CELL_SIZE, MAP_SIZE * CELL_SIZE, i * CELL_SIZE, fill='#333333')

        # Highlight perimeter with different color
        self.map_canvas.create_rectangle(0, 0, MAP_SIZE*CELL_SIZE, MAP_SIZE*CELL_SIZE,
                                          outline='#FF6600', width=2)

    def _on_map_click(self, event):
        """Handle map click."""
        self.is_drawing = True
        self._paint_cell(event)

    def _on_map_drag(self, event):
        """Handle map drag."""
        if self.is_drawing:
            self._paint_cell(event)

    def _on_map_release(self, event):
        """Handle mouse release."""
        self.is_drawing = False
        # Auto-export and save on release
        self._auto_export()
        self._save_project()

    def _on_map_selected(self, event=None):
        """Handle map selection from dropdown."""
        selected_name = self.map_selector_var.get()
        for i, m in enumerate(self.maps):
            if m["name"] == selected_name:
                self.current_map_idx = i
                self._draw_map_grid()
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
        col = event.x // CELL_SIZE
        row = event.y // CELL_SIZE

        if 0 <= row < MAP_SIZE and 0 <= col < MAP_SIZE:
            is_perimeter = self._is_perimeter(row, col)

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
            row_frame = ttk.Frame(self.texture_list_frame)
            row_frame.pack(fill='x', pady=1)

            # Make row clickable for selection (pass event for modifier detection)
            row_frame.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx, e))

            # Name label
            name_label = ttk.Label(row_frame, text=tex.name, width=20, anchor='w')
            name_label.pack(side='left', padx=5)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx, e))

            # Resolution dropdown (always visible)
            res_var = tk.StringVar(value=str(tex.resolution))
            res_combo = ttk.Combobox(row_frame, textvariable=res_var, values=["16", "32", "64", "128"],
                                     width=8, state='readonly')
            res_combo.pack(side='left', padx=5)
            res_combo.bind('<<ComboboxSelected>>', lambda e, idx=i, var=res_var: self._on_texture_resolution_change(idx, var))

            # Memory label
            mem_label = ttk.Label(row_frame, text=f"{tex.memory_bytes()} bytes", width=12, anchor='w')
            mem_label.pack(side='left', padx=5)
            mem_label.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx, e))

            self.texture_rows.append((row_frame, res_var, name_label, mem_label))

    def _deselect_all_textures(self):
        """Deselect all texture rows."""
        for idx in list(self.selected_texture_rows):
            if idx < len(self.texture_rows):
                frame = self.texture_rows[idx][0]
                for child in frame.winfo_children():
                    if isinstance(child, ttk.Label):
                        child.configure(background='')
        self.selected_texture_rows = set()
        self.last_texture_click = None
        self.tex_preview_label.config(image='')
        self.tex_preview_info.config(text='Select a texture to see preview')

    def _update_texture_highlights(self):
        """Update visual highlighting for all texture rows based on selection."""
        for idx, row_data in enumerate(self.texture_rows):
            frame = row_data[0]
            bg = '#cce5ff' if idx in self.selected_texture_rows else ''
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(background=bg)

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
        file_path = filedialog.askopenfilename(
            title="Select Texture Image",
            filetypes=[("Image files", "*.png *.bmp *.jpg *.jpeg"), ("All files", "*.*")]
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

        try:
            resolution = int(self.tex_res_var.get())
            img = Image.open(file_path)
            c_array = image_to_bgr565_array(img, resolution)

            tex = Texture(name, file_path, resolution, c_array)
            tex.index = len(self.textures) + 1

            # Create previews (pixelated)
            self._create_texture_previews(tex)

            self.textures.append(tex)
            self._refresh_texture_list()
            self._update_texture_palette()
            self._draw_map_grid()
            self._update_memory_display()
            self._auto_export()
            self._save_project()

            # Select the new texture
            self._select_texture_row(len(self.textures) - 1)

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
            row_frame = ttk.Frame(self.sprite_list_frame)
            row_frame.pack(fill='x', pady=1)

            # Make row clickable for selection (pass event for modifier detection)
            row_frame.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx, e))

            # Name label
            name_label = ttk.Label(row_frame, text=sprite.name, width=20, anchor='w')
            name_label.pack(side='left', padx=5)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx, e))

            # Resolution dropdown (always visible)
            res_var = tk.StringVar(value=str(sprite.resolution))
            res_combo = ttk.Combobox(row_frame, textvariable=res_var, values=["16", "32", "64", "128"],
                                     width=8, state='readonly')
            res_combo.pack(side='left', padx=5)
            res_combo.bind('<<ComboboxSelected>>', lambda e, idx=i, var=res_var: self._on_sprite_resolution_change(idx, var))

            # Memory label
            mem_label = ttk.Label(row_frame, text=f"{sprite.memory_bytes()} bytes", width=12, anchor='w')
            mem_label.pack(side='left', padx=5)
            mem_label.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx, e))

            self.sprite_rows.append((row_frame, res_var, name_label, mem_label))

    def _deselect_all_sprites(self):
        """Deselect all sprite rows."""
        for idx in list(self.selected_sprite_rows):
            if idx < len(self.sprite_rows):
                frame = self.sprite_rows[idx][0]
                for child in frame.winfo_children():
                    if isinstance(child, ttk.Label):
                        child.configure(background='')
        self.selected_sprite_rows = set()
        self.last_sprite_click = None
        self.sprite_preview_label.config(image='')
        self.sprite_preview_info.config(text='Select a sprite to see preview')

    def _update_sprite_highlights(self):
        """Update visual highlighting for all sprite rows based on selection."""
        for idx, row_data in enumerate(self.sprite_rows):
            frame = row_data[0]
            bg = '#cce5ff' if idx in self.selected_sprite_rows else ''
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(background=bg)

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
            else:
                self.sprite_preview_info.config(text=f"Resolution: {sprite.resolution}x{sprite.resolution}\n"
                                                     f"Memory: {sprite.memory_bytes()} bytes\n"
                                                     f"Transparent: 0x{sprite.transparent:04X}\n\n"
                                                     f"Preview shows sprite at\n"
                                                     f"simulated in-game scale\n"
                                                     f"with transparency.")
        elif not self.selected_sprite_rows:
            self.sprite_preview_label.config(image='')
            self.sprite_preview_info.config(text='Select a sprite to see preview')

    def _on_sprite_resolution_change(self, idx, var):
        """Handle sprite resolution dropdown change."""
        if idx >= len(self.sprites):
            return

        try:
            new_res = int(var.get())
            sprite = self.sprites[idx]

            if new_res != sprite.resolution:
                self._update_sprite_resolution(sprite, new_res)
                self._refresh_sprite_list()
                # Reselect the row
                self._select_sprite_row(idx)
        except ValueError:
            pass

    def _update_sprite_resolution(self, sprite, new_res):
        """Update a sprite's resolution."""
        if not os.path.exists(sprite.image_path):
            messagebox.showerror("Error", f"Image file not found: {sprite.image_path}")
            return

        try:
            img = Image.open(sprite.image_path)
            transparent, img_rgb = self._detect_transparent_color(img, new_res, new_res)
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
        file_path = filedialog.askopenfilename(
            title="Select Sprite Image",
            filetypes=[("Image files", "*.png *.bmp *.jpg *.jpeg"), ("All files", "*.*")]
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

            self.sprites.append(sprite)
            self._refresh_sprite_list()
            self._update_memory_display()
            self._auto_export()
            self._save_project()

            # Select the new sprite
            self._select_sprite_row(len(self.sprites) - 1)

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

    def _create_sprite_preview(self, img_rgb, width, height, transparent_bgr565):
        """
        Create a transparency-aware sprite preview that simulates in-game appearance.
        Shows checkerboard pattern behind transparent pixels, scaled as it would appear in-game.
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
                # Check if this pixel matches transparent color (with some tolerance due to bit conversion)
                if abs(r - trans_r) <= 8 and abs(g - trans_g) <= 4 and abs(b - trans_b) <= 8:
                    # Transparent - leave checkerboard visible
                    pass
                else:
                    # Opaque - draw sprite pixel
                    checker_pixels[x, y] = (r, g, b)

        return ImageTk.PhotoImage(checker)

    def _update_memory_display(self):
        """Update the memory usage display."""
        tex_memory = sum(t.memory_bytes() for t in self.textures)
        sprite_memory = sum(s.memory_bytes() for s in self.sprites)
        map_memory = MAP_SIZE * MAP_SIZE * len(self.maps)  # 1 byte per cell per map
        total = tex_memory + sprite_memory + map_memory

        self.memory_label.config(text=f"Memory Usage: {total:,} bytes")
        self.memory_detail.config(
            text=f"(Textures: {tex_memory:,} | Sprites: {sprite_memory:,} | Maps: {map_memory} ({len(self.maps)} maps))"
        )

    # ========== Project Save/Load ==========

    def _save_project(self):
        """Save project state to JSON file."""
        try:
            project = {
                'maps': self.maps,  # List of {"name": str, "data": 2D list}
                'current_map_idx': self.current_map_idx,
                'textures': [t.to_dict() for t in self.textures],
                'sprites': [s.to_dict() for s in self.sprites],
                'colors': [c.to_dict() for c in self.colors]
            }
            with open(PROJECT_FILE, 'w') as f:
                json.dump(project, f, indent=2)
            print(f"Saved: {len(self.textures)} textures, {len(self.sprites)} sprites, {len(self.maps)} maps, {len(self.colors)} colors")
        except Exception as e:
            print(f"Error saving project: {e}")
            messagebox.showerror("Save Error", f"Failed to save project: {e}")

    def _load_project(self):
        """Load project state from JSON file."""
        if not os.path.exists(PROJECT_FILE):
            return

        missing_files = []

        try:
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
                        self._create_texture_previews(tex)
                        tex.index = len(self.textures) + 1
                        self.textures.append(tex)
                    else:
                        missing_files.append(f"Texture: {tex.name} ({tex.image_path})")

            # Load sprites
            if 'sprites' in project:
                for sd in project['sprites']:
                    sprite = Sprite.from_dict(sd)
                    if os.path.exists(sprite.image_path):
                        # Regenerate C array, transparent color, and preview
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
                        sprite.preview = self._create_sprite_preview(img_rgb, res, res, sprite.transparent)

                        self.sprites.append(sprite)
                    else:
                        missing_files.append(f"Sprite: {sprite.name} ({sprite.image_path})")

            # Load colors
            if 'colors' in project:
                for cd in project['colors']:
                    color = Color.from_dict(cd)
                    self.colors.append(color)

            # Update UI
            self._refresh_texture_list()
            self._update_texture_palette()
            self._refresh_sprite_list()
            self._refresh_color_list()
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
            # Export textures.h
            content = self._generate_textures_h()
            with open(os.path.join(ASSETS_DIR, "textures.h"), 'w') as f:
                f.write(content)

            # Export map.h
            content = self._generate_map_h()
            with open(os.path.join(ASSETS_DIR, "map.h"), 'w') as f:
                f.write(content)

            # Export images.h
            content = self._generate_images_h()
            with open(os.path.join(ASSETS_DIR, "images.h"), 'w') as f:
                f.write(content)

            # Export colors.h
            content = self._generate_colors_h()
            with open(os.path.join(ASSETS_DIR, "colors.h"), 'w') as f:
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
                lines.append(f"    {{{tex.name}_data, {tex.resolution}}},  // {tex.name}")
            lines.append("};")
            lines.append("")

        lines.append("#endif /* TEXTURES_H_ */")

        return "\n".join(lines)

    def _generate_map_h(self):
        """Generate map.h content with all maps and pointer array."""
        lines = [
            "#ifndef MAP_H_",
            "#define MAP_H_",
            "",
            "#include <stdint.h>",
            "",
            f"#define MAP_COUNT {len(self.maps)}",
            "",
        ]

        # Export each map with its name
        for map_info in self.maps:
            map_name = map_info["name"]
            map_data = map_info["data"]
            lines.append(f"static const uint8_t {map_name}[{MAP_SIZE}][{MAP_SIZE}] = {{")
            for row in map_data:
                lines.append("    {" + ",".join(str(v) for v in row) + "},")
            lines.append("};")
            lines.append("")

        # Create pointer array for easy map switching
        lines.append("// Map pointer array for easy switching by index")
        lines.append(f"static const uint8_t (*const mapList[{len(self.maps)}])[{MAP_SIZE}] = {{")
        for map_info in self.maps:
            lines.append(f"    {map_info['name']},")
        lines.append("};")
        lines.append("")
        lines.append("#endif /* MAP_H_ */")

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
            lines.append(f"const SpriteImage {sprite.name} = {{{data_name}, {res}, {res}, 0x{sprite.transparent:04X}}};")
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

"""
RayCast3D Studio
A GUI application for building maps, managing textures, and sprites for the RayCast3D game.
Automatically saves project state and exports to assets folder.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
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
PROJECT_FILE = os.path.join(SCRIPT_DIR, "studio_project.json")


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


class RayCast3DStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("RayCast3D Studio")
        self.root.geometry("1000x750")

        # Data
        self.textures = []  # List of Texture objects
        self.sprites = []   # List of Sprite objects
        self.map_data = [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        self.selected_texture_idx = 1  # 0 = erase, 1+ = texture
        self.is_drawing = False
        self.tile_images = {}  # Cache for tile PhotoImages on canvas
        self.auto_export_enabled = True  # Auto-export on changes

        # UI references for list items
        self.texture_rows = []  # List of (frame, combo_var) tuples
        self.sprite_rows = []
        self.selected_texture_row = None
        self.selected_sprite_row = None

        # Initialize perimeter walls
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

    def _save_and_export(self):
        """Manual save and export."""
        self._save_project()
        self._auto_export()
        self.status_label.config(text="Saved!", foreground='green')

    def _on_delete_key(self, event):
        """Handle delete key press."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 1 and self.selected_texture_row is not None:
            self._remove_texture()
        elif current_tab == 2 and self.selected_sprite_row is not None:
            self._remove_sprite()

    def _on_close(self):
        """Handle window close - save and export before closing."""
        print("Closing - saving project...")
        self._save_project()
        self._auto_export()
        self.root.destroy()

    def _init_perimeter(self):
        """Initialize perimeter with texture 1 (default wall)."""
        for i in range(MAP_SIZE):
            self.map_data[0][i] = 1       # Top row
            self.map_data[MAP_SIZE-1][i] = 1  # Bottom row
            self.map_data[i][0] = 1       # Left column
            self.map_data[i][MAP_SIZE-1] = 1  # Right column

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
        shortcuts_label = ttk.Label(memory_frame, text="Ctrl+T: Add Texture | Ctrl+P: Add Sprite | Del: Remove | Ctrl+1/2/3: Switch Tabs",
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

    def _build_map_tab(self):
        """Build the map editor tab."""
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

        remove_btn = ttk.Button(ctrl_frame, text="Remove Selected (Del)", command=self._remove_texture)
        remove_btn.pack(side='left', padx=5)

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

        remove_btn = ttk.Button(ctrl_frame, text="Remove Selected (Del)", command=self._remove_sprite)
        remove_btn.pack(side='left', padx=5)

        ttk.Label(ctrl_frame, text="Default Resolution:").pack(side='left', padx=(20, 5))
        self.sprite_res_var = tk.StringVar(value="32")
        ttk.Combobox(ctrl_frame, textvariable=self.sprite_res_var, values=["16", "32", "64"], width=5).pack(side='left')

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
        Create a preview that simulates how the texture looks on a wall in-game.
        Simulates the raycaster's vertical stretching and sampling at 128x160 resolution.
        """
        # Simulate a wall at moderate distance - texture fills about 120 pixels tall
        wall_height = 120
        wall_width = 64  # Show multiple columns to see the texture pattern

        # Create preview image
        preview = Image.new("RGB", (wall_width, wall_height), (0, 0, 0))
        preview_pixels = preview.load()

        texture_pixels = texture_img.convert("RGB").load()

        # Simulate raycaster sampling for each column
        for x in range(wall_width):
            # Map x to texture column
            tex_x = (x * tex_resolution) // wall_width

            for y in range(wall_height):
                # Simulate the integer division sampling the raycaster uses
                # This is the key to matching in-game appearance
                tex_y = (y * tex_resolution) // wall_height

                # Clamp to valid range
                tex_x = min(tex_x, tex_resolution - 1)
                tex_y = min(tex_y, tex_resolution - 1)

                preview_pixels[x, y] = texture_pixels[tex_x, tex_y]

        # Scale up for visibility (2x)
        display_preview = preview.resize((wall_width * 2, wall_height * 2), Image.NEAREST)

        return ImageTk.PhotoImage(display_preview)

    def _refresh_texture_list(self):
        """Refresh the texture list with inline dropdown."""
        # Clear existing rows
        for widget in self.texture_list_frame.winfo_children():
            widget.destroy()
        self.texture_rows = []
        self.selected_texture_row = None

        for i, tex in enumerate(self.textures):
            row_frame = ttk.Frame(self.texture_list_frame)
            row_frame.pack(fill='x', pady=1)

            # Make row clickable for selection
            row_frame.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx))

            # Name label
            name_label = ttk.Label(row_frame, text=tex.name, width=20, anchor='w')
            name_label.pack(side='left', padx=5)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx))

            # Resolution dropdown (always visible)
            res_var = tk.StringVar(value=str(tex.resolution))
            res_combo = ttk.Combobox(row_frame, textvariable=res_var, values=["16", "32", "64", "128"],
                                     width=8, state='readonly')
            res_combo.pack(side='left', padx=5)
            res_combo.bind('<<ComboboxSelected>>', lambda e, idx=i, var=res_var: self._on_texture_resolution_change(idx, var))

            # Memory label
            mem_label = ttk.Label(row_frame, text=f"{tex.memory_bytes()} bytes", width=12, anchor='w')
            mem_label.pack(side='left', padx=5)
            mem_label.bind('<Button-1>', lambda e, idx=i: self._select_texture_row(idx))

            self.texture_rows.append((row_frame, res_var, name_label, mem_label))

    def _select_texture_row(self, idx):
        """Select a texture row and show preview."""
        # Deselect previous
        if self.selected_texture_row is not None and self.selected_texture_row < len(self.texture_rows):
            old_frame = self.texture_rows[self.selected_texture_row][0]
            old_frame.configure(style='TFrame')

        self.selected_texture_row = idx

        # Highlight selected
        if idx < len(self.texture_rows):
            frame = self.texture_rows[idx][0]
            # Use a different background
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(background='#cce5ff')

        # Show preview
        if idx < len(self.textures):
            tex = self.textures[idx]
            if tex.preview:
                self.tex_preview_label.config(image=tex.preview)
            self.tex_preview_info.config(text=f"Resolution: {tex.resolution}x{tex.resolution}\n"
                                              f"Memory: {tex.memory_bytes()} bytes\n\n"
                                              f"Preview shows how texture\n"
                                              f"appears on a wall at\n"
                                              f"moderate distance in the\n"
                                              f"128x160 game display.")

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

    def _remove_texture(self):
        """Remove selected texture."""
        if self.selected_texture_row is None or self.selected_texture_row >= len(self.textures):
            return

        idx = self.selected_texture_row
        removed_idx = idx + 1

        # Check if this texture is used on perimeter
        perimeter_uses = False
        for row in range(MAP_SIZE):
            for col in range(MAP_SIZE):
                if self._is_perimeter(row, col) and self.map_data[row][col] == removed_idx:
                    perimeter_uses = True
                    break

        if perimeter_uses and len(self.textures) == 1:
            messagebox.showwarning("Cannot Remove", "Cannot remove the only texture - perimeter walls need at least one texture.")
            return

        del self.textures[idx]

        # Update indices
        for i, tex in enumerate(self.textures):
            tex.index = i + 1

        # Update map cells
        for row in range(MAP_SIZE):
            for col in range(MAP_SIZE):
                if self.map_data[row][col] == removed_idx:
                    # If perimeter, set to texture 1, else erase
                    if self._is_perimeter(row, col):
                        self.map_data[row][col] = 1 if self.textures else 1
                    else:
                        self.map_data[row][col] = 0
                elif self.map_data[row][col] > removed_idx:
                    self.map_data[row][col] -= 1

        self.selected_texture_row = None
        self._refresh_texture_list()
        self._update_texture_palette()
        self._draw_map_grid()
        self._update_memory_display()
        self._auto_export()
        self._save_project()

        # Clear preview
        self.tex_preview_label.config(image='')
        self.tex_preview_info.config(text='')

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
        self.selected_sprite_row = None

        for i, sprite in enumerate(self.sprites):
            row_frame = ttk.Frame(self.sprite_list_frame)
            row_frame.pack(fill='x', pady=1)

            # Make row clickable for selection
            row_frame.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx))

            # Name label
            name_label = ttk.Label(row_frame, text=sprite.name, width=20, anchor='w')
            name_label.pack(side='left', padx=5)
            name_label.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx))

            # Resolution dropdown (always visible)
            res_var = tk.StringVar(value=str(sprite.resolution))
            res_combo = ttk.Combobox(row_frame, textvariable=res_var, values=["16", "32", "64"],
                                     width=8, state='readonly')
            res_combo.pack(side='left', padx=5)
            res_combo.bind('<<ComboboxSelected>>', lambda e, idx=i, var=res_var: self._on_sprite_resolution_change(idx, var))

            # Memory label
            mem_label = ttk.Label(row_frame, text=f"{sprite.memory_bytes()} bytes", width=12, anchor='w')
            mem_label.pack(side='left', padx=5)
            mem_label.bind('<Button-1>', lambda e, idx=i: self._select_sprite_row(idx))

            self.sprite_rows.append((row_frame, res_var, name_label, mem_label))

    def _select_sprite_row(self, idx):
        """Select a sprite row and show preview."""
        # Deselect previous
        if self.selected_sprite_row is not None and self.selected_sprite_row < len(self.sprite_rows):
            old_frame = self.sprite_rows[self.selected_sprite_row][0]
            for child in old_frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(background='')

        self.selected_sprite_row = idx

        # Highlight selected
        if idx < len(self.sprite_rows):
            frame = self.sprite_rows[idx][0]
            for child in frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(background='#cce5ff')

        # Show preview
        if idx < len(self.sprites):
            sprite = self.sprites[idx]
            if sprite.preview:
                self.sprite_preview_label.config(image=sprite.preview)
            self.sprite_preview_info.config(text=f"Resolution: {sprite.resolution}x{sprite.resolution}\n"
                                                 f"Memory: {sprite.memory_bytes()} bytes\n"
                                                 f"Transparent: 0x{sprite.transparent:04X}\n\n"
                                                 f"Preview shows sprite at\n"
                                                 f"simulated in-game scale\n"
                                                 f"with transparency.")

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

    def _remove_sprite(self):
        """Remove selected sprite."""
        if self.selected_sprite_row is None or self.selected_sprite_row >= len(self.sprites):
            return

        idx = self.selected_sprite_row
        del self.sprites[idx]

        self.selected_sprite_row = None
        self._refresh_sprite_list()
        self._update_memory_display()
        self._auto_export()
        self._save_project()

        # Clear preview
        self.sprite_preview_label.config(image='')
        self.sprite_preview_info.config(text='')

    def _create_sprite_preview(self, img_rgb, width, height, transparent_bgr565):
        """
        Create a transparency-aware sprite preview that simulates in-game appearance.
        Shows checkerboard pattern behind transparent pixels, scaled as it would appear in-game.
        """
        # Simulate sprite at moderate scale - about 80 pixels tall on 160 pixel screen
        scale = max(1, 80 // height)
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
        map_memory = MAP_SIZE * MAP_SIZE  # 1 byte per cell
        total = tex_memory + sprite_memory + map_memory

        self.memory_label.config(text=f"Memory Usage: {total:,} bytes")
        self.memory_detail.config(
            text=f"(Textures: {tex_memory:,} | Sprites: {sprite_memory:,} | Map: {map_memory})"
        )

    # ========== Project Save/Load ==========

    def _save_project(self):
        """Save project state to JSON file."""
        try:
            project = {
                'map_data': self.map_data,
                'textures': [t.to_dict() for t in self.textures],
                'sprites': [s.to_dict() for s in self.sprites]
            }
            with open(PROJECT_FILE, 'w') as f:
                json.dump(project, f, indent=2)
            print(f"Saved: {len(self.textures)} textures, {len(self.sprites)} sprites")
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

            # Load map data
            if 'map_data' in project:
                self.map_data = project['map_data']

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

            # Update UI
            self._refresh_texture_list()
            self._update_texture_palette()
            self._refresh_sprite_list()
            self._draw_map_grid()

            # Warn about missing files
            if missing_files:
                messagebox.showwarning(
                    "Missing Image Files",
                    "The following images could not be found:\n\n" + "\n".join(missing_files[:10]) +
                    ("\n..." if len(missing_files) > 10 else "") +
                    "\n\nPlease re-add these textures/sprites."
                )

            print(f"Loaded: {len(self.textures)} textures, {len(self.sprites)} sprites")

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

            self.status_label.config(text="Auto-saved to assets/", foreground='green')
        except Exception as e:
            self.status_label.config(text=f"Export error: {e}", foreground='red')

    def _generate_textures_h(self):
        """Generate textures.h content."""
        lines = [
            "#ifndef TEXTURES_H_",
            "#define TEXTURES_H_",
            "",
            "#include <stdint.h>",
            "",
        ]

        if self.textures:
            res = self.textures[0].resolution
            lines.append(f"#define TEX_WIDTH {res}")
            lines.append(f"#define TEX_HEIGHT {res}")
            lines.append(f"#define NUM_TEXTURES {len(self.textures)}")
            lines.append("")

        # Generate texture arrays
        for tex in self.textures:
            lines.append(f"// {tex.name}")
            lines.append(f"const uint16_t {tex.name}[{tex.resolution} * {tex.resolution}] = {{")

            # Format array in rows
            row_size = tex.resolution
            for i in range(0, len(tex.c_array), row_size):
                row = tex.c_array[i:i+row_size]
                lines.append("    " + ", ".join(row) + ",")

            lines.append("};")
            lines.append("")

        # Generate texture pointer array
        if self.textures:
            tex_names = [t.name for t in self.textures]
            lines.append("// Texture lookup array: map value 1 -> textures[0], etc.")
            lines.append(f"const uint16_t* textures[] = {{" + ", ".join(tex_names) + "};")
            lines.append("")

        lines.append("#endif /* TEXTURES_H_ */")

        return "\n".join(lines)

    def _generate_map_h(self):
        """Generate map.h content."""
        lines = [
            "#ifndef MAP_H_",
            "#define MAP_H_",
            "",
            "#include <stdint.h>",
            "",
            f"static const uint8_t testMap[{MAP_SIZE}][{MAP_SIZE}] = {{",
        ]

        for row in self.map_data:
            lines.append("    {" + ",".join(str(v) for v in row) + "},")

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


def main():
    root = tk.Tk()
    app = RayCast3DStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""
RayCast3D Map Builder
A GUI application for building maps, managing textures, and sprites for the RayCast3D game.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import os

# Constants
MAP_SIZE = 24
CELL_SIZE = 24  # pixels per cell in the grid display
DEFAULT_TEX_RESOLUTION = 64


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


class Texture:
    """Represents a wall texture."""
    def __init__(self, name, image_path, resolution, c_array=None):
        self.name = name
        self.image_path = image_path
        self.resolution = resolution
        self.c_array = c_array or []
        self.preview = None  # Tkinter PhotoImage for display
        self.index = 0  # Texture index in map (1-based, 0 = empty)

    def memory_bytes(self):
        return self.resolution * self.resolution * 2


class Sprite:
    """Represents a sprite (foreground or map)."""
    def __init__(self, name, image_path, width, height, sprite_type, c_array=None):
        self.name = name
        self.image_path = image_path
        self.width = width
        self.height = height
        self.sprite_type = sprite_type  # 'foreground' or 'map'
        self.c_array = c_array or []
        self.preview = None

    def memory_bytes(self):
        return self.width * self.height * 2


class MapBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RayCast3D Map Builder")
        self.root.geometry("1200x800")

        # Data
        self.textures = []  # List of Texture objects
        self.sprites = []   # List of Sprite objects
        self.map_data = [[0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        self.selected_texture_idx = 1  # 0 = erase, 1+ = texture
        self.is_drawing = False

        # Initialize perimeter walls
        self._init_perimeter()

        # Build UI
        self._build_ui()
        self._update_memory_display()

    def _init_perimeter(self):
        """Force walls around the perimeter."""
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

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab 1: Map Builder
        self.map_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.map_tab, text='Map Builder')
        self._build_map_tab()

        # Tab 2: Texture Manager
        self.texture_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.texture_tab, text='Textures')
        self._build_texture_tab()

        # Tab 3: Sprite Manager
        self.sprite_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.sprite_tab, text='Sprites')
        self._build_sprite_tab()

        # Tab 4: Export
        self.export_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.export_tab, text='Export')
        self._build_export_tab()

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

        # Erase button
        self.erase_btn = ttk.Button(right_frame, text="Erase (0)", command=lambda: self._select_texture(0))
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

        # Instructions
        instr = ttk.Label(right_frame, text="Click/drag to place walls\nPerimeter walls are locked",
                          font=('Arial', 9), foreground='gray')
        instr.pack(pady=10)

    def _build_texture_tab(self):
        """Build the texture manager tab."""
        main_frame = ttk.Frame(self.texture_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Controls
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(ctrl_frame, text="Add Texture", command=self._add_texture).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Remove Selected", command=self._remove_texture).pack(side='left', padx=5)

        ttk.Label(ctrl_frame, text="Resolution:").pack(side='left', padx=(20, 5))
        self.tex_res_var = tk.StringVar(value="64")
        res_combo = ttk.Combobox(ctrl_frame, textvariable=self.tex_res_var, values=["16", "32", "64", "128"], width=6)
        res_combo.pack(side='left')

        # Texture list
        columns = ('Index', 'Name', 'Resolution', 'Memory (bytes)')
        self.texture_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self.texture_tree.heading(col, text=col)
            self.texture_tree.column(col, width=120)
        self.texture_tree.pack(fill='both', expand=True)

        # Preview area
        preview_frame = ttk.LabelFrame(main_frame, text="Preview")
        preview_frame.pack(fill='x', pady=10)

        self.tex_preview_label = ttk.Label(preview_frame)
        self.tex_preview_label.pack(padx=10, pady=10)

        self.texture_tree.bind('<<TreeviewSelect>>', self._on_texture_select)

    def _build_sprite_tab(self):
        """Build the sprite manager tab."""
        main_frame = ttk.Frame(self.sprite_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Controls
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(ctrl_frame, text="Add Sprite", command=self._add_sprite).pack(side='left', padx=5)
        ttk.Button(ctrl_frame, text="Remove Selected", command=self._remove_sprite).pack(side='left', padx=5)

        ttk.Label(ctrl_frame, text="Type:").pack(side='left', padx=(20, 5))
        self.sprite_type_var = tk.StringVar(value="map")
        type_combo = ttk.Combobox(ctrl_frame, textvariable=self.sprite_type_var, values=["map", "foreground"], width=12)
        type_combo.pack(side='left')

        ttk.Label(ctrl_frame, text="Width:").pack(side='left', padx=(20, 5))
        self.sprite_width_var = tk.StringVar(value="32")
        ttk.Combobox(ctrl_frame, textvariable=self.sprite_width_var, values=["16", "32", "64"], width=5).pack(side='left')

        ttk.Label(ctrl_frame, text="Height:").pack(side='left', padx=(10, 5))
        self.sprite_height_var = tk.StringVar(value="32")
        ttk.Combobox(ctrl_frame, textvariable=self.sprite_height_var, values=["16", "32", "64"], width=5).pack(side='left')

        # Sprite list
        columns = ('Name', 'Type', 'Width', 'Height', 'Memory (bytes)')
        self.sprite_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self.sprite_tree.heading(col, text=col)
            self.sprite_tree.column(col, width=100)
        self.sprite_tree.pack(fill='both', expand=True)

        # Preview area
        preview_frame = ttk.LabelFrame(main_frame, text="Preview")
        preview_frame.pack(fill='x', pady=10)

        self.sprite_preview_label = ttk.Label(preview_frame)
        self.sprite_preview_label.pack(padx=10, pady=10)

        self.sprite_tree.bind('<<TreeviewSelect>>', self._on_sprite_select)

    def _build_export_tab(self):
        """Build the export tab."""
        main_frame = ttk.Frame(self.export_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Output directory selection
        dir_frame = ttk.LabelFrame(main_frame, text="Output Directory")
        dir_frame.pack(fill='x', pady=10)

        self.output_dir_var = tk.StringVar(value=os.path.join(os.path.dirname(__file__), "assets"))
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=60).pack(side='left', padx=10, pady=10)
        ttk.Button(dir_frame, text="Browse", command=self._browse_output_dir).pack(side='left', padx=5)

        # Export buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Export textures.h", command=self._export_textures).pack(pady=5, fill='x')
        ttk.Button(btn_frame, text="Export map.h", command=self._export_map).pack(pady=5, fill='x')
        ttk.Button(btn_frame, text="Export images.h (Sprites)", command=self._export_sprites).pack(pady=5, fill='x')
        ttk.Button(btn_frame, text="Export All", command=self._export_all).pack(pady=20, fill='x')

        # Status
        self.export_status = ttk.Label(main_frame, text="", font=('Arial', 10))
        self.export_status.pack(pady=10)

        # Preview of generated code
        preview_frame = ttk.LabelFrame(main_frame, text="Code Preview")
        preview_frame.pack(fill='both', expand=True, pady=10)

        self.code_preview = tk.Text(preview_frame, height=15, font=('Consolas', 9))
        self.code_preview.pack(fill='both', expand=True, padx=5, pady=5)

    def _draw_map_grid(self):
        """Draw the map grid on canvas."""
        self.map_canvas.delete('all')

        # Create color map for textures
        colors = ['black', '#444444', '#888888', '#CC6600', '#00CC00', '#0066CC', '#CC00CC', '#CCCC00']

        for row in range(MAP_SIZE):
            for col in range(MAP_SIZE):
                x1 = col * CELL_SIZE
                y1 = row * CELL_SIZE
                x2 = x1 + CELL_SIZE
                y2 = y1 + CELL_SIZE

                val = self.map_data[row][col]
                if val == 0:
                    fill_color = 'black'
                else:
                    fill_color = colors[val % len(colors)]

                self.map_canvas.create_rectangle(x1, y1, x2, y2, fill=fill_color, outline='#333333')

                # Show texture index if wall
                if val > 0:
                    self.map_canvas.create_text(x1 + CELL_SIZE//2, y1 + CELL_SIZE//2,
                                                 text=str(val), fill='white', font=('Arial', 8))

        # Highlight perimeter
        self.map_canvas.create_rectangle(0, 0, MAP_SIZE*CELL_SIZE, MAP_SIZE*CELL_SIZE,
                                          outline='red', width=2)

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

    def _paint_cell(self, event):
        """Paint a cell at mouse position."""
        col = event.x // CELL_SIZE
        row = event.y // CELL_SIZE

        if 0 <= row < MAP_SIZE and 0 <= col < MAP_SIZE:
            # Don't allow modifying perimeter
            if row == 0 or row == MAP_SIZE-1 or col == 0 or col == MAP_SIZE-1:
                return

            self.map_data[row][col] = self.selected_texture_idx
            self._draw_map_grid()

    def _select_texture(self, idx):
        """Select a texture for painting."""
        self.selected_texture_idx = idx
        if idx == 0:
            self.selected_label.config(text="Selected: Erase")
        else:
            if idx <= len(self.textures):
                self.selected_label.config(text=f"Selected: {self.textures[idx-1].name}")
            else:
                self.selected_label.config(text=f"Selected: Texture {idx}")

    def _update_texture_palette(self):
        """Update the texture palette in map tab."""
        for widget in self.palette_inner.winfo_children():
            widget.destroy()

        for i, tex in enumerate(self.textures):
            idx = i + 1
            frame = ttk.Frame(self.palette_inner)
            frame.pack(fill='x', pady=2)

            btn = ttk.Button(frame, text=f"{idx}: {tex.name}",
                            command=lambda i=idx: self._select_texture(i))
            btn.pack(fill='x')

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

            # Create preview
            preview_img = resize_and_letterbox(img, 64, 64)
            tex.preview = ImageTk.PhotoImage(preview_img)

            self.textures.append(tex)
            self._refresh_texture_list()
            self._update_texture_palette()
            self._update_memory_display()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load texture: {e}")

    def _remove_texture(self):
        """Remove selected texture."""
        selection = self.texture_tree.selection()
        if not selection:
            return

        idx = self.texture_tree.index(selection[0])
        del self.textures[idx]

        # Update indices
        for i, tex in enumerate(self.textures):
            tex.index = i + 1

        # Clear any map cells using removed texture
        removed_idx = idx + 1
        for row in range(MAP_SIZE):
            for col in range(MAP_SIZE):
                if self.map_data[row][col] == removed_idx:
                    self.map_data[row][col] = 1 if (row == 0 or row == MAP_SIZE-1 or col == 0 or col == MAP_SIZE-1) else 0
                elif self.map_data[row][col] > removed_idx:
                    self.map_data[row][col] -= 1

        self._refresh_texture_list()
        self._update_texture_palette()
        self._draw_map_grid()
        self._update_memory_display()

    def _refresh_texture_list(self):
        """Refresh the texture treeview."""
        for item in self.texture_tree.get_children():
            self.texture_tree.delete(item)

        for tex in self.textures:
            self.texture_tree.insert('', 'end', values=(tex.index, tex.name, tex.resolution, tex.memory_bytes()))

    def _on_texture_select(self, event):
        """Handle texture selection for preview."""
        selection = self.texture_tree.selection()
        if selection:
            idx = self.texture_tree.index(selection[0])
            tex = self.textures[idx]
            if tex.preview:
                self.tex_preview_label.config(image=tex.preview)

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
            width = int(self.sprite_width_var.get())
            height = int(self.sprite_height_var.get())
            sprite_type = self.sprite_type_var.get()

            img = Image.open(file_path)

            # Convert to BGR565
            img_resized = resize_and_letterbox(img, width, height)
            img_resized = img_resized.convert("RGB")
            pixels = img_resized.load()

            c_vals = []
            for y in range(height):
                for x in range(width):
                    r, g, b = pixels[x, y]
                    blue5 = b >> 3
                    green6 = g >> 2
                    red5 = r >> 3
                    color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
                    c_vals.append(f"0x{color:04X}")

            sprite = Sprite(name, file_path, width, height, sprite_type, c_vals)

            # Create preview
            preview_img = resize_and_letterbox(img, 64, 64)
            sprite.preview = ImageTk.PhotoImage(preview_img)

            self.sprites.append(sprite)
            self._refresh_sprite_list()
            self._update_memory_display()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load sprite: {e}")

    def _remove_sprite(self):
        """Remove selected sprite."""
        selection = self.sprite_tree.selection()
        if not selection:
            return

        idx = self.sprite_tree.index(selection[0])
        del self.sprites[idx]

        self._refresh_sprite_list()
        self._update_memory_display()

    def _refresh_sprite_list(self):
        """Refresh the sprite treeview."""
        for item in self.sprite_tree.get_children():
            self.sprite_tree.delete(item)

        for sprite in self.sprites:
            self.sprite_tree.insert('', 'end', values=(
                sprite.name, sprite.sprite_type, sprite.width, sprite.height, sprite.memory_bytes()
            ))

    def _on_sprite_select(self, event):
        """Handle sprite selection for preview."""
        selection = self.sprite_tree.selection()
        if selection:
            idx = self.sprite_tree.index(selection[0])
            sprite = self.sprites[idx]
            if sprite.preview:
                self.sprite_preview_label.config(image=sprite.preview)

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

    def _browse_output_dir(self):
        """Browse for output directory."""
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path:
            self.output_dir_var.set(dir_path)

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
            # Add first texture as index 0 placeholder (map uses 1-based indexing)
            lines.append("// Texture lookup array (index 0 is placeholder)")
            lines.append(f"const uint16_t* textures[] = {{{tex_names[0]}, " + ", ".join(tex_names) + "};")
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
        """Generate images.h content for sprites."""
        lines = [
            "#ifndef IMAGES_H_",
            "#define IMAGES_H_",
            "",
            "#include <stdint.h>",
            "",
            "// Foreground Sprites",
        ]

        # Foreground sprites first
        for sprite in self.sprites:
            if sprite.sprite_type == 'foreground':
                lines.append(f"// {sprite.name} ({sprite.width}x{sprite.height})")
                lines.append(f"const uint16_t {sprite.name}[{sprite.width} * {sprite.height}] = {{")

                row_size = sprite.width
                for i in range(0, len(sprite.c_array), row_size):
                    row = sprite.c_array[i:i+row_size]
                    lines.append("    " + ", ".join(row) + ",")

                lines.append("};")
                lines.append("")

        lines.append("// Map Sprites")

        # Map sprites
        for sprite in self.sprites:
            if sprite.sprite_type == 'map':
                lines.append(f"// {sprite.name} ({sprite.width}x{sprite.height})")
                lines.append(f"const uint16_t {sprite.name}[{sprite.width} * {sprite.height}] = {{")

                row_size = sprite.width
                for i in range(0, len(sprite.c_array), row_size):
                    row = sprite.c_array[i:i+row_size]
                    lines.append("    " + ", ".join(row) + ",")

                lines.append("};")
                lines.append("")

        lines.append("#endif /* IMAGES_H_ */")

        return "\n".join(lines)

    def _export_textures(self):
        """Export textures.h."""
        try:
            content = self._generate_textures_h()
            path = os.path.join(self.output_dir_var.get(), "textures.h")

            with open(path, 'w') as f:
                f.write(content)

            self.export_status.config(text=f"Exported: {path}")
            self.code_preview.delete('1.0', tk.END)
            self.code_preview.insert('1.0', content[:5000] + "\n\n... (truncated)")

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_map(self):
        """Export map.h."""
        try:
            content = self._generate_map_h()
            path = os.path.join(self.output_dir_var.get(), "map.h")

            with open(path, 'w') as f:
                f.write(content)

            self.export_status.config(text=f"Exported: {path}")
            self.code_preview.delete('1.0', tk.END)
            self.code_preview.insert('1.0', content)

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_sprites(self):
        """Export images.h for sprites."""
        try:
            content = self._generate_images_h()
            path = os.path.join(self.output_dir_var.get(), "images.h")

            with open(path, 'w') as f:
                f.write(content)

            self.export_status.config(text=f"Exported: {path}")
            self.code_preview.delete('1.0', tk.END)
            self.code_preview.insert('1.0', content[:5000] + "\n\n... (truncated)")

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _export_all(self):
        """Export all files."""
        try:
            self._export_textures()
            self._export_map()
            self._export_sprites()
            self.export_status.config(text="Exported all files successfully!")
            messagebox.showinfo("Success", "All files exported successfully!")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


def main():
    root = tk.Tk()
    app = MapBuilderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

from PIL import Image
import os
import struct

# Helper: resize image with aspect ratio preserved and letterbox padding
# img: PIL.Image, target width/height, bg_color tuple
# returns a new Image of size (width,height)
def resize_and_letterbox(img, width, height, bg_color=(0, 0, 0)):
    # maintain aspect ratio
    img.thumbnail((width, height), Image.LANCZOS)
    # center on background
    canvas = Image.new("RGB", (width, height), bg_color)
    x = (width - img.width) // 2
    y = (height - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


def bmp_to_c_array_direct_color_scaled(image_file_path, resolution):
    """
    Converts an image into a C array of uint16_t in BGR565 format (square resize with letterboxing).
    """
    try:
        img = Image.open(image_file_path)
        img = resize_and_letterbox(img, resolution, resolution)
        img = img.convert("RGB")
        pixels = img.load()

        c_vals = []
        for y in range(resolution):
            for x in range(resolution):
                r, g, b = pixels[x, y]
                blue5  = b >> 3
                green6 = g >> 2
                red5   = r >> 3
                color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
                c_vals.append(f"0x{color:04X}")

        arr_str = "{\n    " + ", ".join(c_vals) + "\n};"
        name = os.path.splitext(os.path.basename(image_file_path))[0]
        return name, arr_str
    except FileNotFoundError:
        return None, f"Error: File not found at {image_file_path}"
    except Exception as e:
        return None, f"Error processing {image_file_path}: {e}"


def bmp_to_binary(image_file_path, width, height, output_folder):
    """
    Converts an image into a raw binary file of 16-bit BGR565 values with letterbox.
    Writes filename.bin into output_folder.
    """
    try:
        img = Image.open(image_file_path)
        img = resize_and_letterbox(img, width, height)
        img = img.convert("RGB")
        pixels = img.load()

        base = os.path.splitext(os.path.basename(image_file_path))[0]
        bin_path = os.path.join(output_folder, f"{base}.bin")
        os.makedirs(output_folder, exist_ok=True)

        with open(bin_path, 'wb') as bf:
            for y in range(height):
                for x in range(width):
                    r, g, b = pixels[x, y]
                    blue5  = b >> 3
                    green6 = g >> 2
                    red5   = r >> 3
                    color = ((blue5 & 0x1F) << 11) | ((green6 & 0x3F) << 5) | (red5 & 0x1F)
                    bf.write(struct.pack('>H', color))
        return base, bin_path
    except Exception as e:
        return None, f"Error processing {image_file_path}: {e}"


if __name__ == "__main__":
    print("Choose mode:")
    print("1) C array text output (.txt)")
    print("2) Raw binary output (.bin) for SD card (with letterbox)")
    mode = input("Enter 1 or 2: ").strip()

    if mode == '1':
        in_folder = input("Path to folder with BMP/PNG: ")
        out_file  = input("Output text file (.txt): ")
        res       = int(input("Square resolution (e.g. 32): "))

        try:
            imgs = [f for f in os.listdir(in_folder)
                    if f.lower().endswith(('.bmp', '.png'))]
            if not imgs:
                print(f"No BMP/PNG in {in_folder}")
                exit(1)
        except FileNotFoundError:
            print(f"Folder not found: {in_folder}")
            exit(1)

        with open(out_file, 'w') as out:
            for fn in imgs:
                path = os.path.join(in_folder, fn)
                name, arr = bmp_to_c_array_direct_color_scaled(path, res)
                if name:
                    out.write(f"// {fn}\nconst uint16_t {name}[{res}*{res}] = {arr}\n\n")
                else:
                    print(arr)
        print(f"C arrays saved to {out_file}")

    elif mode == '2':
        in_folder = input("Path to folder with BMP/PNG: ")
        out_folder = input("Output folder for .bin files: ")
        w = int(input("Enter width: "))
        h = int(input("Enter height: "))

        try:
            imgs = [f for f in os.listdir(in_folder)
                    if f.lower().endswith(('.bmp', '.png'))]
            if not imgs:
                print(f"No BMP/PNG in {in_folder}")
                exit(1)
        except FileNotFoundError:
            print(f"Folder not found: {in_folder}")
            exit(1)

        for fn in imgs:
            path = os.path.join(in_folder, fn)
            name, binp = bmp_to_binary(path, w, h, out_folder)
            if name:
                print(f"Wrote {binp}")
            else:
                print(binp)
        print(f"Done. Binaries in {out_folder}")

    else:
        print("Invalid choice.")

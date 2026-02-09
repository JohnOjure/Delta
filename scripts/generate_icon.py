from PIL import Image, ImageDraw
import os

def create_icon(size=256):
    """Create the Delta icon image."""
    # Create a simple delta symbol icon
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw a triangle (delta symbol)
    padding = size // 8
    points = [
        (size // 2, padding),              # Top
        (padding, size - padding),         # Bottom left
        (size - padding, size - padding)   # Bottom right
    ]
    # Cornflower blue
    draw.polygon(points, fill=(100, 149, 237))
    
    # Draw inner triangle (hollow effect)
    inner_padding = size // 4
    inner_points = [
        (size // 2, inner_padding + (padding // 2)),
        (inner_padding, size - inner_padding),
        (size - inner_padding, size - inner_padding)
    ]
    # Darker cutout
    draw.polygon(inner_points, fill=(30, 30, 30))
    
    return image

if __name__ == "__main__":
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    os.makedirs(assets_dir, exist_ok=True)
    
    img = create_icon()
    
    # Save as PNG
    png_path = os.path.join(assets_dir, "icon.png")
    img.save(png_path)
    print(f"Created {png_path}")
    
    # Save as ICO
    ico_path = os.path.join(assets_dir, "icon.ico")
    img.save(ico_path, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Created {ico_path}")

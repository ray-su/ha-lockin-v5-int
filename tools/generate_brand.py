"""Generate original neutral artwork; no vendor marks or external assets."""
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    target = Path(__file__).resolve().parents[1] / "custom_components/lockin_v5/brand"
    target.mkdir(exist_ok=True)
    scale = 4
    image = Image.new("RGBA", (256 * scale, 256 * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    def box(values):
        return tuple(value * scale for value in values)
    color = (0, 144, 166, 255)
    draw.rounded_rectangle(box((72, 25, 184, 157)), radius=56 * scale, outline=color, width=19 * scale)
    draw.rounded_rectangle(box((38, 105, 218, 230)), radius=26 * scale, fill=color)
    draw.ellipse(box((111, 137, 145, 171)), fill=(255, 255, 255, 255))
    draw.rounded_rectangle(box((120, 158, 136, 193)), radius=6 * scale, fill=(255, 255, 255, 255))
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        result = image.resize((size, size), Image.Resampling.LANCZOS)
        result.save(target / name, optimize=True)
        with Image.open(target / name) as check:
            assert check.size == (size, size) and check.mode == "RGBA"
    print("Created and verified 256px and 512px neutral PNG icons")


if __name__ == "__main__":
    main()

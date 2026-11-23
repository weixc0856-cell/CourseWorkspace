"""Assembles captured slide screenshots into a single Slide Contact Sheet (4x3 grid).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SLIDES_DIR = Path("D:/CourseContent/build/t1-01-why-aerodynamics/slides")
OUTPUT_SHEET = SLIDES_DIR / "slide-contact-sheet.png"

def make_contact_sheet():
    slide_files = sorted(list(SLIDES_DIR.glob("slide-[0-9][0-9][0-9].png")))
    if not slide_files:
        print("[Error] No slide PNGs found in", SLIDES_DIR)
        return
        
    print(f"[Assembly] Found {len(slide_files)} slide images.")
    
    # 4 columns, 3 rows for 11 slides
    cols = 4
    rows = 3
    
    # Thumbnail resolution: 960 x 540 each
    thumb_w = 960
    thumb_h = 540
    padding = 24
    header_h = 70
    
    sheet_w = cols * thumb_w + (cols + 1) * padding
    sheet_h = rows * thumb_h + (rows + 1) * padding + header_h
    
    sheet = Image.new("RGB", (sheet_w, sheet_h), color="#FAF9F6")
    draw = ImageDraw.Draw(sheet)
    
    # Header title
    title_text = "T1-01 Slide Contact Sheet · Full Episode 11-Slide Master Review (Academic Production Freeze)"
    draw.text((padding, 22), title_text, fill="#252A31")
    
    for idx, f in enumerate(slide_files):
        r = idx // cols
        c = idx % cols
        
        x = padding + c * (thumb_w + padding)
        y = header_h + padding + r * (thumb_h + padding)
        
        with Image.open(f) as img:
            thumb = img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(thumb, (x, y))
            
        # Draw clean border around thumbnail
        draw.rectangle([x, y, x + thumb_w, y + thumb_h], outline="#E3E0D7", width=2)
        
    sheet.save(OUTPUT_SHEET, quality=95)
    print(f"[Done] Generated Slide Contact Sheet: {OUTPUT_SHEET}")

if __name__ == "__main__":
    make_contact_sheet()

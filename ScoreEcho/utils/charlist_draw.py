from io import BytesIO
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .charlist_assets import (
    TEXTURE_PATH,
    XW_FONT_PATH,
    ensure_assets,
    ensure_avatar,
    load_name_id_map,
)
from .score_rank import get_score_grade

# Colors from XutheringWavesUID
GOLD = (233, 203, 142)
SPECIAL_GOLD = (255, 203, 99)
GREY = (175, 175, 175)

def _load_font(size: int) -> ImageFont.FreeTypeFont:
    font_path = XW_FONT_PATH / "waves_fonts.ttf"
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size=size)
    
    return ImageFont.load_default()


def _load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def _make_avatar(role_id: str) -> Image.Image:
    """
    Generate character avatar with mask.
    """
    avatar_path = ensure_avatar(role_id)
    if avatar_path and avatar_path.exists():
        pic = _load_image(avatar_path)
    else:
        pic = Image.new("RGBA", (160, 160), (70, 70, 70, 255))
        draw = ImageDraw.Draw(pic)
        draw.text((80, 80), "?", fill="white", anchor="mm")

    # Resize to standard size for processing
    pic = pic.resize((160, 160))
    
    # Apply Mask
    mask_path = TEXTURE_PATH / "avatar_mask.png"
    if mask_path.exists():
        mask = _load_image(mask_path).resize((160, 160)).split()[-1]
        pic.putalpha(mask)
    
    return pic


def draw_charlist_image(result_data: Dict[str, object], uid: str = "", name: str = "") -> bytes:
    ensure_assets()
    name_id_map = load_name_id_map()

    # Prepare data list
    items: List[Tuple[str, float, str]] = []
    for role_name, score_results in result_data.items():
        total_score = 0.0
        if isinstance(score_results, (int, float)):
            total_score = float(score_results)
        elif isinstance(score_results, list):
            try:
                total_score = sum(float(item) for item in score_results)
            except (TypeError, ValueError):
                total_score = 0.0
        grade = get_score_grade(total_score).upper()
        items.append((role_name, total_score, grade))

    # Sort by score desc
    items.sort(key=lambda x: x[1], reverse=True)

    # Layout Configuration
    card_w = 900
    row_h = 140
    header_h = 280
    footer_h = 60
    margin_top = 20
    
    total_h = header_h + len(items) * (row_h + 15) + footer_h + margin_top

    # Create Background
    bg_path = TEXTURE_PATH / "bg3.png"
    if bg_path.exists():
        bg_img = _load_image(bg_path)
        # Resize/Crop to cover
        bg_ratio = bg_img.width / bg_img.height
        target_ratio = card_w / total_h
        
        if bg_ratio > target_ratio:
            # Image is wider, crop width
            new_h = total_h
            new_w = int(new_h * bg_ratio)
            bg_img = bg_img.resize((new_w, new_h))
            left = (new_w - card_w) // 2
            bg_img = bg_img.crop((left, 0, left + card_w, total_h))
        else:
            # Image is taller, crop height
            new_w = card_w
            new_h = int(new_w / bg_ratio)
            bg_img = bg_img.resize((new_w, new_h))
            bg_img = bg_img.crop((0, 0, card_w, total_h))
            
        # Apply blur for better readability
        bg_img = bg_img.filter(ImageFilter.GaussianBlur(5))
        base = bg_img
    else:
        base = Image.new("RGBA", (card_w, total_h), (20, 22, 26, 255))

    draw = ImageDraw.Draw(base)

    # Fonts - Matches XutheringWavesUID sizes
    font_title = _load_font(42) # Header title
    font_name = _load_font(30) # User name
    font_uid = _load_font(25) # UID
    
    font_row_name = _load_font(30) # Role name
    font_row_score = _load_font(30) # Score value
    font_row_label = _load_font(16) # Score label

    # --- Header ---
    # Draw Title
    draw.text((40, 60), "声骸练度排行", fill="white", font=font_title, anchor="lm")
    
    # Draw User Info
    draw.text((40, 130), f"漂泊者: {name}", fill=GOLD, font=font_name, anchor="lm")
    draw.text((40, 175), f"UID: {uid}", fill=GREY, font=font_uid, anchor="lm")
    
    # Decoration line
    draw.line((40, 200, card_w - 40, 200), fill=(255, 255, 255, 50), width=2)
    
    # --- Rows ---
    y_offset = header_h
    
    # Load row background
    row_bg_path = TEXTURE_PATH / "bar_5star.png"
    if row_bg_path.exists():
        row_bg_base = _load_image(row_bg_path)
    else:
        row_bg_base = Image.new("RGBA", (card_w - 60, row_h), (0, 0, 0, 100))
        
    for role_name, score, grade in items:
        # Create row canvas
        row_w = card_w - 80
        row_img = row_bg_base.resize((row_w, row_h)) if row_bg_path.exists() else row_bg_base.resize((row_w, row_h))

        # 1. Avatar (Left side)
        role_id = name_id_map.get(role_name, "")
        avatar = _make_avatar(role_id)
        # Resize avatar to fit nicely in row - slightly smaller than full height
        avatar = avatar.resize((120, 120))
        # Place avatar - Offset similar to XutheringWavesUID (60, 0) relative to bar?
        # In our redesign we are centering it vertically in the bar
        row_img.paste(avatar, (20, 10), avatar)
        
        draw_row = ImageDraw.Draw(row_img)

        # 2. Name
        # XutheringWavesUID draws name at (180, 83) if it were level? No.
        # We place name to the right of avatar
        draw_row.text((160, 50), role_name, fill="white", font=font_row_name, anchor="lm")
        
        # 3. Grade Icon (Right side)
        score_bg_path = TEXTURE_PATH / f"score_{grade.lower()}.png"
        grade_end_x = row_w - 20
        if score_bg_path.exists():
            grade_icon = _load_image(score_bg_path)
            # Resize if too big
            grade_icon = grade_icon.resize((int(grade_icon.width * 0.9), int(grade_icon.height * 0.9)))
            # Position from right
            icon_x = row_w - grade_icon.width - 20
            icon_y = (row_h - grade_icon.height) // 2
            row_img.alpha_composite(grade_icon, (icon_x, icon_y))
            grade_end_x = icon_x
        else:
            draw_row.text((row_w - 60, row_h//2), grade, fill=SPECIAL_GOLD, font=font_row_score, anchor="mm")

        # 4. Score (Left of Grade)
        # Match XutheringWavesUID style: 
        # Score value: font 30, white
        # Label: font 16, SPECIAL_GOLD
        
        score_x = grade_end_x - 30
        draw_row.text(
            (score_x, 42), # Adjusted y
            f"{score:.2f}",
            fill="white",
            font=font_row_score,
            anchor="rm"
        )
        draw_row.text(
            (score_x, 75), # Adjusted y
            "声骸分数",
            fill=SPECIAL_GOLD,
            font=font_row_label,
            anchor="rm"
        )

        # Paste row onto base
        base.paste(row_img, (40, y_offset), row_img)
        y_offset += row_h + 15

    # Footer
    draw.text((card_w // 2, total_h - 30), "Powered by ScoreEcho", fill=(128, 128, 128, 200), font=font_row_label, anchor="mm")

    buffer = BytesIO()
    base.save(buffer, format="PNG")
    return buffer.getvalue()

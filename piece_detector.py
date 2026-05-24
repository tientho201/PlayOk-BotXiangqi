import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

# Define pieces and their template character variations
RED_TEMPLATES_CHARS = {
    "K": ["帥", "帅"],
    "A": ["仕", "士"],
    "B": ["相", "象"],
    "R": ["俥", "车"],
    "N": ["傌", "马"],
    "C": ["炮", "砲"],
    "P": ["兵"]
}

BLACK_TEMPLATES_CHARS = {
    "k": ["將", "将"],
    "a": ["士"],
    "b": ["象"],
    "r": ["車", "车"],
    "n": ["馬", "马"],
    "c": ["砲", "炮"],
    "p": ["卒"]
}

class PieceDetector:
    """
    OpenCV and Pillow adaptive piece recognition system.
    Generates high-quality vector reference templates in-memory using system fonts
    to avoid requiring external static PNG assets.
    """
    def __init__(self, cell_size=40):
        self.cell_size = cell_size
        self.char_size = int(cell_size * 0.65)  # character region inside piece
        self.font = None
        
        # Pre-render/load templates
        self.red_templates = {}
        self.black_templates = {}
        self._load_or_render_all_templates()

    def _load_system_font(self):
        """
        Attempts to load a standard Chinese system font on Windows in order of preference.
        """
        font_paths = [
            r"C:\Windows\Fonts\simsun.ttc",  # SimSun (standard Songti style matching digital boards like PlayOK)
            r"C:\Windows\Fonts\simkai.ttf",  # KaiTi (handwritten style)
            r"C:\Windows\Fonts\msyh.ttc",    # Microsoft YaHei (sans-serif)
            r"C:\Windows\Fonts\arial.ttf"    # Fallback
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                try:
                    # Optimized ratio to 0.82 to match actual digital token breathing margins on PlayOK perfectly!
                    return ImageFont.truetype(path, int(self.char_size * 0.82))
                except Exception:
                    continue
        return ImageFont.load_default()

    def _render_templates(self, template_chars_dict):
        """
        Renders white characters on a black background to serve as binary template images.
        """
        templates = {}
        for piece_type, chars in template_chars_dict.items():
            templates[piece_type] = []
            for char in chars:
                # Create a black single-channel image
                img = Image.new("L", (self.char_size, self.char_size), 0)
                draw = ImageDraw.Draw(img)
                
                # Compute text boundary to center it perfectly
                try:
                    left, top, right, bottom = draw.textbbox((0, 0), char, font=self.font)
                    w = right - left
                    h = bottom - top
                except AttributeError:
                    # Fallback for older PIL versions
                    w, h = draw.textsize(char, font=self.font)
                    left, top = 0, 0
                
                x_offset = (self.char_size - w) // 2 - left
                y_offset = (self.char_size - h) // 2 - top
                
                draw.text((x_offset, y_offset), char, fill=255, font=self.font)
                
                # Convert PIL image to OpenCV numpy array
                templates[piece_type].append(np.array(img))
        return templates

    def _render_single_char_template(self, char):
        """
        Renders a single character template in-memory.
        """
        img = Image.new("L", (self.char_size, self.char_size), 0)
        draw = ImageDraw.Draw(img)
        try:
            left, top, right, bottom = draw.textbbox((0, 0), char, font=self.font)
            w = right - left
            h = bottom - top
        except AttributeError:
            w, h = draw.textsize(char, font=self.font)
            left, top = 0, 0
        x_offset = (self.char_size - w) // 2 - left
        y_offset = (self.char_size - h) // 2 - top
        draw.text((x_offset, y_offset), char, fill=255, font=self.font)
        return np.array(img)

    def _load_or_render_all_templates(self):
        """
        Loads the pre-saved high-quality digital templates from the templates/ directory if available,
        AND also always appends rendered standard Chinese system fonts to ensure absolute robustness
        across both traditional and simplified character sets under different web themes.
        """
        templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
        
        self.red_templates = {}
        for piece_type in RED_TEMPLATES_CHARS.keys():
            self.red_templates[piece_type] = []
            img_path = os.path.join(templates_dir, f"red_{piece_type.upper()}.png")
            if os.path.exists(img_path):
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img_resized = cv2.resize(img, (self.char_size, self.char_size))
                    self.red_templates[piece_type].append(img_resized)
            
            # Always append system font templates to support both traditional and simplified character variations
            if self.font is None:
                self.font = self._load_system_font()
            for char in RED_TEMPLATES_CHARS[piece_type]:
                img_rendered = self._render_single_char_template(char)
                self.red_templates[piece_type].append(img_rendered)
                    
        self.black_templates = {}
        for piece_type in BLACK_TEMPLATES_CHARS.keys():
            self.black_templates[piece_type] = []
            img_path = os.path.join(templates_dir, f"black_{piece_type.upper()}.png")
            if os.path.exists(img_path):
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    img_resized = cv2.resize(img, (self.char_size, self.char_size))
                    self.black_templates[piece_type].append(img_resized)
            
            # Always append system font templates to support both traditional and simplified character variations
            if self.font is None:
                self.font = self._load_system_font()
            for char in BLACK_TEMPLATES_CHARS[piece_type]:
                img_rendered = self._render_single_char_template(char)
                self.black_templates[piece_type].append(img_rendered)

    def detect_color_and_presence(self, cropped_cell):
        """
        Uses robust pixel-ratio thresholds in HSV color space to detect piece presence and color.
        Excludes wood board background (H ≈ 18-25, S ≈ 130-160, V ≈ 210-240).
        """
        h, w, _ = cropped_cell.shape
        cy, cx = h // 2, w // 2
        r = int(min(h, w) * 0.38)
        
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (cx, cy), r, 255, -1)
        
        hsv = cv2.cvtColor(cropped_cell, cv2.COLOR_BGR2HSV)
        total_pixels = np.sum(mask > 0)
        if total_pixels == 0:
            return False, None
        
        # --- Red piece detection ---
        # Highly saturated bright red on PlayOK: H in [0, 8] or [172, 180], S > 150, V > 100
        red_mask_low  = cv2.inRange(hsv, np.array([0,  150, 100]), np.array([8,   255, 255]))
        red_mask_high = cv2.inRange(hsv, np.array([172, 150, 100]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(red_mask_low, red_mask_high)
        red_mask = cv2.bitwise_and(red_mask, mask)
        red_ratio = np.sum(red_mask > 0) / total_pixels
        
        if red_ratio > 0.15:
            return True, "red"
        
        # --- Black piece detection ---
        # Very dark gray/black circle body on PlayOK: V < 105
        black_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 105]))
        black_mask = cv2.bitwise_and(black_mask, mask)
        black_ratio = np.sum(black_mask > 0) / total_pixels
        
        if black_ratio > 0.30:
            return True, "black"
        
        return False, None


    def binarize_character_text(self, cropped_cell, color):
        """
        Extracts the character stroke pattern from a piece cell as a binary image
        (white strokes on black background) to match the template format.
        
        For PlayOK digital pieces: character strokes are WHITE on a colored (red/dark) background.
        We extract near-white pixels from within the inner circular region.
        
        For traditional wood pieces: character strokes are dark ink on light background.
        We use Otsu with inversion to extract white strokes on black.
        """
        h, w, _ = cropped_cell.shape
        cy, cx = h // 2, w // 2
        
        hsv = cv2.cvtColor(cropped_cell, cv2.COLOR_BGR2HSV)
        
        # Inner region where the character is
        c_r = int(min(h, w) * 0.38)
        
        # Compute mean HSV within the inner circle to classify piece type
        inner_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(inner_mask, (cx, cy), c_r, 255, -1)
        
        mean_s = cv2.mean(hsv[:, :, 1], mask=inner_mask)[0]
        mean_v = cv2.mean(hsv[:, :, 2], mask=inner_mask)[0]
        
        # Digital piece: S > 100 (colored background) or V < 180 (dark background)
        is_digital = (mean_s > 100) or (mean_v < 180)
        
        if is_digital:
            # Extract WHITE character strokes: pixels that are near-white = high V, low S.
            # Broader bounds (V > 165, S < 95) capture compressed white strokes beautifully without background bleed.
            white_mask_arr = cv2.inRange(hsv, np.array([0, 0, 165]), np.array([180, 95, 255]))
            white_in_piece = cv2.bitwise_and(white_mask_arr, inner_mask)
            
            # Crop and resize
            x1_c = max(0, cx - c_r)
            y1_c = max(0, cy - c_r)
            x2_c = min(w, cx + c_r)
            y2_c = min(h, cy + c_r)
            
            text_crop = white_in_piece[y1_c:y2_c, x1_c:x2_c]
            text_bin = cv2.resize(text_crop, (self.char_size, self.char_size))
            # Binarize: ensure binary output
            _, text_bin = cv2.threshold(text_bin, 127, 255, cv2.THRESH_BINARY)
        else:
            # Traditional wood piece: dark ink on light background
            gray = cv2.cvtColor(cropped_cell, cv2.COLOR_BGR2GRAY)
            x1_c = max(0, cx - c_r)
            y1_c = max(0, cy - c_r)
            x2_c = min(w, cx + c_r)
            y2_c = min(h, cy + c_r)
            char_crop = gray[y1_c:y2_c, x1_c:x2_c]
            char_crop = cv2.resize(char_crop, (self.char_size, self.char_size))
            # Invert: dark ink → white, light background → black
            _, text_bin = cv2.threshold(char_crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
        return text_bin

    def recognize_piece(self, cropped_cell, color):
        """
        Performs template matching against rendered character structures.
        Returns the best matching standard Xiangqi FEN character or '.' if unmatched.
        Always returns the best-matching piece type (no strict threshold needed)
        since detect_color_and_presence has already confirmed a piece is present.
        """
        is_piece, detected_color = self.detect_color_and_presence(cropped_cell)
        if not is_piece or detected_color != color:
            return "."
            
        # Get binarized character stroke
        char_bin = self.binarize_character_text(cropped_cell, color)
        
        # Pad char_bin by 5 pixels on all sides to allow sliding correlation (up to 5px shift)
        padded_char = cv2.copyMakeBorder(char_bin, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=0)
        
        best_score = -1.0
        best_type = "."
        
        templates = self.red_templates if color == "red" else self.black_templates
        
        for piece_type, t_imgs in templates.items():
            for t_img in t_imgs:
                # Ensure sizes match exactly
                t_resized = cv2.resize(t_img, (self.char_size, self.char_size))
                
                # Match template inside padded_char
                res = cv2.matchTemplate(padded_char, t_resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                
                if max_val > best_score:
                    best_score = max_val
                    best_type = piece_type
                    
        # Return the best match — piece presence already confirmed by detect_color_and_presence
        if best_score > 0.40:
            return best_type
        return "."

    def scan_board(self, board_img, margin_ratio=0.045, padding=40):
        """
        Splits the padded board image into a 9x10 grid and detects all pieces.
        Subtracts padding from size metrics, computes exact absolute coordinates,
        and extracts perfectly centered cells including outer border regions.
        """
        h, w, _ = board_img.shape
        
        # Deduct padding to calculate actual board size
        orig_w = w - 2 * padding
        orig_h = h - 2 * padding
        
        # Compute dynamic margins based on actual board dimensions
        margin_x = int(orig_w * margin_ratio)
        margin_y = int(orig_h * margin_ratio)
        
        playable_w = orig_w - 2 * margin_x
        playable_h = orig_h - 2 * margin_y
        
        col_width = playable_w / 8.0
        row_height = playable_h / 9.0
        
        # Update internal size parameter to match current board layout scale
        self.cell_size = int(min(col_width, row_height))
        self.char_size = int(self.cell_size * 0.65)
        
        # Regenerate templates for correct scaling if size changed significantly
        if len(self.red_templates) == 0 or self.red_templates["K"][0].shape[0] != self.char_size:
            self.font = None  # Reset font so it re-loads if needed
            self._load_or_render_all_templates()
            
        board_matrix = []
        
        for row in range(10):
            row_pieces = []
            for col in range(9):
                # Compute cell center coordinate (adding padding offset)
                cx = int(padding + margin_x + col * col_width)
                cy = int(padding + margin_y + row * row_height)
                
                # Bounding box of the piece cell (safe to grab outside original bbox due to padding)
                x1 = max(0, cx - self.cell_size // 2)
                y1 = max(0, cy - self.cell_size // 2)
                x2 = min(w, cx + self.cell_size // 2)
                y2 = min(h, cy + self.cell_size // 2)
                
                cropped = board_img[y1:y2, x1:x2]
                
                # Standardize cropped shape
                if cropped.shape[0] != self.cell_size or cropped.shape[1] != self.cell_size:
                    cropped = cv2.resize(cropped, (self.cell_size, self.cell_size))
                    
                # Detect color
                is_piece, color = self.detect_color_and_presence(cropped)
                
                if is_piece:
                    piece = self.recognize_piece(cropped, color)
                    row_pieces.append(piece)
                else:
                    row_pieces.append(".")
            board_matrix.append(row_pieces)
            
        return board_matrix

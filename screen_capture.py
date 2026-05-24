import mss
import numpy as np
import cv2

def capture_screen_area(bbox, padding=40):
    """
    Captures a specific desktop region defined by bbox: [left, top, width, height].
    Applies surrounding padding and clamps bounds to the virtual monitor boundaries
    to prevent out-of-bounds crashes when the board is near screen edges.
    """
    if not bbox or len(bbox) < 4:
        return None
    try:
        left, top, width, height = bbox
        with mss.mss() as sct:
            # Get virtual monitor bounds to clamp padded coordinates safely
            monitors = sct.monitors
            if len(monitors) > 0:
                screen = monitors[0]  # The virtual screen covering all monitors
                screen_l = screen.get("left", 0)
                screen_t = screen.get("top", 0)
                screen_w = screen.get("width", 1920)
                screen_h = screen.get("height", 1080)
            else:
                screen_l, screen_t, screen_w, screen_h = 0, 0, 1920, 1080

            # Calculate proposed padded region
            p_left = int(left - padding)
            p_top = int(top - padding)
            p_width = int(width + 2 * padding)
            p_height = int(height + 2 * padding)

            # Clamp left and adjust width
            if p_left < screen_l:
                diff = screen_l - p_left
                p_left = screen_l
                p_width = max(0, p_width - diff)

            # Clamp top and adjust height
            if p_top < screen_t:
                diff = screen_t - p_top
                p_top = screen_t
                p_height = max(0, p_height - diff)

            # Clamp width and height to right/bottom screen edges
            if p_left + p_width > screen_l + screen_w:
                p_width = max(0, screen_l + screen_w - p_left)
            if p_top + p_height > screen_t + screen_h:
                p_height = max(0, screen_t + screen_h - p_top)

            # If resulting region is invalid, return None
            if p_width <= 0 or p_height <= 0:
                return None

            monitor = {
                "left": p_left,
                "top": p_top,
                "width": p_width,
                "height": p_height
            }
            
            # Grab screenshot of the clamped padded region
            sct_img = sct.grab(monitor)
            frame = np.array(sct_img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            return frame
            
    except Exception as e:
        print(f"[CẢNH BÁO] Chụp ảnh lỗi viền: {e}. Thử chụp không có padding...")
        # Fallback to absolute bounds with no padding
        try:
            left, top, width, height = bbox
            with mss.mss() as sct:
                monitor = {
                    "left": int(left),
                    "top": int(top),
                    "width": int(width),
                    "height": int(height)
                }
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                return frame
        except Exception as fallback_err:
            print(f"[LỖI CRITICAL] Chụp ảnh màn hình thất bại hoàn toàn: {fallback_err}")
            return None

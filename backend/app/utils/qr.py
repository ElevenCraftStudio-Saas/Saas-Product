import qrcode
import os
from pathlib import Path

def generate_qr_code(url: str, slug: str, output_dir: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Ensure directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    file_path = os.path.join(output_dir, f"{slug}_qr.png")
    img.save(file_path)
    return file_path

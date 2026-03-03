import qrcode
from io import BytesIO
import base64
from decimal import Decimal

def generate_upi_qr_code(account, amount: Decimal, transaction_note: str = ""):
    """Generate UPI QR code for payment"""
    
    # Standard UPI URL format
    upi_url = (
        f"upi://pay?"
        f"pa={account.upi_id}&"
        f"pn={account.account_holder_name}&"
        f"am={float(amount):.2f}&"
        f"cu=INR"
    )
    
    if transaction_note:
        upi_url += f"&tn={transaction_note.replace(' ', '%20')}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return img_base64, upi_url

import qrcode
from io import BytesIO
import base64

def generate_upi_qr_code(account, amount=None, transaction_note="Payment"):
    """
    Generate UPI QR code base64 string for the given receivable account.
    
    :param account: ReceivableAccount instance
    :param amount: Optional payment amount (Decimal/float/str)
    :param transaction_note: Optional transaction note text
    :return: base64-encoded PNG image of the QR code, UPI payment URI string
    """
    # Compose UPI URI
    # Mandatory fields: pa (upi_id), pn (account_holder_name)
    # Optional: am (amount), tn (transaction note), cu (currency)
    
    upi_uri = f"upi://pay?pa={account.upi_id}&pn={account.account_holder_name}"
    
    if amount is not None:
        upi_uri += f"&am={amount}"
    
    upi_uri += f"&cu=INR&tn={transaction_note}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to in-memory bytes buffer
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    # Encode image to base64 to embed or send over APIs
    qr_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    
    return qr_base64, upi_uri
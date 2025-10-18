from pyhanko.sign import signers,fields
from pyhanko.sign.pkcs11 import PKCS11Signer, open_pkcs11_session
from pyhanko_certvalidator import ValidationContext
from pyhanko.sign.fields import SigSeedSubFilter
from pyhanko.pdf_utils import text, images
from pyhanko.pdf_utils.font import opentype
from pyhanko import stamp
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
def sign_pdf_pades(
    input_pdf: str,
    output_pdf: str,
    pkcs11_lib: str,
    token_label: str,
    cert_label: str,
    user_pin: str,
    visible: bool = False,
    visible_text: str = "Firmato digitalmente da ",
    page: int = 0,
    box: tuple = (50, 50, 250, 100)
):
    """
    Sign a PDF (PAdES) using a Bit4id hardware token through PKCS#11.
    Produces a PAdES-BES compliant signature.

    Args:
        input_pdf (str): Path to the PDF to sign
        output_pdf (str): Output signed PDF path
        pkcs11_lib (str): Path to the Bit4id PKCS#11 library
        token_label (str): Token label
        cert_label (str): Label of certificate on token
        user_pin (str): Token PIN
        visible (bool): Whether to show visible signature field
        visible_text (str): Optional text to show on visible signature
        page (int): Page number for visible signature (0-based)
        box (tuple): Coordinates (x1, y1, x2, y2) for visible signature
    """

    # Open a PKCS#11 session
    with open_pkcs11_session(
        lib_location=pkcs11_lib,
        user_pin=user_pin,
    ) as session, open(input_pdf, "rb") as inf:
        # Create a signer object from the PKCS#11 session
        signer = PKCS11Signer(
            pkcs11_session=session,
            cert_id=b"DS3"
        )

        w = IncrementalPdfFileWriter(inf, strict=False)

   
        # Configure PDF signer
        pdf_signer = signers.PdfSigner(
            signers.PdfSignatureMetadata(
                field_name="Signature1",
                # You can change this to PAdES-EPES or add a timestamp later
                subfilter=SigSeedSubFilter.PADES,
                #validation_context=ValidationContext(allow_fetching=True),
                md_algorithm='sha256'
            ),
            signer=signer,
            stamp_style=stamp.TextStampStyle(
                # the 'signer' and 'ts' parameters will be interpolated by pyHanko, if present
                stamp_text=visible_text+': %(signer)s\nTime: %(ts)s',
                text_box_style=text.TextBoxStyle(
                    font=opentype.GlyphAccumulatorFactory('./NotoSans-Regular.ttf')
                ),
            ),
            
        )

        # Sign the PDF
        with open(output_pdf, "wb") as outf:
            if visible:
                from pyhanko.sign.fields import SigFieldSpec
                sig_field = SigFieldSpec(
                    sig_field_name="Signature1",
                    on_page=page,
                    box=box
                )
                fields.append_signature_field(
                    w, sig_field_spec=sig_field)
                pdf_signer.sign_pdf(
                    w,
                    output=outf
                )
            else:
                pdf_signer.sign_pdf(w, output=outf)

    print(f"✅ PDF signed successfully: {output_pdf}")

import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
from datetime import datetime
import sys
import os

# Add version and timestamp info
VERSION = "1.1.0"
LAST_UPDATED = "2025-03-27 16:59:43"
CURRENT_USER = "Dave Maher"

# Function to render PDF pages as images
def pdf_to_images(pdf_bytes):
    doc = fitz.open("pdf", pdf_bytes)
    images = []
    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    return images, doc

# Function to validate crop values
def validate_crop_values(crop_values, page_rect):
    left, top, right, bottom = crop_values
    if left >= right or top >= bottom:
        raise ValueError("Invalid crop values: ensure right > left and bottom > top")
    if right > page_rect.width or bottom > page_rect.height:
        raise ValueError("Crop values exceed page dimensions")

# Improved crop and scale function
def crop_and_scale_pdf(pdf_bytes, crop_values, scale):
    doc = fitz.open("pdf", pdf_bytes)
    output_pdf = fitz.open()

    try:
        for i, page in enumerate(doc):
            rect = page.rect
            left, top, right, bottom = crop_values

            # Validate crop values
            validate_crop_values(crop_values, rect)

            # First, scale the entire page
            scaled_width = rect.width * scale
            scaled_height = rect.height * scale
            
            # Calculate scaled crop coordinates
            scaled_left = left * scale
            scaled_top = top * scale
            scaled_right = right * scale
            scaled_bottom = bottom * scale

            # Create MediaBox for the entire scaled page
            media_box = fitz.Rect(0, 0, scaled_width, scaled_height)

            # Create CropBox for the selected area
            crop_box = fitz.Rect(scaled_left, scaled_top, scaled_right, scaled_bottom)

            # Ensure crop box doesn't exceed page boundaries
            crop_box = crop_box & media_box

            # Debug logging
            st.sidebar.write(f"Page {i+1} Processing Info:")
            st.sidebar.write(f"Original: {rect.width:.2f} x {rect.height:.2f}")
            st.sidebar.write(f"Scaled: {scaled_width:.2f} x {scaled_height:.2f}")
            st.sidebar.write(f"Crop: {crop_box}")

            # Apply the boxes to the page
            page.set_mediabox(media_box)
            page.set_cropbox(crop_box)

            output_pdf.insert_pdf(doc, from_page=i, to_page=i)

        output_bytes = io.BytesIO()
        output_pdf.save(output_bytes)
        return output_bytes.getvalue()
    
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return None
    finally:
        doc.close()
        output_pdf.close()

# Function to convert DWG/DXF to PDF using a Python library
def convert_dwg_to_pdf_lib(dwg_file_path):
    try:
        import ezdxf
        try:
            doc = ezdxf.readfile(dwg_file_path)
        except ezdxf.DXFError as e:
            if "Not a DXF file" in str(e):
                st.error(f"Error: The uploaded file '{os.path.basename(dwg_file_path)}' is not a valid DXF or DWG file that ezdxf can process.  Please upload a DXF file.")
                return None
            else:
                st.error(f"Error reading DXF/DWG file: {e}")
                return None

        # Use a memory buffer instead of a file
        buffer = io.BytesIO()

        from ezdxf.addons import odafc
        if not odafc.is_available:
            st.error("Error: ODA File Converter is not available.  Please install it, or use a different DWG/DXF file.")
            return None
        odafc.export_pdf(doc, buffer)
        pdf_bytes = buffer.getvalue()
        return pdf_bytes

    except ImportError:
        st.error("Error: ezdxf library is required to convert DWG/DXF files. Please install it using 'pip install ezdxf'")
        return None

    except Exception as e:
        st.error(f"An error occurred during DWG/DXF to PDF conversion: {str(e)}")
        return None


# Streamlit UI
st.set_page_config(page_title="Maggie's PDF App", layout="wide")

# App header with version and user info
st.title("📃 Maggie's PDF App")
with st.expander("App Information"):
    st.markdown(f"""
    - **Version:** {VERSION}
    - **Last Updated:** {LAST_UPDATED}
    - **Created by:** {CURRENT_USER}
    """)

# --- Main App Structure ---
app_mode = st.sidebar.radio("Choose Mode", ["Process PDF", "Convert DWG/DXF to PDF"])

if app_mode == "Process PDF":
    st.header("PDF Processing")
    uploaded_file = st.file_uploader("📁 Upload a PDF to process", type=["pdf"])

    if uploaded_file:
        pdf_bytes = uploaded_file.read()
        images, doc = pdf_to_images(pdf_bytes)

        if len(images) > 0:
            # Sidebar controls
            st.sidebar.header("⚙ Controls")
            
            # Page selection
            if len(images) > 1:
                page_idx = st.sidebar.slider("Select Page", 0, len(images) - 1, 0)
            else:
                page_idx = 0
            img = images[page_idx]

            # Crop settings
            width, height = img.size
            st.sidebar.subheader("Crop Settings")
            left = st.sidebar.slider("Left Crop", 0, width, 0)
            top = st.sidebar.slider("Top Crop", 0, height, 0)
            right = st.sidebar.slider("Right Crop", 0, width, width)
            bottom = st.sidebar.slider("Bottom Crop", 0, height, height)

            # Scaling factor
            st.sidebar.subheader("Scale Settings")
            scale = st.sidebar.slider("Scale Factor", 0.5, 2.0, 1.0, 0.1)

            # Main content area
            st.header("Preview")
            try:
                cropped_img = img.crop((left, top, right, bottom))
                new_width_preview = int((right - left) * scale)
                new_height_preview = int((bottom - top) * scale)
                cropped_img = cropped_img.resize((new_width_preview, new_height_preview), Image.LANCZOS)

                # Display preview
                st.image(cropped_img, caption="Cropped and Scaled Preview", use_container_width=True)

                # Process PDF button
                if st.sidebar.button("Apply Crop and Scale"):
                    with st.spinner("Processing..."):
                        output_pdf_bytes = crop_and_scale_pdf(pdf_bytes, (left, top, right, bottom), scale)
                        if output_pdf_bytes:
                            st.success("PDF Cropped & Scaled Successfully!")
                            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                            download_filename = f"cropped_pdf_{timestamp}.pdf"
                            st.sidebar.download_button(
                                "Download Cropped PDF",
                                output_pdf_bytes,
                                download_filename,
                                "application/pdf"
                            )

            except Exception as e:
                st.error(f"Error in preview: {str(e)}")
                st.error(f"Error details: {str(sys.exc_info())}")
        else:
            st.error("No pages found in the uploaded PDF. Please upload a valid PDF file.")

elif app_mode == "Convert DWG/DXF to PDF":
    st.header("DWG/DXF to PDF Conversion")
    dwg_file = st.file_uploader("📁 Upload a DWG or DXF file", type=["dwg", "dxf"])

    if dwg_file:
        dwg_file_path = dwg_file.name

        with open(dwg_file_path, "wb") as f:
            f.write(dwg_file.read())

        if st.button("Convert to PDF"):
            with st.spinner("Converting..."):
                pdf_bytes = convert_dwg_to_pdf_lib(dwg_file_path)

            if pdf_bytes:
                st.success("DWG/DXF converted to PDF successfully!")
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                download_filename = f"converted_{timestamp}.pdf"
                st.download_button(
                    label="Download Converted PDF",
                    data=pdf_bytes,
                    file_name=download_filename,
                    mime="application/pdf",
                )
            else:
                st.error("Conversion failed.")
        if os.path.exists(dwg_file_path):
            os.remove(dwg_file_path)

# Footer
st.markdown("---")
st.markdown("Created by Dave Maher")

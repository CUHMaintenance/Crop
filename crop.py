import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
from datetime import datetime
import sys
import os
import subprocess # For running the conversion command

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

# Function to convert DWG to PDF using a command-line tool (e.g., LibreCAD)
def convert_dwg_to_pdf(dwg_file_path, output_dir):
    try:
        # Construct the command.  This assumes librecad is installed and in the system PATH
        #  Important:  LibreCAD is just an example.  You might need to adapt this
        #  to use a different tool (like a Python library, if one is available, or
        #  another command-line utility).  The "-print" argument is NOT standard
        #  and is just a placeholder.  Replace this with the correct command
        #  for your chosen tool.
        output_path = os.path.join(output_dir, "converted.pdf") # Fixed output filename
        command = ["dxf2pdf", dwg_file_path, output_path] # Example using dxf2pdf

        # Run the command.  Check the return code for success/failure.
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            error_message = f"DWG to PDF conversion failed.  Error: {result.stderr}"
            st.error(error_message)
            return None  # Explicitly return None on failure

        return output_path # Return the path to the created PDF

    except FileNotFoundError:
        error_message = "Error: dxf2pdf command not found.  Please ensure you have installed the required DWG conversion tool and that it is in your system's PATH."
        st.error(error_message)
        return None
    except Exception as e:
        error_message = f"An error occurred during DWG to PDF conversion: {str(e)}"
        st.error(error_message)
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

# --- DWG to PDF Conversion Section ---
st.header("DWG to PDF Conversion") # Added Header for DWG conversion
dwg_file = st.file_uploader("📁 Upload a DWG file", type=["dwg", "dxf"]) # added dxf

if dwg_file:
    # Create a temporary directory for the conversion
    temp_dir = "temp_dwg_conversion"
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Save the uploaded DWG file to the temporary directory
    dwg_file_path = os.path.join(temp_dir, dwg_file.name)
    with open(dwg_file_path, "wb") as f:
        f.write(dwg_file.read())

    if st.button("Convert DWG to PDF"):
        with st.spinner("Converting DWG to PDF..."):
            pdf_path = convert_dwg_to_pdf(dwg_file_path, temp_dir) # Pass temp_dir

        if pdf_path:
            # Offer the converted PDF for download
            with open(pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
            st.success("DWG converted to PDF successfully!")
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            download_filename = f"converted_dwg_{timestamp}.pdf"
            st.download_button(
                label="Download Converted PDF",
                data=pdf_bytes,
                file_name=download_filename,
                mime="application/pdf",
            )
        else:
            st.error("DWG to PDF conversion failed.")

    # Clean up the temporary file
    if os.path.exists(dwg_file_path): # Check if file exists before attempting to delete
        os.remove(dwg_file_path)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir) # Remove the directory

# --- Existing PDF Processing Section ---
st.header("PDF Processing") # Ensure the sections have distinct headers.
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
        # Crop and scale the image for preview
        try:
            cropped_img = img.crop((left, top, right, bottom))
            new_width_preview = int((right - left) * scale)
            new_height_preview = int((bottom - top) * scale)
            cropped_img = cropped_img.resize((new_width_preview, new_height_preview), Image.LANCZOS)

            # Display preview
            st.image(cropped_img, caption="Cropped and Scaled Preview", use_container_width=True)

            # Process PDF button
            if st.sidebar.button("Apply Crop and Scale"): # Changed button text
                with st.spinner("Processing..."):
                    # Apply the same crop and scale logic to the PDF
                    output_pdf_bytes = crop_and_scale_pdf(pdf_bytes, (left, top, right, bottom), scale)
                    if output_pdf_bytes:
                        st.success("PDF Cropped & Scaled Successfully!")
                        # Generate timestamp for filename
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

# Footer
st.markdown("---")
st.markdown("Created by Dave Maher")

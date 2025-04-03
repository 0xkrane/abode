import streamlit as st
import os
import json
import random
import base64
from pathlib import Path
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
import logging
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
BASE_DIR = Path("room_styles")
STYLES_FILE = BASE_DIR / "styles.json"

# Validate OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key not found. Please add it to your .env file.")
else:
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)

def load_styles():
    """Load style information from styles.json"""
    try:
        # First check if we have style directories
        if not BASE_DIR.exists():
            st.error("No style directories found. Please run style_image_downloader.py first.")
            return []
            
        # Find all style directories
        style_dirs = [d for d in BASE_DIR.iterdir() if d.is_dir()]
        
        if not style_dirs:
            st.error("No style directories found. Please run style_image_downloader.py first.")
            return []
            
        # Load styles from directories
        styles = []
        for style_dir in style_dirs:
            style_name = style_dir.name.replace("_", " ").title()
            
            # Get description from description.txt if it exists
            description = ""
            desc_file = style_dir / "description.txt"
            if desc_file.exists():
                with open(desc_file, "r") as f:
                    description = f.read()
            
            # Get image paths
            image_files = [str(style_dir / f) for f in os.listdir(style_dir) 
                          if f.lower().endswith((".jpg", ".jpeg", ".png")) and not f.endswith(".txt")]
            
            if image_files:
                styles.append({
                    "name": style_name,
                    "description": description,
                    "image_paths": image_files
                })
        
        if not styles:
            st.error("No styles with images found. Please run style_image_downloader.py first.")
            return []
            
        return styles
            
    except Exception as e:
        st.error(f"Error loading styles: {e}")
        return []

def select_random_images(styles, num_images=5):
    """Select random images from different styles"""
    all_images = []
    style_info = {}  # To track which style each image belongs to
    
    # Get up to 2 images from each style until we have enough
    random.shuffle(styles)
    for style in styles:
        if len(all_images) >= num_images:
            break
            
        style_images = style["image_paths"]
        if style_images:
            # Shuffle and select up to 2 random images from this style
            random.shuffle(style_images)
            selected = style_images[:min(2, len(style_images))]
            
            for img in selected:
                if len(all_images) < num_images:
                    all_images.append(img)
                    style_info[img] = {
                        "name": style["name"],
                        "description": style.get("description", "")
                    }
    
    return all_images, style_info

def encode_image(image_path):
    """Encode image to base64 for API submission"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def load_image_from_upload(uploaded_file):
    """Load an image from a file upload widget"""
    if uploaded_file is not None:
        # Read the file and convert to base64
        bytes_data = uploaded_file.getvalue()
        encoded = base64.b64encode(bytes_data).decode("utf-8")
        return encoded
    return None

def generate_design_options(liked_images, disliked_images, uploaded_room_image, room_type, room_size="", num_options=5):
    """Generate multiple design options using OpenAI API"""
    design_options = []
    
    try:
        # Prepare system message
        system_message = """You are an expert interior designer with extensive knowledge of furniture styles, color theory, and spatial arrangement.
Your task is to analyze a user's empty room photo and their style preferences, then provide several DIFFERENT design options.

The user has indicated style preferences by liking and disliking example room images.
Use these preferences to understand their taste, but create DIVERSE and DISTINCT design options.

For each design option, you should provide:
1. A TITLE for the design concept (e.g., "Modern Minimalist Oasis", "Cozy Industrial Loft")
2. A BRIEF DESCRIPTION of the overall design approach (1-2 sentences)
3. SPECIFIC RECOMMENDATIONS for furniture, colors, and decor items

Ensure each design option is truly different from the others - vary the colors, furniture styles, layouts, and overall mood."""

        # Prepare the messages
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": [
                {
                    "type": "text",
                    "text": f"I need {num_options} DIFFERENT design options for my {room_type}" + 
                            (f" with dimensions: {room_size}" if room_size else "") + 
                            f". Please create {num_options} distinct approaches, each with its own title, brief description, and specific furniture/decor recommendations. " +
                            "Below is a photo of my empty room, followed by example room images I liked and disliked."
                }
            ]}
        ]
        
        # Add the empty room image
        messages[1]["content"].append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{uploaded_room_image}"
            }
        })
        
        # Add a separator for clarity
        messages[1]["content"].append({
            "type": "text",
            "text": "ROOM IMAGES I LIKED:"
        })
        
        # Add liked images
        for img_path in liked_images:
            encoded_image = encode_image(img_path)
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encoded_image}"
                }
            })
        
        # Add a separator for disliked images
        if disliked_images:
            messages[1]["content"].append({
                "type": "text",
                "text": "ROOM IMAGES I DISLIKED:"
            })
            
            # Add disliked images
            for img_path in disliked_images:
                encoded_image = encode_image(img_path)
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}"
                    }
                })
        
        # Create a placeholder for the loading message
        loading_placeholder = st.empty()
        
        # Display loading message
        loading_placeholder.info(f"Generating {num_options} design options... This may take a moment.")
        
        # Make the API call
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=3000,
            timeout=90.0  # 90 second timeout
        )
        
        # Clear the loading message
        loading_placeholder.empty()
        
        # Process the response
        response_text = response.choices[0].message.content
        
        # Split the response into different design options
        # Expecting format like "Option 1: Title", "Option 2: Title", etc.
        options = []
        
        # Check for different possible formats
        if "OPTION 1" in response_text.upper():
            # Split by "OPTION X" pattern
            parts = response_text.split("\n")
            current_option = ""
            option_num = 0
            
            for part in parts:
                if part.strip().upper().startswith("OPTION ") and ":" in part:
                    if current_option:
                        options.append(current_option.strip())
                    current_option = part
                    option_num += 1
                else:
                    current_option += "\n" + part
            
            # Add the last option
            if current_option:
                options.append(current_option.strip())
                
        elif "DESIGN OPTION 1" in response_text.upper():
            # Split by "DESIGN OPTION X" pattern
            parts = response_text.split("\n")
            current_option = ""
            option_num = 0
            
            for part in parts:
                if part.strip().upper().startswith("DESIGN OPTION ") and ":" in part:
                    if current_option:
                        options.append(current_option.strip())
                    current_option = part
                    option_num += 1
                else:
                    current_option += "\n" + part
            
            # Add the last option
            if current_option:
                options.append(current_option.strip())
                
        elif "1." in response_text and "2." in response_text:
            # Split by numbered list items
            parts = []
            
            for i in range(1, num_options + 1):
                if f"{i}." in response_text:
                    parts.append(f"{i}.")
            
            # Split the text using the numbered parts
            split_text = []
            for i in range(len(parts)):
                if i < len(parts) - 1:
                    start_idx = response_text.find(parts[i])
                    end_idx = response_text.find(parts[i+1])
                    if start_idx != -1 and end_idx != -1:
                        split_text.append(response_text[start_idx:end_idx])
                else:
                    start_idx = response_text.find(parts[i])
                    if start_idx != -1:
                        split_text.append(response_text[start_idx:])
            
            options = split_text
        else:
            # Fallback - just return the whole response as one option
            options = [response_text]
        
        # If we couldn't parse options or have fewer than expected, just split evenly
        if len(options) < num_options:
            st.warning(f"Could only generate {len(options)} distinct options. Adding remaining as variations.")
            
            # Add remaining options as variations
            while len(options) < num_options:
                options.append(f"Design Variation {len(options)+1}:\n" + options[0])
                
        # If we have more than requested, truncate
        if len(options) > num_options:
            options = options[:num_options]
            
        return options
            
    except Exception as e:
        logger.error(f"Error generating design options: {e}")
        st.error(f"Error generating design options: {e}")
        return [f"Error generating design: {str(e)}"]

def main():
    st.set_page_config(
        page_title="Abode - Interior Design Assistant",
        page_icon="🏠",
        layout="wide"
    )
    
    st.title("Abode - Interior Design Assistant")
    
    # Check for API key
    if not api_key:
        st.error("""
        ❌ Missing OpenAI API key. 
        Please add a valid API key to your .env file with: OPENAI_API_KEY=your_actual_key
        Get a key from https://platform.openai.com/api-keys
        """)
        return
    
    # Initialize session state variables
    if "step" not in st.session_state:
        st.session_state.step = 1  # Step 1: Style preferences, Step 2: Room upload, Step 3: Results
    
    # Linear flow - everything on one page
    st.write("---")
    
    # Step 1: Style Preferences
    if st.session_state.step == 1:
        st.header("Step 1: Your Style Preferences")
        st.write("Swipe through these room styles to help us understand your preferences.")
        
        styles = load_styles()
        
        if not styles:
            return
        
        # Initialize session state for image selection
        if "random_images" not in st.session_state:
            random_images, style_info = select_random_images(styles)
            st.session_state.random_images = random_images
            st.session_state.style_info = style_info
            st.session_state.current_index = 0
            st.session_state.liked_images = []
            st.session_state.disliked_images = []
        
        # Display swipe interface
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col2:
            if st.session_state.current_index < len(st.session_state.random_images):
                # Get current image
                current_img = st.session_state.random_images[st.session_state.current_index]
                img_style = st.session_state.style_info[current_img]
                
                # Display image and style info
                st.subheader(img_style["name"])
                st.image(current_img, use_container_width=True)
                
                # Like/dislike buttons
                left_col, like_col, center_col, dislike_col, right_col = st.columns([1, 1, 0.5, 1, 1])
                
                with like_col:
                    if st.button("👍 Like", key=f"like_{st.session_state.current_index}", use_container_width=True):
                        st.session_state.liked_images.append(current_img)
                        st.session_state.current_index += 1
                        st.rerun()
                
                with dislike_col:
                    if st.button("👎 Dislike", key=f"dislike_{st.session_state.current_index}", use_container_width=True):
                        st.session_state.disliked_images.append(current_img)
                        st.session_state.current_index += 1
                        st.rerun()
                        
                # Progress indicator
                st.progress(st.session_state.current_index / len(st.session_state.random_images))
                st.caption(f"Image {st.session_state.current_index + 1} of {len(st.session_state.random_images)}")
            else:
                st.success("You've reviewed all the example rooms!")
                
                # Show summary of liked/disliked styles
                if st.session_state.liked_images:
                    st.subheader("Styles you liked:")
                    liked_styles = [st.session_state.style_info[img]["name"] for img in st.session_state.liked_images]
                    st.write(", ".join(set(liked_styles)))
                
                if st.session_state.disliked_images:
                    st.subheader("Styles you disliked:")
                    disliked_styles = [st.session_state.style_info[img]["name"] for img in st.session_state.disliked_images]
                    st.write(", ".join(set(disliked_styles)))
                
                # Button to proceed or reset
                left_col, button_col1, center_col, button_col2, right_col = st.columns([1.5, 1, 0.5, 1, 1.5])
                
                with button_col1:
                    if st.button("Reset & Try Different Styles", use_container_width=True):
                        for key in ["random_images", "style_info", "current_index", "liked_images", "disliked_images"]:
                            if key in st.session_state:
                                del st.session_state[key]
                        st.rerun()
                
                with button_col2:
                    if st.button("Continue to Room Upload", use_container_width=True):
                        if not st.session_state.liked_images:
                            st.warning("Please like at least one style before continuing.")
                        else:
                            st.session_state.step = 2
                            st.rerun()
    
    # Step 2: Room Upload
    elif st.session_state.step == 2:
        st.header("Step 2: Upload Your Room")
        
        # Back button at the top left
        st.button("← Back to Style Preferences", on_click=lambda: setattr(st.session_state, "step", 1))
        
        # Display a summary of liked styles
        if st.session_state.liked_images:
            liked_styles = [st.session_state.style_info[img]["name"] for img in st.session_state.liked_images]
            st.write("Your preferred styles: " + ", ".join(set(liked_styles)))
        
        # Room type selection
        room_type = st.selectbox(
            "Room Type",
            options=["Living Room", "Bedroom", "Dining Room", "Kitchen", "Bathroom", "Home Office", "Other"]
        )
        
        # Room size (optional)
        room_size = st.text_input("Room Size/Dimensions (optional)", "")
        
        # Room photo upload
        st.write("Upload a photo of your empty room:")
        uploaded_file = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png"])
        
        # Process the uploaded photo
        if uploaded_file is not None:
            # Display the uploaded image
            image = Image.open(uploaded_file)
            st.image(image, caption="Your Room", use_container_width=True)
            
            # Center the Generate Design Options button
            left_col, button_col, right_col = st.columns([1.5, 2, 1.5])
            
            with button_col:
                if st.button("Generate Design Options", use_container_width=True):
                    # Encode the uploaded image
                    encoded_image = load_image_from_upload(uploaded_file)
                    
                    if encoded_image:
                        # Store room info in session state
                        st.session_state.room_type = room_type
                        st.session_state.room_size = room_size
                        st.session_state.room_image = encoded_image
                        
                        # Move to step 3
                        st.session_state.step = 3
                        st.rerun()
    
    # Step 3: Generate and display results
    elif st.session_state.step == 3:
        st.header("Step 3: Your Design Options")
        
        # Back button at the top left
        st.button("← Back to Room Upload", on_click=lambda: setattr(st.session_state, "step", 2))
        
        # If we don't have design options yet, generate them
        if "design_options" not in st.session_state:
            design_options = generate_design_options(
                st.session_state.liked_images,
                st.session_state.disliked_images,
                st.session_state.room_image,
                st.session_state.room_type,
                st.session_state.room_size,
                num_options=5  # Generate 5 different options
            )
            st.session_state.design_options = design_options
        
        # Display each design option first
        st.subheader("Your Design Options")
        
        # Create tabs for each option
        tabs = st.tabs([f"Option {i+1}" for i in range(len(st.session_state.design_options))])
        
        for i, tab in enumerate(tabs):
            with tab:
                st.markdown(st.session_state.design_options[i])
        
        # Display the room image below
        st.subheader("Your Room")
        image_bytes = base64.b64decode(st.session_state.room_image)
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, use_container_width=True)
        
        # Center the Start Over button
        left_col, button_col, right_col = st.columns([1.5, 2, 1.5])
        with button_col:
            if st.button("Start Over", use_container_width=True):
                for key in st.session_state.keys():
                    del st.session_state[key]
                st.rerun()

if __name__ == "__main__":
    main() 